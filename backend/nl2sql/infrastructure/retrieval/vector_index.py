"""Embedded Ladybug vector projection; no extensions, downloads or vector server."""

import math
import os
from contextlib import ExitStack
from pathlib import Path
from threading import RLock

import ladybug

from nl2sql.domain.models import Failure

VectorEntries = tuple[tuple[str, tuple[float, ...]], ...]


def normalized(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Validate dimensions, finite values and norms before native calls."""
    if not 1 <= len(vector) <= 4096 or any(not math.isfinite(value) for value in vector):
        raise ValueError("Invalid vector")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("Vector must have a finite nonzero norm")
    return tuple(value / magnitude for value in vector)


class LadybugVectorIndex:
    """Exact cosine search over bounded metadata, automatically rebuilt per snapshot."""

    def __init__(self, entries: VectorEntries, native_dir: Path | None = None) -> None:
        if not entries or len(entries) > 10_000 or len({key for key, _ in entries}) != len(entries):
            raise ValueError("Invalid vector partition")
        vectors = tuple(normalized(vector) for _, vector in entries)
        if len({len(vector) for vector in vectors}) != 1:
            raise ValueError("Embedding dimensions differ")
        self.dimension = len(vectors[0])
        self.keys = {key for key, _ in entries}
        self._lock = RLock()
        self._closed = False
        with ExitStack() as cleanup:
            if os.name == "nt" and native_dir is not None:
                cleanup.callback(os.add_dll_directory(str(native_dir)).close)
            database = ladybug.Database(
                ":memory:", buffer_pool_size=32 * 1024 * 1024, max_num_threads=1
            )
            cleanup.callback(database.close)
            self._connection = ladybug.Connection(database)
            cleanup.callback(self._connection.close)
            self._execute(
                "CREATE NODE TABLE MetadataVector(id STRING PRIMARY KEY, "
                f"embedding DOUBLE[{self.dimension}])"
            )
            for (key, _), vector in zip(entries, vectors, strict=True):
                self._execute(
                    "CREATE (:MetadataVector {id:$id, "
                    f"embedding:CAST($vector AS DOUBLE[{self.dimension}])}})",
                    {"id": key, "vector": list(vector)},
                )
            self._cleanup = cleanup.pop_all()

    def _execute(self, query: str, values: dict[str, object] | None = None) -> list[list[object]]:
        try:
            result = self._connection.execute(query, values)
            if isinstance(result, list):
                for item in result:
                    item.close()
                raise ValueError("Only one vector statement is allowed")
            try:
                rows: list[list[object]] = []
                while result.has_next():
                    rows.append(result.get_next())
                return rows
            finally:
                result.close()
        except Exception as error:
            raise Failure(
                "VECTOR_UNAVAILABLE",
                "The metadata vector projection is unavailable.",
                "unavailable",
            ) from error

    def search(self, vector: tuple[float, ...], allowed: set[str]) -> tuple[tuple[str, float], ...]:
        """The Cypher predicate scopes candidates before the result limit."""
        if len(vector) != self.dimension:
            raise ValueError("Query/index dimension mismatch")
        query = normalized(vector)
        with self._lock:
            if self._closed:
                raise Failure(
                    "VECTOR_UNAVAILABLE", "The metadata vector projection is closed.", "unavailable"
                )
            rows = self._execute(
                "MATCH (v:MetadataVector) WHERE v.id IN $allowed "
                "RETURN v.id,array_cosine_similarity(v.embedding,"
                f"CAST($query AS DOUBLE[{self.dimension}])) AS score "
                "ORDER BY score DESC,v.id LIMIT $limit",
                {"allowed": sorted(allowed & self.keys), "query": list(query), "limit": 100},
            )
            return tuple(
                (str(key), float(str(score)))
                for key, score in rows
                if math.isfinite(float(str(score))) and float(str(score)) > 0
            )

    def close(self) -> None:
        """Idempotent native cleanup, serialized with searches."""
        with self._lock:
            if not self._closed:
                self._closed = True
                self._cleanup.close()
