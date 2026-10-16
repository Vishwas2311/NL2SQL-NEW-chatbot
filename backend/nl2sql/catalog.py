"""Validated catalog ingestion, atomic publication and verified relationship graph."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Protocol, cast

import networkx as nx

from nl2sql.domain import Catalog, Dimension, Failure, Relation, SemanticView, view_policy
from nl2sql.telemetry import measured


class _PathFinder(Protocol):
    """The official dispatcher stubs leave backend kwargs unknown; only three arguments are used."""

    def __call__(self, graph: nx.Graph[str], source: str, target: str) -> list[str]: ...


_shortest_path = cast(_PathFinder, vars(nx)["shortest_path"])


def digest(value: str) -> str:
    """Stable non-secret provenance fingerprint."""
    return hashlib.sha256(value.encode()).hexdigest()


class JoinGraph:
    """Traverse only certified, unambiguous, grain-preserving directed edges."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        # NetworkX's official stubs are generic; Pylint inspects the runtime-only class.
        self.graph: nx.DiGraph[str] = nx.DiGraph()  # pylint: disable=unsubscriptable-object
        for table in catalog.tables:
            self.graph.add_node(table.id, grain=table.grain, version=catalog.version)
        for relation in catalog.relations:
            if relation.certified:
                self.graph.add_edge(
                    relation.left,
                    relation.right,
                    relationship=relation.id,
                    pairs=relation.pairs,
                    cardinality=relation.cardinality,
                    temporal=relation.temporal,
                    evidence=relation.evidence,
                    version=catalog.version,
                )

    @measured("graph_ms")
    def resolve(
        self, view: SemanticView, targets: set[str], historical: bool = False
    ) -> tuple[Relation, ...]:
        """Reject alternative paths rather than select the shortest by accident."""
        allowed = {
            edge.id: edge
            for edge in self.catalog.relations
            if edge.id in view.relationships and edge.certified
        }
        graph = self.graph.edge_subgraph([(edge.left, edge.right) for edge in allowed.values()])
        chosen: dict[str, Relation] = {}
        for target in sorted(targets - {view.root}):
            if view.root not in graph or target not in graph:
                raise Failure("INVALID_JOIN", "The approved relationship is unavailable.")
            try:
                path = _shortest_path(graph, view.root, target)
            except nx.NetworkXNoPath as error:
                raise Failure("AMBIGUOUS_JOIN", "The relationship needs clarification.") from error
            if len(path) > 7:
                raise Failure("INVALID_JOIN", "The approved relationship exceeds its edge budget.")
            if _alternative_path(graph, path):
                raise Failure("AMBIGUOUS_JOIN", "The relationship needs clarification.")
            for left, right in zip(path, path[1:], strict=False):
                matching = [
                    edge for edge in allowed.values() if edge.left == left and edge.right == right
                ]
                if len(matching) != 1:
                    raise Failure("AMBIGUOUS_JOIN", "The relationship needs clarification.")
                edge = matching[0]
                if historical and edge.temporal == "current_only":
                    raise Failure(
                        "HISTORICAL_JOIN",
                        "Current-only attributes cannot answer historical questions.",
                    )
                if edge.cardinality not in ("many_to_one", "one_to_one"):
                    raise Failure("UNSAFE_FANOUT", "This combination has incompatible data grain.")
                chosen[edge.id] = edge
        # Preserve dependency order rather than alphabetic edge IDs.
        ordered: list[Relation] = []
        seen = {view.root}
        while chosen:
            ready = [edge for edge in chosen.values() if edge.left in seen]
            if not ready:
                raise Failure("INVALID_JOIN", "The relationship cannot be resolved.")
            for edge in ready:
                ordered.append(edge)
                seen.add(edge.right)
                del chosen[edge.id]
        return tuple(ordered)


def _alternative_path(graph: nx.DiGraph[str], path: list[str]) -> bool:
    """At most six bounded breadth-first searches replace exponential simple-path enumeration."""
    for left, right in zip(path, path[1:], strict=False):
        alternate = nx.restricted_view(graph, [], [(left, right)])
        try:
            route = _shortest_path(alternate, path[0], path[-1])
        except nx.NetworkXNoPath:
            continue
        if len(route) <= 7:
            return True
    return False


def validate_catalog(catalog: Catalog, connection: sqlite3.Connection | None = None) -> None:
    """Quarantine malformed mappings before publishing any derived resource."""
    groups = (catalog.tables, catalog.relations, catalog.dimensions, catalog.metrics, catalog.views)
    for group in groups:
        ids = [entry.id for entry in group]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate catalog IDs")
    if not catalog.approved or catalog.effective_from > catalog.effective_to:
        raise ValueError("Catalog approval or effective interval is invalid")
    tables = {table.id: table for table in catalog.tables}
    columns = {table.id: {col.name: col.kind for col in table.columns} for table in catalog.tables}
    sources = [(table.physical_owner, table.physical_name or table.id) for table in catalog.tables]
    if len(set(sources)) != len(sources):
        raise ValueError("Duplicate physical table mapping")
    if any(
        table.id in {"approved_aggregate", "approved_ranked"} or table.id.startswith("component_")
        for table in catalog.tables
    ):
        raise ValueError("Table ID collides with a compiler-owned CTE")
    for table in catalog.tables:
        if not set(table.grain) <= columns[table.id].keys() or not table.grain:
            raise ValueError("Missing table grain")
        if len(columns[table.id]) != len(table.columns):
            raise ValueError("Duplicate column")
        physical_columns = [column.physical_name or column.name for column in table.columns]
        if len(set(physical_columns)) != len(physical_columns) or (
            table.tenant_column is not None and columns[table.id].get(table.tenant_column) != "text"
        ):
            raise ValueError("Invalid physical column or tenant mapping")
        if connection is not None:
            physical = {
                str(row[1]): str(row[2]).upper()
                for row in connection.execute(f'PRAGMA table_info("{table.id}")')
            }
            for name, kind in columns[table.id].items():
                expected = "INTEGER" if kind == "integer" else "TEXT"
                if physical.get(name) != expected:
                    raise ValueError("Physical schema type/mapping drift")
    for item in (*catalog.dimensions, *catalog.metrics):
        if item.table not in columns or item.column not in columns[item.table]:
            raise ValueError("Missing physical mapping")
        kind = columns[item.table][item.column]
        if isinstance(item, Dimension):
            if item.kind != kind:
                raise ValueError("Dimension type does not match its physical column")
        elif item.aggregate != "count" and kind not in {"integer", "decimal"}:
            raise ValueError("Numeric aggregates require integer storage columns")
    for edge in catalog.relations:
        if not edge.pairs or edge.left not in tables or edge.right not in tables:
            raise ValueError("Missing relationship endpoint")
        if len(set(edge.pairs)) != len(edge.pairs):
            raise ValueError("Duplicate relationship pair")
        for left, right in edge.pairs:
            if left not in columns[edge.left] or right not in columns[edge.right]:
                raise ValueError("Missing composite key column")
            if columns[edge.left][left] != columns[edge.right][right]:
                raise ValueError("Join type mismatch")
        if edge.cardinality in ("many_to_one", "one_to_one"):
            if set(right for _, right in edge.pairs) != set(tables[edge.right].grain):
                raise ValueError("Incomplete composite target key")
        left_tenant, right_tenant = (
            tables[edge.left].tenant_column,
            tables[edge.right].tenant_column,
        )
        if (
            left_tenant is not None
            and right_tenant is not None
            and (left_tenant, right_tenant) not in edge.pairs
        ):
            raise ValueError("Missing certified tenant partition pair")
        evidence = edge.logical_evidence
        if evidence is not None and any(
            (
                edge.physical_key_id is not None,
                not edge.certified,
                edge.cardinality not in {"many_to_one", "one_to_one"},
                evidence.effective_catalog_version != catalog.version,
                evidence.source_grain != tables[edge.left].grain,
                evidence.target_grain != tables[edge.right].grain,
                evidence.column_types
                != tuple((columns[edge.left][a], columns[edge.right][b]) for a, b in edge.pairs),
                not set(evidence.partition_pairs) <= set(edge.pairs),
                (
                    left_tenant is not None
                    and right_tenant is not None
                    and (left_tenant, right_tenant) not in evidence.partition_pairs
                ),
            )
        ):
            raise ValueError("Logical join certification contract mismatch")
    _validate_metric_dependencies(catalog)
    _validate_views(catalog)
    _validate_entities_and_templates(catalog)


class CatalogStore:
    """Atomically publish complete immutable snapshots; failed candidates leave old state."""

    def __init__(self, path: Path, expected_digest: str) -> None:
        self.path = path
        self.expected_digest = expected_digest
        self._lock = Lock()
        self._active: Catalog | None = None

    def load(self, connection: sqlite3.Connection | None = None) -> Catalog:
        """Require an externally pinned digest, never trust a file's own checksum."""
        payload = self.path.read_text(encoding="utf-8")
        if digest(payload) != self.expected_digest:
            raise ValueError("Catalog digest does not match approved pin")
        candidate = Catalog.model_validate_json(payload)
        validate_catalog(candidate, connection)
        with self._lock:
            self._active = candidate
        return candidate

    def snapshot(self) -> Catalog:
        """Pin the current snapshot for the entire request."""
        with self._lock:
            if self._active is None:
                raise Failure("CATALOG_UNAVAILABLE", "The catalog is unavailable.", 503)
            return self._active

    @classmethod
    def from_snapshot(cls, catalog: Catalog) -> CatalogStore:
        """Runtime bundles call this only after lifecycle/signature verification."""
        validate_catalog(catalog)
        store = cls(Path("<verified-runtime-bundle>"), catalog_hash(catalog))
        store._active = catalog
        return store


def catalog_hash(catalog: Catalog) -> str:
    """Canonical snapshot hash independent of file whitespace."""
    return digest(json.dumps(catalog.model_dump(mode="json"), sort_keys=True))


def _validate_metric_dependencies(catalog: Catalog) -> None:
    metrics = {metric.id: metric for metric in catalog.metrics}
    dependencies: nx.DiGraph[str] = nx.DiGraph()  # pylint: disable=unsubscriptable-object
    dependencies.add_nodes_from(metrics)
    for metric in catalog.metrics:
        if metric.expression is not None:
            for key in (metric.expression.numerator, metric.expression.denominator):
                source = metrics.get(key)
                if (
                    source is None
                    or source.table != metric.table
                    or source.aggregate != "sum"
                    or source.expression is not None
                    or source.temporal != metric.temporal
                ):
                    raise ValueError("Derived metrics require mapped same-grain primitive sums")
                dependencies.add_edge(metric.id, key)
            if metric.expression.kind == "ratio" and metric.unit != "percent":
                raise ValueError("Ratio metrics require an explicit percentage unit")
            sources = [
                metrics[key] for key in (metric.expression.numerator, metric.expression.denominator)
            ]
            if len({(source.unit, source.scale) for source in sources}) != 1:
                raise ValueError("Derived operands require compatible units and scales")
            if (
                metric.aggregate != "sum"
                or (
                    metric.expression.kind == "difference"
                    and (metric.unit, metric.scale) != (sources[0].unit, sources[0].scale)
                )
                or (metric.expression.kind == "ratio" and metric.scale != 1)
            ):
                raise ValueError("Derived metric output unit/scale is incompatible")
    if not nx.is_directed_acyclic_graph(dependencies):
        raise ValueError("Metric dependency cycle")


def _validate_composite_view(view: SemanticView, catalog: Catalog) -> None:
    if not view.components:
        return
    components = [candidate for candidate in catalog.views if candidate.id in view.components]
    if len(components) != len(view.components) or any(item.components for item in components):
        raise ValueError("Invalid composite view components")
    dimension = next((item for item in catalog.dimensions if item.id == view.common_key), None)
    if dimension is None or dimension.table != view.root or view.common_key not in view.dimensions:
        raise ValueError("Composite views require an explicit certified common grain")
    policy = view_policy(view)
    root = next(table for table in catalog.tables if table.id == view.root)
    if set(root.grain) != {dimension.column, policy.tenant_column}:
        raise ValueError("Composite root must be unique at tenant/common-key grain")
    if any(
        view_policy(item).scope_claim != policy.scope_claim
        or view_policy(item).strategy != "tenant_scope"
        for item in components
    ):
        raise ValueError("Composite component policies are incompatible")
    if any(sum(key in item.metrics for item in components) != 1 for key in view.metrics):
        raise ValueError("Composite metrics must map to exactly one component")
    if any(not set(view.dimensions) <= set(item.dimensions) for item in components):
        raise ValueError("Composite dimensions must exist in every component")


def _validate_entities_and_templates(catalog: Catalog) -> None:
    """Keep lookup scopes and saved reports tied to certified catalog mappings."""
    columns = {table.id: {col.name: col.kind for col in table.columns} for table in catalog.tables}
    dimensions = {item.id: item for item in catalog.dimensions}
    for entity in catalog.entities:
        if entity.table not in columns:
            raise ValueError("Missing entity source")
        required = {
            entity.key_column,
            entity.tenant_column,
            entity.scope_column,
            *entity.label_columns,
        }
        if not required <= columns[entity.table].keys():
            raise ValueError("Missing entity scope/key mapping")
        canonical = dimensions.get(entity.canonical_field)
        if canonical is None or (canonical.table, canonical.column) != (
            entity.table,
            entity.key_column,
        ):
            raise ValueError("Entity identifier dimension must map to its exact key")
        if columns[entity.table][entity.key_column] not in {"text", "integer"} or any(
            columns[entity.table][name] != "text"
            for name in (*entity.label_columns, entity.tenant_column, entity.scope_column)
        ):
            raise ValueError("Entity lookup requires typed keys and textual labels/scope")
    template_ids = [item.id for item in catalog.templates]
    questions = [
        " ".join(re.findall(r"[a-z0-9]+", item.question.casefold())) for item in catalog.templates
    ]
    if (
        len(set(template_ids)) != len(template_ids)
        or len(set(questions)) != len(questions)
        or any(not value for value in questions)
    ):
        raise ValueError("Duplicate or empty certified template")
    for template in catalog.templates:
        view = next((item for item in catalog.views if item.id == template.plan.view_id), None)
        if (
            view is None
            or template.plan.catalog_version != catalog.version
            or template.plan.view_version != view.version
            or not set(template.plan.metrics) <= set(view.metrics)
            or not set(template.plan.dimensions) <= set(view.dimensions)
        ):
            raise ValueError("Invalid certified template mapping")


def _validate_views(catalog: Catalog) -> None:
    """Certify view roots, time roles, policy fields and composite grains."""
    tables = {table.id: table for table in catalog.tables}
    columns = {table.id: {col.name: col.kind for col in table.columns} for table in catalog.tables}
    metrics = {item.id: item for item in catalog.metrics}
    dimensions = {item.id: item for item in catalog.dimensions}
    edges = {item.id for item in catalog.relations if item.certified}
    graph = JoinGraph(catalog)
    for view in catalog.views:
        if not view.certified or not view.evidence or view.root not in tables:
            raise ValueError("Uncertified or unmapped view")
        if not set(view.metrics) <= metrics.keys() or not set(view.dimensions) <= dimensions.keys():
            raise ValueError("Missing semantic dependency")
        if not set(view.relationships) <= edges:
            raise ValueError("Unverified relationship")
        if view.grain != tables[view.root].grain:
            raise ValueError("Incorrect view grain")
        if not view.components and any(metrics[key].table != view.root for key in view.metrics):
            raise ValueError("Mixed fact grains")
        if view.time_column is not None and columns[view.root].get(view.time_column) != "date":
            raise ValueError("Missing snapshot date role")
        policy = view_policy(view)
        if not policy.evidence:
            raise ValueError("Missing policy certification")
        if policy.strategy == "tenant_scope" and (
            policy.tenant_column not in columns[view.root]
            or policy.scope_dimension not in dimensions
        ):
            raise ValueError("Missing mandatory policy fields")
        if policy.status_column is not None and policy.status_column not in columns[view.root]:
            raise ValueError("Missing mandatory status mapping")
        graph.resolve(view, {dimensions[key].table for key in view.dimensions})
        _validate_composite_view(view, catalog)
