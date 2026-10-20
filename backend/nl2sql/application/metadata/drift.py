"""Normalized schema differences and transitive impact; rename guesses confer no authority."""

from __future__ import annotations

import json

import networkx as nx

from nl2sql.application.metadata.certification import physical_object
from nl2sql.domain.fingerprints import catalog_hash, digest
from nl2sql.domain.metadata import ChangeClass, ChangeImpact, SchemaChange
from nl2sql.domain.models import Catalog, Metric, Principal, view_policy
from nl2sql.domain.physical import PhysicalInventory, inventory_digest


def schema_changes(
    before: PhysicalInventory | None, after: PhysicalInventory
) -> tuple[SchemaChange, ...]:
    """Daily rows are deliberately absent from fingerprints."""
    if before is not None and inventory_digest(before) == inventory_digest(after):
        return ()
    old = {item.id: item for item in before.objects} if before else {}
    new = {item.id: item for item in after.objects}
    result: list[SchemaChange] = []
    for key in sorted(old.keys() | new.keys()):
        if key not in old or key not in new:
            result.append(
                SchemaChange(
                    kind="object_added" if key in new else "object_removed",
                    classification="approval_required_addition"
                    if key in new
                    else "breaking_physical",
                    object_id=key,
                )
            )
            continue
        left, right = old[key], new[key]
        if left.kind != right.kind or left.verification != right.verification:
            result.append(
                SchemaChange(
                    kind="object_contract", classification="breaking_physical", object_id=key
                )
            )
        a, b = {col.name: col for col in left.columns}, {col.name: col for col in right.columns}
        for name in sorted(a.keys() | b.keys()):
            if name not in a or name not in b:
                result.append(
                    SchemaChange(
                        kind="column_added" if name in b else "column_removed",
                        classification="compatible_physical_addition"
                        if name in b
                        else "breaking_physical",
                        object_id=key,
                        column=name,
                    )
                )
            elif a[name] != b[name]:
                metadata = a[name].model_copy(update={"comment": b[name].comment}) == b[name]
                result.append(
                    SchemaChange(
                        kind="column_comment" if metadata else "column_contract",
                        classification="metadata_only" if metadata else "breaking_physical",
                        object_id=key,
                        column=name,
                    )
                )
        keys_a, keys_b = (
            {item.id: item for item in left.keys},
            {item.id: item for item in right.keys},
        )
        for name in sorted(keys_a.keys() | keys_b.keys()):
            if keys_a.get(name) != keys_b.get(name):
                result.append(
                    SchemaChange(
                        kind="key_added" if name not in keys_a else "key_changed",
                        classification="approval_required_addition"
                        if name not in keys_a
                        else "breaking_physical",
                        object_id=key,
                    )
                )
        if (
            left.dependencies != right.dependencies
            or left.definition_digest != right.definition_digest
        ):
            result.append(
                SchemaChange(
                    kind="definition_or_dependency",
                    classification="breaking_physical",
                    object_id=key,
                )
            )
        if (
            left.comment != right.comment
            or left.indexes != right.indexes
            or left.last_ddl_at != right.last_ddl_at
        ):
            result.append(
                SchemaChange(kind="object_metadata", classification="metadata_only", object_id=key)
            )
    removed = [item for key, item in old.items() if key not in new]
    added = [item for key, item in new.items() if key not in old]
    if any(
        tuple((col.name, col.data_type) for col in a.columns)
        == tuple((col.name, col.data_type) for col in b.columns)
        for a in removed
        for b in added
    ):
        result.append(SchemaChange(kind="potential_rename_unverified", classification="unknown"))
    if before is not None and (
        before.owners != after.owners
        or before.source_id != after.source_id
        or before.classification != after.classification
        or before.verification != after.verification
    ):
        result.append(SchemaChange(kind="source_scope", classification="security_sensitive"))
    return tuple(result)


def policy_digest(catalog: Catalog) -> str:
    """Rollback cannot restore an older policy strategy, partition or entity scope."""
    return digest(
        json.dumps(
            {
                "version": catalog.policy_version,
                "views": [
                    (view.id, view_policy(view).model_dump(), view.mandatory_status)
                    for view in catalog.views
                ],
                "tenants": [
                    (
                        table.id,
                        table.tenant_column,
                        table.physical_owner,
                        table.physical_name,
                        [(column.name, column.physical_name) for column in table.columns],
                    )
                    for table in catalog.tables
                ],
                "entities": [item.model_dump() for item in catalog.entities],
                "partitions": [(item.id, item.pairs) for item in catalog.relations],
            },
            sort_keys=True,
        )
    )


def semantic_changes(
    before: Catalog | None,
    after: Catalog | None,
    old_grants: tuple[Principal, ...],
    new_grants: tuple[Principal, ...],
) -> tuple[SchemaChange, ...]:
    """A synonym edit and a permission edit have different operational consequences."""
    result: list[SchemaChange] = []
    if before is not None and after is not None and catalog_hash(before) != catalog_hash(after):
        for kind, old_items, new_items in (
            ("metrics", before.metrics, after.metrics),
            ("dimensions", before.dimensions, after.dimensions),
            ("views", before.views, after.views),
            ("relations", before.relations, after.relations),
            ("tables", before.tables, after.tables),
        ):
            old = {item.id: item for item in old_items}
            new = {item.id: item for item in new_items}
            for key in sorted(old.keys() | new.keys()):
                if old.get(key) != new.get(key):
                    classification: ChangeClass = "breaking_semantic"
                    if key not in old:
                        classification = "approval_required_addition"
                    elif (
                        isinstance(old.get(key), Metric)
                        and isinstance(new.get(key), Metric)
                        and old[key].model_copy(
                            update={
                                field: getattr(new[key], field)
                                for field in ("aliases", "label", "definition")
                            }
                        )
                        == new[key]
                    ):
                        classification = "metadata_only"
                    result.append(
                        SchemaChange(
                            kind="semantic_" + kind, classification=classification, semantic_id=key
                        )
                    )
        fields = (
            "version",
            "default_as_of",
            "effective_from",
            "effective_to",
            "fiscal_start_month",
            "templates",
        )
        if any(getattr(before, key) != getattr(after, key) for key in fields):
            result.append(SchemaChange(kind="catalog_contract", classification="breaking_semantic"))
        if policy_digest(before) != policy_digest(after):
            result.append(SchemaChange(kind="policy_mapping", classification="security_sensitive"))
    if old_grants != new_grants:
        result.append(SchemaChange(kind="access_grants", classification="security_sensitive"))
    return tuple(result)


def dependency_graph(catalog: Catalog) -> nx.DiGraph[str]:
    """Physical source -> expression -> view -> search/compiler/saved-plan consumers."""
    graph: nx.DiGraph[str] = nx.DiGraph()  # pylint: disable=unsubscriptable-object
    for table in catalog.tables:
        for column in table.columns:
            graph.add_edge("table:" + table.id, f"column:{table.id}.{column.name}")
    for metric in catalog.metrics:
        graph.add_edge(f"column:{metric.table}.{metric.column}", "metric:" + metric.id)
        if metric.expression is not None:
            for key in (metric.expression.numerator, metric.expression.denominator):
                graph.add_edge("metric:" + key, "metric:" + metric.id)
        graph.add_edge("metric:" + metric.id, "retrieval:" + metric.id)
    for dimension in catalog.dimensions:
        graph.add_edge(f"column:{dimension.table}.{dimension.column}", "dimension:" + dimension.id)
    for edge in catalog.relations:
        for a, b in edge.pairs:
            graph.add_edge(f"column:{edge.left}.{a}", "relationship:" + edge.id)
            graph.add_edge(f"column:{edge.right}.{b}", "relationship:" + edge.id)
    for view in catalog.views:
        graph.add_edge("table:" + view.root, "view:" + view.id)
        if view.time_column is not None:
            graph.add_edge(f"column:{view.root}.{view.time_column}", "view:" + view.id)
        for kind, keys in (
            ("metric", view.metrics),
            ("dimension", view.dimensions),
            ("relationship", view.relationships),
            ("view", view.components),
        ):
            for key in keys:
                graph.add_edge(kind + ":" + key, "view:" + view.id)
        policy = view_policy(view)
        if policy.tenant_column is not None:
            graph.add_edge(f"column:{view.root}.{policy.tenant_column}", "policy:" + view.id)
        if policy.scope_dimension is not None:
            graph.add_edge("dimension:" + policy.scope_dimension, "policy:" + view.id)
        if policy.status_column is not None:
            graph.add_edge(f"column:{view.root}.{policy.status_column}", "policy:" + view.id)
        graph.add_edge("policy:" + view.id, "view:" + view.id)
        for consumer in ("compiler", "saved_plan"):
            graph.add_edge("view:" + view.id, consumer + ":" + view.id)
    return graph


def analyze_impact(
    changes: tuple[SchemaChange, ...], catalog: Catalog | None, inventory: PhysicalInventory | None
) -> ChangeImpact:
    """Use old mappings to identify broken dependencies, including removed objects."""
    if catalog is None or inventory is None:
        return ChangeImpact(changes=changes, approval_required=bool(changes))
    graph = dependency_graph(catalog)
    affected: set[str] = set()
    blocked: set[str] = set()
    mapping = {
        item.id: table
        for table in catalog.tables
        if (item := physical_object(table, inventory)) is not None
    }
    for item in inventory.objects:
        if item.id in mapping:
            for dependency in item.dependencies:
                if dependency in mapping:
                    graph.add_edge(
                        "table:" + mapping[dependency].id, "table:" + mapping[item.id].id
                    )
    for change in changes:
        roots: set[str] = set()
        table = mapping.get(change.object_id or "")
        if table is not None:
            if change.column is None:
                roots.add("table:" + table.id)
            else:
                roots.update(
                    f"column:{table.id}.{column.name}"
                    for column in table.columns
                    if (column.physical_name or column.name) == change.column
                )
        if change.semantic_id is not None:
            kind = {
                "semantic_metrics": "metric",
                "semantic_dimensions": "dimension",
                "semantic_views": "view",
                "semantic_relations": "relationship",
                "semantic_tables": "table",
            }.get(change.kind)
            if kind is not None:
                roots.add(kind + ":" + change.semantic_id)
        if change.kind in {"policy_mapping", "source_scope", "access_grants", "catalog_contract"}:
            roots.update("view:" + view.id for view in catalog.views)
        reached = _reachable(graph, roots)
        affected.update(reached)
        if (
            change.classification in {"breaking_physical", "security_sensitive"}
            and change.kind != "access_grants"
        ):
            blocked.update(node.split(":", 1)[1] for node in reached if node.startswith("view:"))

    def selected(kind: str) -> tuple[str, ...]:
        return tuple(
            sorted(node.split(":", 1)[1] for node in affected if node.startswith(kind + ":"))
        )

    return ChangeImpact(
        changes=changes,
        metrics=selected("metric"),
        dimensions=selected("dimension"),
        views=selected("view"),
        relationships=selected("relationship"),
        retrieval=selected("retrieval"),
        compiler=selected("compiler"),
        policies=selected("policy"),
        saved_plans=selected("saved_plan"),
        blocked_views=tuple(sorted(blocked)),
        approval_required=bool(changes),
        revalidation=("catalog", "graph", "compiler_goldens", "authorization", "api_contracts")
        if changes
        else (),
    )


def _reachable(graph: nx.DiGraph[str], roots: set[str]) -> set[str]:
    """Bound work by visited nodes, including when dependencies share many paths."""
    reached = {node for node in roots if node in graph}
    pending = list(reached)
    while pending:
        node = pending.pop()
        if node not in graph:
            continue
        for target in graph.successors(node):
            if target not in reached:
                reached.add(target)
                pending.append(target)
    return reached
