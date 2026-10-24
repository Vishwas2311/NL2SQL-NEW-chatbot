"""Immutable graph snapshots with process-local embedded SurrealDB traversal."""

import json
import logging
import os
import secrets
import time
from pathlib import Path
from threading import RLock

from surrealdb import RecordID

from nl2sql.application.metadata.drift import dependency_graph
from nl2sql.domain.fingerprints import catalog_hash, digest
from nl2sql.domain.models import Catalog, Failure
from nl2sql.infrastructure.embedded import open_projection, records
from nl2sql.telemetry import REQUEST_DEADLINE


def snapshot(catalog: Catalog) -> bytes:
    """Canonical rebuild artifact; SQLite certification remains the authority."""
    dependencies = dependency_graph(catalog)
    return json.dumps(
        {
            "format": "surreal-graph-v1",
            "catalog": catalog_hash(catalog),
            "nodes": sorted(set(dependencies.nodes) | {table.id for table in catalog.tables}),
            "joins": sorted((e.id, e.left, e.right) for e in catalog.relations if e.certified),
            "lineage": sorted(dependencies.links),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


class SurrealGraph:
    """Workers share immutable snapshots, never a locked SurrealKV datastore."""

    def __init__(self, path: Path, catalog: Catalog) -> None:
        self._lock = RLock()
        self._closed = False
        try:
            expected = snapshot(catalog)
            with path.open("rb") as source:
                if source.read(len(expected) + 1) != expected:
                    raise ValueError("Graph snapshot/catalog mismatch")
            self._connection = open_projection()
            try:
                self._populate(catalog)
                nodes = self._rows("SELECT key FROM node")
                dependencies = dependency_graph(catalog)
                if {row["key"] for row in nodes} != set(dependencies.nodes) | {
                    table.id for table in catalog.tables
                }:
                    raise ValueError("Graph nodes mismatch")
                joins = self._rows(
                    "SELECT key, pair, in.key AS source, out.key AS target FROM link "
                    "WHERE kind=$kind",
                    {"kind": "join"},
                )
                if sorted((r["key"], r["source"], r["target"], r["pair"]) for r in joins) != sorted(
                    (e.id, e.left, e.right, json.dumps([e.left, e.right]))
                    for e in catalog.relations
                    if e.certified
                ):
                    raise ValueError("Graph topology mismatch")
                lineage = self._rows(
                    "SELECT in.key AS source, out.key AS target FROM link WHERE kind=$kind",
                    {"kind": "lineage"},
                )
                if {(r["source"], r["target"]) for r in lineage} != set(dependencies.links):
                    raise ValueError("Graph lineage mismatch")
            except BaseException:
                self._connection.close()
                raise
        except Exception as error:
            raise Failure(
                "GRAPH_UNAVAILABLE", "The certified graph is unavailable.", "unavailable"
            ) from error

    @classmethod
    def build(cls, path: Path, catalog: Catalog) -> "SurrealGraph":
        """Validate before atomic publication; never overwrite an existing version."""
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / ".metadata-private").touch(exist_ok=True)
        if path.exists():
            return cls(path, catalog)
        reservation = path.with_suffix(".building")
        owned = False
        temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            with reservation.open("x"):
                owned = True
                if path.exists():
                    return cls(path, catalog)
                with temporary.open("xb") as target:
                    target.write(snapshot(catalog))
                    target.flush()
                    os.fsync(target.fileno())
                with cls(temporary, catalog):
                    pass
                temporary.replace(path)
        except FileExistsError as error:
            remaining = max(0, (REQUEST_DEADLINE.get() or time.time() + 30) - time.time())
            deadline = time.monotonic() + min(30, remaining)
            while time.monotonic() < deadline:
                if path.exists():
                    return cls(path, catalog)
                time.sleep(0.05)
            raise Failure(
                "GRAPH_BUSY", "The certified graph is preparing.", "unavailable"
            ) from error
        except Exception as error:
            logging.getLogger(__name__).error("graph_build_failed")
            raise Failure(
                "GRAPH_BUILD", "The certified graph could not be built.", "unavailable"
            ) from error
        finally:
            if owned:
                reservation.unlink()
                temporary.unlink(missing_ok=True)
        return cls(path, catalog)

    def _populate(self, catalog: Catalog) -> None:
        dependencies = dependency_graph(catalog)
        nodes = set(dependencies.nodes) | {table.id for table in catalog.tables}
        for node in sorted(nodes):
            self._rows(
                "CREATE $id CONTENT $record",
                {"id": RecordID("node", digest(node)), "record": {"key": node}},
            )
        links = [
            (edge.id, edge.left, edge.right, "join") for edge in catalog.relations if edge.certified
        ] + [(left + ":" + right, left, right, "lineage") for left, right in dependencies.links]
        for key, left, right, kind in links:
            self._rows(
                "RELATE $left->link->$right CONTENT $record",
                {
                    "left": RecordID("node", digest(left)),
                    "right": RecordID("node", digest(right)),
                    "record": {"key": key, "kind": kind, "pair": json.dumps([left, right])},
                },
            )

    def _rows(self, query: str, values: dict[str, object] | None = None) -> list[dict[str, object]]:
        try:
            return records(self._connection, query, values)
        except Exception as error:
            logging.getLogger(__name__).error("graph_query_failed")
            raise Failure(
                "GRAPH_UNAVAILABLE", "The certified graph is unavailable.", "unavailable"
            ) from error

    def shortest_path(
        self,
        source: str,
        target: str,
        allowed: set[tuple[str, str]],
        excluded: tuple[str, str] | None = None,
    ) -> list[str]:
        """Frontier BFS filters edges before discovery and never enumerates paths."""
        with self._lock:
            self._check_open()
            parents: dict[str, str | None] = {source: None}
            frontier = [source]
            keys = [json.dumps(pair) for pair in sorted(allowed) if pair != excluded]
            while frontier:
                if target in frontier:
                    route = [target]
                    while (parent := parents[route[-1]]) is not None:
                        route.append(parent)
                    return list(reversed(route))
                rows = self._rows(
                    "SELECT in.key AS source, out.key AS target FROM link "
                    "WHERE in.key IN $frontier AND kind=$kind AND pair IN $pairs "
                    "ORDER BY source,target",
                    {"frontier": frontier, "kind": "join", "pairs": keys},
                )
                frontier = list[str]()
                for row in rows:
                    parent, node = str(row["source"]), str(row["target"])
                    if node not in parents:
                        parents[node] = parent
                        frontier.append(node)
            return []

    def lineage(self, roots: set[str]) -> set[str]:
        """Reach all stored downstream consumers with bounded visited-node work."""
        with self._lock:
            self._check_open()
            known = {str(row["key"]) for row in self._rows("SELECT key FROM node")}
            reached = roots & known
            frontier = sorted(reached)
            while frontier:
                rows = self._rows(
                    "SELECT out.key AS target FROM link WHERE in.key IN $frontier AND kind=$kind",
                    {"frontier": frontier, "kind": "lineage"},
                )
                frontier = sorted({str(row["target"]) for row in rows} - reached)
                reached.update(frontier)
            return reached

    def _check_open(self) -> None:
        if self._closed:
            raise Failure("GRAPH_UNAVAILABLE", "The certified graph is unavailable.", "unavailable")

    def close(self) -> None:
        """Idempotent cleanup after the owning runtime lease drains."""
        with self._lock:
            if not self._closed:
                self._closed = True
                self._connection.close()

    def __enter__(self) -> "SurrealGraph":
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()
