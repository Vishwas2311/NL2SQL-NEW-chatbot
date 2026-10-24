"""Scope-partitioned exact and SQLite FTS5/BM25 retrieval over metadata only."""

import logging
import math
import re
import sqlite3
from contextlib import ExitStack
from dataclasses import dataclass
from functools import cached_property
from threading import RLock

from nl2sql.application.ports import Candidate, EmbeddingProvider
from nl2sql.application.text import normalize
from nl2sql.domain.models import Catalog, Failure, Metric, Principal
from nl2sql.domain.search import (
    RetrievalCandidate,
    SearchRecord,
    authorized_records,
    schema_records,
)
from nl2sql.infrastructure.retrieval.vector_index import (
    SurrealVectorIndex,
)
from nl2sql.settings import RetrievalOptions


@dataclass
class SearchPartition:
    """Each immutable FTS connection has exclusive access under its own grant-partition lock."""

    connection: sqlite3.Connection
    lock: RLock


def search_records(catalog: Catalog) -> tuple[tuple[str, str], ...]:
    """Generate documents only from certified metadata relevant to each granted metric."""
    tables = {table.id: table for table in catalog.tables}
    records: list[tuple[str, str]] = []
    for metric in catalog.metrics:
        table = tables[metric.table]
        column = next(item for item in table.columns if item.name == metric.column)
        terms = (
            metric.id.replace("_", " "),
            metric.domain,
            metric.label,
            *metric.aliases,
            metric.definition,
            table.description,
            column.description,
            *(view.id.replace("_", " ") for view in catalog.views if metric.id in view.metrics),
        )
        records.append((metric.id, " ".join(terms)))
    return tuple(records)


class Retriever:
    """Build per-entitlement indexes once, before requests are admitted."""

    def __init__(
        self,
        catalog: Catalog,
        principals: tuple[Principal, ...],
        encoder: EmbeddingProvider | None = None,
        options: RetrievalOptions | None = None,
    ) -> None:
        self.catalog = catalog
        self.options = options or RetrievalOptions()
        self._indexes: dict[tuple[str, ...], SearchPartition] = {}
        self.encoder = encoder
        self._native_indexes: dict[tuple[str, ...], SurrealVectorIndex] = {}
        self._vectors: dict[tuple[str, ...], tuple[tuple[str, tuple[float, ...]], ...]] = {}
        with ExitStack() as cleanup:
            self._build(principals, cleanup)
            cleanup.pop_all()

    def _build(self, principals: tuple[Principal, ...], cleanup: ExitStack) -> None:
        documents = dict(search_records(self.catalog))
        partitions: dict[tuple[str, ...], tuple[SearchRecord, ...]] = {}
        text_bytes = components = 0
        for principal in principals:
            key = tuple(sorted(principal.metrics))
            if key in partitions:
                continue
            records = authorized_records(self.records, principal)
            text_bytes += sum(
                len(documents[metric].encode()) for metric in key if metric in documents
            )
            text_bytes += sum(len(record.embedding_text.encode()) for record in records)
            partitions[key] = records
            if text_bytes > self.options.max_text_bytes or len(partitions) > 128:
                raise Failure(
                    "BUNDLE_LIMIT", "Partitioned retrieval exceeds its text budget.", "too_large"
                )
        native_mb = 32 * sum(bool(key) for key in partitions) if self.encoder else 0
        if native_mb > self.options.max_native_mb:
            raise Failure(
                "BUNDLE_LIMIT",
                "Partitioned retrieval exceeds its estimated projection memory budget.",
                "too_large",
            )
        self.budget = {
            "text_bytes": text_bytes,
            "estimated_projection_mb": native_mb,
            "partitions": len(partitions),
        }
        prepared: dict[tuple[str, ...], tuple[tuple[str, tuple[float, ...]], ...]] = {}
        if self.encoder is not None:
            for key in partitions:
                if not key:
                    continue
                allowed = [metric for metric in self.catalog.metrics if metric.id in key]
                vectors = self.encoder.encode(tuple(documents[metric.id] for metric in allowed))
                components += sum(len(vector) for vector in vectors)
                if components > 1_000_000:
                    raise Failure(
                        "BUNDLE_LIMIT",
                        "Embedding partitions exceed their component budget.",
                        "too_large",
                    )
                if (
                    len(vectors) != len(allowed)
                    or not vectors
                    or len({len(v) for v in vectors}) != 1
                ):
                    raise ValueError("Embedding output shape does not match the approved metadata")
                if any(
                    not vector
                    or len(vector) > 4096
                    or any(not math.isfinite(value) for value in vector)
                    or math.hypot(*vector) == 0
                    for vector in vectors
                ):
                    raise ValueError("Invalid local embedding vectors")
                prepared[key] = tuple(
                    (metric.id, vector) for metric, vector in zip(allowed, vectors, strict=True)
                )
        self.budget["vector_components"] = components
        for key, records in partitions.items():
            connection = sqlite3.connect(":memory:", check_same_thread=False)
            cleanup.callback(connection.close)
            connection.execute("CREATE VIRTUAL TABLE docs USING fts5(metric_id UNINDEXED, text)")
            connection.execute("CREATE VIRTUAL TABLE schema_docs USING fts5(id UNINDEXED, text)")
            connection.executemany(
                "INSERT INTO schema_docs VALUES (?, ?)",
                ((record.id, record.embedding_text) for record in records),
            )
            for metric in self.catalog.metrics:
                if metric.id in key:
                    connection.execute(
                        "INSERT INTO docs VALUES (?, ?)",
                        (metric.id, documents[metric.id]),
                    )
            connection.commit()
            self._indexes[key] = SearchPartition(connection, RLock())
            if key in prepared:
                self._vectors[key] = prepared[key]
                index = SurrealVectorIndex(prepared[key])
                cleanup.callback(index.close)
                self._native_indexes[key] = index

    def ambiguous_alias(self, text: str, principal: Principal) -> bool:
        """A shared exact alias cannot select among multiple authorized meanings."""
        question = f" {normalize(text)} "
        aliases: dict[str, set[str]] = {}
        for metric in self.catalog.metrics:
            if metric.id in principal.metrics:
                for alias in (metric.label, *metric.aliases):
                    aliases.setdefault(normalize(alias), set()).add(metric.id)
        return any(len(ids) > 1 and f" {alias} " in question for alias, ids in aliases.items())

    def retrieve(
        self, text: str, principal: Principal, domain: str | None = None
    ) -> tuple[Candidate, ...]:
        """Scope filtering happens before search; unknown scope fails closed."""
        allowed: list[Metric] = [
            metric
            for metric in self.catalog.metrics
            if metric.id in principal.metrics and (domain is None or metric.domain == domain)
        ]
        if not allowed:
            return ()
        question = f" {normalize(text)} "
        spans: list[tuple[str, int, int]] = []
        for metric in allowed:
            for alias in (metric.label, *metric.aliases, metric.id.replace("_", " ")):
                for match in re.finditer(
                    r"(?<![a-z0-9])" + re.escape(normalize(alias)) + r"(?![a-z0-9])", question
                ):
                    spans.append((metric.id, match.start(), match.end()))
        matched = {
            key
            for key, start, end in spans
            if not any(
                other != key and left <= start and right >= end and (left < start or right > end)
                for other, left, right in spans
            )
        }
        exact = [metric for metric in allowed if metric.id in matched]
        if exact:
            return tuple(Candidate(metric.id, "exact", 1.0) for metric in exact)[
                : self.options.top_k
            ]
        terms = re.findall(r"[a-z0-9]+", normalize(text))[:40]
        key = tuple(sorted(principal.metrics))
        if not terms or key not in self._indexes:
            return ()
        with self._indexes[key].lock:
            connection = self._indexes[key].connection
            rows = connection.execute(
                "SELECT metric_id, bm25(docs) FROM docs WHERE docs MATCH ? ORDER BY 2 LIMIT ?",
                (" OR ".join(f'"{term}"' for term in terms), self.options.max_candidates),
            ).fetchall()
        permitted = {metric.id for metric in allowed}
        lexical = tuple(
            Candidate(str(row[0]), "bm25", float(row[1])) for row in rows if row[0] in permitted
        )
        # Structural terms can identify a metric even when its own document has no match.
        schema = self.retrieve_schema(text, principal, self.options.max_candidates)
        seen = {item.metric_id for item in lexical}
        expanded = list(lexical)
        for record in schema:
            for metric in record.metric_scope:
                if metric in permitted and metric not in seen:
                    expanded.append(Candidate(metric, "bm25", -record.score))
                    seen.add(metric)
        lexical = tuple(expanded[: self.options.max_candidates])
        if self.encoder is None:
            return lexical[: self.options.top_k]
        return self._hybrid(text, key, permitted, lexical)

    def _hybrid(
        self, text: str, scope: tuple[str, ...], allowed: set[str], lexical: tuple[Candidate, ...]
    ) -> tuple[Candidate, ...]:
        encoder = self.encoder
        assert encoder is not None
        try:
            encoded = encoder.encode((text,))
            if len(encoded) != 1:
                raise ValueError("Expected one query vector")
            query = encoded[0]
            if (
                not query
                or any(not math.isfinite(value) for value in query)
                or math.hypot(*query) == 0
            ):
                raise ValueError("Invalid query vector")
            semantic = list(self._native_indexes[scope].search(query, allowed))
            semantic = [
                (key, score)
                for key, score in semantic[: self.options.max_candidates]
                if key in allowed
            ]
            fusion: dict[str, float] = {}
            for ranking in (
                tuple(item.metric_id for item in lexical),
                tuple(key for key, _ in semantic),
            ):
                for rank, key in enumerate(ranking, 1):
                    fusion[key] = fusion.get(key, 0) + 1 / (self.options.rrf_constant + rank)
            return tuple(
                Candidate(key, "hybrid_rrf", score)
                for key, score in sorted(fusion.items(), key=lambda item: (-item[1], item[0]))
            )[: self.options.top_k]
        except (ValueError, RuntimeError, Failure) as error:
            if isinstance(error, Failure) and error.code == "EMBEDDING_CANCELLED":
                raise
            logging.getLogger("nl2sql").warning("Local embedding failed: %s", type(error).__name__)
            if lexical:
                return lexical[: self.options.top_k]
            raise Failure(
                "EMBEDDING_UNAVAILABLE", "Optional retrieval is unavailable.", "unavailable"
            ) from error

    def retrieve_schema(
        self,
        text: str,
        principal: Principal,
        limit: int = 20,
    ) -> tuple[RetrievalCandidate, ...]:
        """Generalized lexical evidence, partitioned before scoring and link expansion."""
        if not 1 <= limit <= 100:
            raise ValueError("Schema candidate budget must be bounded")
        key = tuple(sorted(principal.metrics))
        terms = re.findall(r"[a-z0-9]+", normalize(text))[:40]
        if key not in self._indexes or not terms:
            return ()
        records = {record.id: record for record in self.authorized_schema(principal)}
        with self._indexes[key].lock:
            rows = (
                self._indexes[key]
                .connection.execute(
                    "SELECT id,bm25(schema_docs) FROM schema_docs WHERE schema_docs MATCH ? "
                    "ORDER BY 2,id LIMIT ?",
                    (" OR ".join(f'"{term}"' for term in terms), limit),
                )
                .fetchall()
            )
        return tuple(
            RetrievalCandidate(
                id=record.id,
                kind=record.kind,
                score=-float(score),
                source="bm25",
                parent_id=record.parent_id,
                related_ids=record.related_ids,
                catalog_version=record.catalog_version,
                metric_scope=record.metric_scope,
                confidence_signals=("certified_mapping", "authorized_partition"),
            )
            for identity, score in rows
            if (record := records.get(str(identity))) is not None
        )

    def authorized_schema(self, principal: Principal) -> tuple[SearchRecord, ...]:
        """Only a configured grant partition can expose approved structural metadata."""
        if tuple(sorted(principal.metrics)) not in self._indexes:
            return ()
        return authorized_records(self.records, principal)

    @cached_property
    def records(self) -> tuple[SearchRecord, ...]:
        """Generated once during immutable index construction."""
        return schema_records(self.catalog)

    def close(self) -> None:
        """Release snapshot-derived metadata indexes."""
        with ExitStack() as cleanup:
            for index in self._native_indexes.values():
                cleanup.callback(index.close)
            for partition in self._indexes.values():
                cleanup.callback(partition.connection.close)

    def vector_manifest(self) -> dict[str, object]:
        """Scope partition, catalog version and IDs accompany every optional vector entry."""
        metrics = {metric.id: metric for metric in self.catalog.metrics}
        return {
            "catalog_version": self.catalog.version,
            "backend": "surreal-exact-cosine",
            "partitions": [
                {
                    "metric_grants": scope,
                    "entries": [
                        {
                            "id": key,
                            "domain": metrics[key].domain,
                            "source": metrics[key].table,
                            "vector": vector,
                        }
                        for key, vector in entries
                    ],
                }
                for scope, entries in sorted(self._vectors.items())
            ],
        }
