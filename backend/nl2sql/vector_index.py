"""Optional exact FAISS adapter; never installs dependencies or downloads models."""

import importlib
import math
from collections.abc import Callable, Iterable
from typing import Protocol, cast

from nl2sql.domain import Failure

VectorEntries = tuple[tuple[str, tuple[float, ...]], ...]


class VectorIndex(Protocol):
    """One instance per authorized metric-grant partition."""

    def search(self, vector: tuple[float, ...], allowed: set[str]) -> tuple[tuple[str, float], ...]:
        """Return only permitted metric IDs."""
        ...


VectorIndexFactory = Callable[[VectorEntries], VectorIndex]


class FlatIndex(Protocol):
    """Small optional native binding boundary."""

    def add(self, values: object) -> None:
        """Add normalized float32 vectors."""
        ...

    def search(
        self, values: object, count: int
    ) -> tuple[Iterable[Iterable[float]], Iterable[Iterable[int]]]:
        """Search bounded vectors."""
        ...


class FaissModule(Protocol):
    """Only the exact inner-product index is used."""

    IndexFlatIP: Callable[[int], FlatIndex]


class ArrayModule(Protocol):
    """Array conversion boundary without a base NumPy dependency."""

    def ascontiguousarray(self, values: object, dtype: str) -> object:
        """Create contiguous float32 data."""
        ...


def normalized(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Validate dimensions, finite values and norms before native calls."""
    if not 1 <= len(vector) <= 4096 or any(not math.isfinite(value) for value in vector):
        raise ValueError("Invalid vector")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("Vector must have a finite nonzero norm")
    return tuple(value / magnitude for value in vector)


class FaissVectorIndex:
    """Normalized IndexFlatIP cosine search; approval precedes lazy native imports."""

    def __init__(self, entries: VectorEntries, *, approved: bool = False) -> None:
        if not approved:
            raise ValueError("Optional native FAISS requires explicit organizational approval")
        if not entries or len(entries) > 10_000 or len({key for key, _ in entries}) != len(entries):
            raise ValueError("Invalid vector partition")
        vectors = tuple(normalized(vector) for _, vector in entries)
        if len({len(vector) for vector in vectors}) != 1:
            raise ValueError("Embedding dimensions differ")
        self.keys = tuple(key for key, _ in entries)
        self.dimension = len(vectors[0])
        try:
            native = cast(FaissModule, importlib.import_module("faiss"))
            self.arrays = cast(ArrayModule, importlib.import_module("numpy"))
        except ImportError as error:
            raise Failure(
                "VECTOR_DEPENDENCY", "Approved optional vector libraries are unavailable.", 503
            ) from error
        self.index = native.IndexFlatIP(self.dimension)
        self.index.add(self.arrays.ascontiguousarray(vectors, dtype="float32"))

    def search(self, vector: tuple[float, ...], allowed: set[str]) -> tuple[tuple[str, float], ...]:
        """Reject malformed native results and filter before fusion."""
        if len(vector) != self.dimension:
            raise ValueError("Query/index dimension mismatch")
        query = self.arrays.ascontiguousarray((normalized(vector),), dtype="float32")
        scores, indexes = self.index.search(query, min(len(self.keys), 80))
        result: list[tuple[str, float]] = []
        for score, index in zip(next(iter(scores)), next(iter(indexes)), strict=True):
            if not 0 <= index < len(self.keys) or not math.isfinite(score):
                raise ValueError("Invalid FAISS result")
            key = self.keys[index]
            if key in allowed and score > 0:
                result.append((key, float(score)))
        return tuple(sorted(result, key=lambda item: (-item[1], item[0])))[:20]
