"""Local immutable Ladybug projections; no extensions, servers or model calls."""

import json
import logging
import os
import secrets
import time
from pathlib import Path
from threading import RLock

import ladybug

from nl2sql.application.metadata.drift import dependency_graph
from nl2sql.domain.fingerprints import catalog_hash
from nl2sql.domain.models import Catalog, Failure
from nl2sql.telemetry import REQUEST_DEADLINE


class LadybugGraph:
    """Bootstrap owns each read-only handle; retirement never deletes shared files."""

    def __init__(
        self, path: Path, catalog: Catalog, buffer_mb: int = 64, native_dir: Path | None = None
    ) -> None:
        self._lock = RLock()
        self._closed = False
        self._dll_directory = (
            os.add_dll_directory(str(native_dir)) if os.name == "nt" and native_dir else None
        )
        try:
            self._database = ladybug.Database(
                path,
                read_only=True,
                buffer_pool_size=buffer_mb * 1024 * 1024,
                max_num_threads=1,
            )
            try:
                self._connection = ladybug.Connection(self._database)
                rows = self._rows("MATCH (n:Manifest) RETURN n.id")
                if rows != [[catalog_hash(catalog)]]:
                    raise ValueError("Graph catalog mismatch")
                expected = sorted(
                    (edge.id, edge.left, edge.right) for edge in catalog.relations if edge.certified
                )
                actual = self._rows(
                    "MATCH (a:Node)-[r:Link]->(b:Node) WHERE r.kind = $kind "
                    "RETURN r.id, a.id, b.id",
                    {"kind": "join"},
                )
                if sorted(tuple(str(value) for value in row) for row in actual) != expected:
                    raise ValueError("Graph topology mismatch")
                dependencies = dependency_graph(catalog)
                lineage = self._rows(
                    "MATCH (a:Node)-[r:Link]->(b:Node) WHERE r.kind=$kind RETURN a.id,b.id",
                    {"kind": "lineage"},
                )
                if {tuple(str(value) for value in row) for row in lineage} != set(
                    dependencies.links
                ):
                    raise ValueError("Graph lineage mismatch")

            except BaseException:
                if hasattr(self, "_connection"):
                    self._connection.close()
                self._database.close()
                raise
        except Exception as error:
            if self._dll_directory is not None:
                self._dll_directory.close()
            raise Failure(
                "GRAPH_UNAVAILABLE", "The certified graph is unavailable.", "unavailable"
            ) from error

    @classmethod
    def build(
        cls, path: Path, catalog: Catalog, buffer_mb: int = 64, native_dir: Path | None = None
    ) -> "LadybugGraph":
        """Create a new private file transactionally; never overwrite an existing version."""
        path.parent.mkdir(parents=True, exist_ok=True)
        (path.parent / ".metadata-private").touch(exist_ok=True)
        if path.exists():
            return cls(path, catalog, buffer_mb, native_dir)
        # Exclusive reservation coordinates independent bootstrap/admin processes.
        reservation = path.with_suffix(".building")
        dll_directory = (
            os.add_dll_directory(str(native_dir)) if os.name == "nt" and native_dir else None
        )
        owned = False
        temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
        try:
            with reservation.open("x"):
                owned = True
                if path.exists():
                    return cls(path, catalog, buffer_mb, native_dir)
                database = ladybug.Database(
                    temporary,
                    buffer_pool_size=buffer_mb * 1024 * 1024,
                    max_num_threads=1,
                )
                try:
                    connection = ladybug.Connection(database)
                    try:
                        cls._populate(connection, catalog)
                    finally:
                        connection.close()
                finally:
                    database.close()
                with cls(temporary, catalog, buffer_mb, native_dir):
                    pass
                temporary.replace(path)
        except FileExistsError as error:
            remaining = max(0, (REQUEST_DEADLINE.get() or time.time() + 30) - time.time())
            deadline = time.monotonic() + min(30, remaining)
            while time.monotonic() < deadline:
                if path.exists():
                    return cls(path, catalog, buffer_mb, native_dir)
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
            if dll_directory is not None:
                dll_directory.close()
        return cls(path, catalog, buffer_mb, native_dir)

    @staticmethod
    def _populate(connection: ladybug.Connection, catalog: Catalog) -> None:
        def execute(query: str, values: dict[str, object] | None = None) -> None:
            result = connection.execute(query, values)
            for item in result if isinstance(result, list) else [result]:
                item.close()

        execute("CREATE NODE TABLE Node(id STRING, PRIMARY KEY(id))")
        execute("CREATE NODE TABLE Manifest(id STRING, PRIMARY KEY(id))")
        execute("CREATE REL TABLE Link(FROM Node TO Node, id STRING, kind STRING, pair STRING)")
        execute("BEGIN TRANSACTION")
        try:
            dependencies = dependency_graph(catalog)
            nodes = set(dependencies.nodes) | {table.id for table in catalog.tables}
            for node in sorted(nodes):
                execute("CREATE (:Node {id: $id})", {"id": node})
            for edge in catalog.relations:
                if edge.certified:
                    execute(
                        "MATCH (a:Node), (b:Node) WHERE a.id=$a AND b.id=$b "
                        "CREATE (a)-[:Link {id:$id, kind:$kind, pair:$pair}]->(b)",
                        {
                            "a": edge.left,
                            "b": edge.right,
                            "id": edge.id,
                            "kind": "join",
                            "pair": json.dumps([edge.left, edge.right]),
                        },
                    )
            for left, right in dependencies.links:
                execute(
                    "MATCH (a:Node), (b:Node) WHERE a.id=$a AND b.id=$b "
                    "CREATE (a)-[:Link {id:$id, kind:$kind, pair:$pair}]->(b)",
                    {
                        "a": left,
                        "b": right,
                        "id": left + ":" + right,
                        "kind": "lineage",
                        "pair": "",
                    },
                )
            execute("CREATE (:Manifest {id:$id})", {"id": catalog_hash(catalog)})
            execute("COMMIT")
        except BaseException:
            execute("ROLLBACK")
            raise
        execute("CHECKPOINT")

    def _rows(self, query: str, values: dict[str, object] | None = None) -> list[list[object]]:
        try:
            result = self._connection.execute(query, values)
        except Exception as error:
            logging.getLogger(__name__).error("graph_query_failed")
            raise Failure(
                "GRAPH_UNAVAILABLE", "The certified graph is unavailable.", "unavailable"
            ) from error
        if isinstance(result, list):
            for item in result:
                item.close()
            raise ValueError("Only one graph statement is allowed")
        try:
            rows: list[list[object]] = []
            while result.has_next():
                rows.append(result.get_next())
            return rows
        finally:
            result.close()

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
                    "MATCH (a:Node)-[r:Link]->(b:Node) "
                    "WHERE a.id IN $frontier AND r.kind=$kind AND r.pair IN $pairs "
                    "RETURN a.id, b.id ORDER BY a.id, b.id",
                    {"frontier": frontier, "kind": "join", "pairs": keys},
                )
                frontier = list[str]()
                for left, right in rows:
                    parent, node = str(left), str(right)
                    if node not in parents:
                        parents[node] = parent
                        frontier.append(node)
            return []

    def lineage(self, roots: set[str]) -> set[str]:
        """Reach all stored downstream consumers with bounded visited-node work."""
        with self._lock:
            self._check_open()
            known = {str(row[0]) for row in self._rows("MATCH (n:Node) RETURN n.id")}
            reached = roots & known
            frontier = sorted(reached)
            while frontier:
                rows = self._rows(
                    "MATCH (a:Node)-[r:Link]->(b:Node) "
                    "WHERE a.id IN $frontier AND r.kind=$kind RETURN DISTINCT b.id",
                    {"frontier": frontier, "kind": "lineage"},
                )
                frontier = sorted({str(row[0]) for row in rows} - reached)
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
                try:
                    self._connection.close()
                finally:
                    self._database.close()
                    if self._dll_directory is not None:
                        self._dll_directory.close()

    def __enter__(self) -> "LadybugGraph":
        return self

    def __exit__(self, *_error: object) -> None:
        self.close()
