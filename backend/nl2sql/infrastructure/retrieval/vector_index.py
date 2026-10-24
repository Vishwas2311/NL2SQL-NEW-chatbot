"""Embedded Surreal vector projection; no extensions, downloads or vector server."""

import math
from contextlib import ExitStack
from threading import RLock

from nl2sql.domain.models import Failure
from nl2sql.infrastructure.embedded import open_projection, records

VectorEntries = tuple[tuple[str, tuple[float, ...]], ...]


def normalized(vector: tuple[float, ...]) -> tuple[float, ...]:
    """Validate dimensions, finite values and norms before native calls."""
    if not 1 <= len(vector) <= 4096 or any(not math.isfinite(value) for value in vector):
        raise ValueError("Invalid vector")
    magnitude = math.hypot(*vector)
    if not math.isfinite(magnitude) or magnitude == 0:
        raise ValueError("Vector must have a finite nonzero norm")
    return tuple(value / magnitude for value in vector)


class SurrealVectorIndex:
    """Exact cosine search over bounded metadata, automatically rebuilt per snapshot."""

    def __init__(self, entries: VectorEntries) -> None:
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
            self._connection = open_projection()
            cleanup.callback(self._connection.close)
            for (key, _), vector in zip(entries, vectors, strict=True):
                self._execute(
                    "CREATE metric CONTENT $record",
                    {"record": {"key": key, "embedding": list(vector)}},
                )
            self._cleanup = cleanup.pop_all()

    def _execute(
        self, query: str, values: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        try:
            return records(self._connection, query, values)
        except Exception as error:
            raise Failure(
                "VECTOR_UNAVAILABLE",
                "The metadata vector projection is unavailable.",
                "unavailable",
            ) from error

    def search(self, vector: tuple[float, ...], allowed: set[str]) -> tuple[tuple[str, float], ...]:
        """The SurrealQL predicate scopes candidates before the result limit."""
        if len(vector) != self.dimension:
            raise ValueError("Query/index dimension mismatch")
        query = normalized(vector)
        with self._lock:
            if self._closed:
                raise Failure(
                    "VECTOR_UNAVAILABLE", "The metadata vector projection is closed.", "unavailable"
                )
            rows = self._execute(
                "SELECT key,vector::similarity::cosine(embedding,$query) AS score "
                "FROM metric WHERE key IN $allowed ORDER BY score DESC,key ASC LIMIT $limit",
                {"allowed": sorted(allowed & self.keys), "query": list(query), "limit": 100},
            )
            return tuple(
                (str(row["key"]), float(str(row["score"])))
                for row in rows
                if math.isfinite(float(str(row["score"]))) and float(str(row["score"])) > 0
            )

    def close(self) -> None:
        """Idempotent native cleanup, serialized with searches."""
        with self._lock:
            if not self._closed:
                self._closed = True
                self._cleanup.close()
