"""Reconcile approved semantic mappings with discovered physical evidence."""

from nl2sql.application.catalog import validate_catalog
from nl2sql.domain.models import Catalog, Failure, FrozenModel, Table, view_policy
from nl2sql.domain.physical import PhysicalInventory, PhysicalObject


class Compatibility(FrozenModel):
    """A new physical column does not become a metric or an entitlement."""

    issues: tuple[str, ...]
    used_objects: tuple[str, ...]
    unmapped_objects: tuple[str, ...]


def physical_object(table: Table, inventory: PhysicalInventory) -> PhysicalObject | None:
    """The compatibility link is owner-qualified and case preserving."""
    owner = table.physical_owner or ("SYNTHETIC" if inventory.source_kind == "synthetic" else None)
    return next(
        (
            item
            for item in inventory.objects
            if item.owner == owner and item.name == (table.physical_name or table.id)
        ),
        None,
    )


def reconcile(catalog: Catalog, inventory: PhysicalInventory) -> Compatibility:
    """Fail closed on type, grain, key or policy uncertainty; retain an inventory regardless."""
    issues: list[str] = []
    try:
        # Structural preview is not certification; publication verifies signed reviews.
        validate_catalog(catalog.model_copy(update={"approved": True}))
    except (ValueError, LookupError, Failure) as error:
        return Compatibility(
            issues=("semantic_catalog_invalid:" + type(error).__name__,),
            used_objects=(),
            unmapped_objects=tuple(item.id for item in inventory.objects),
        )
    matched = {table.id: physical_object(table, inventory) for table in catalog.tables}
    used: set[str] = set()
    for table in catalog.tables:
        item = matched[table.id]
        if item is None:
            issues.append("object_missing:" + table.id)
            continue
        used.add(item.id)
        if item.verification != "verified_physical":
            issues.append("physical_evidence_incomplete:" + table.id)
        by_name = {column.name: column for column in item.columns}
        for column in table.columns:
            source = by_name.get(column.physical_name or column.name)
            if source is None:
                issues.append(f"column_missing:{table.id}.{column.name}")
                continue
            kind = source.data_type.upper()
            valid = (
                (
                    column.kind == "integer"
                    and (
                        kind == "INTEGER"
                        or (
                            kind == "NUMBER"
                            and source.scale == 0
                            and source.precision is not None
                            and source.precision <= 38
                        )
                    )
                )
                or (
                    column.kind == "decimal"
                    and kind == "NUMBER"
                    and source.precision is not None
                    and source.precision <= 38
                    and source.scale is not None
                    and -84 <= source.scale <= 127
                )
                or (
                    column.kind == "date"
                    and (
                        kind == "DATE" or (inventory.source_kind == "synthetic" and kind == "TEXT")
                    )
                )
                or (
                    column.kind == "text"
                    and kind in {"TEXT", "VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR"}
                )
            )
            if not valid:
                issues.append(f"column_type:{table.id}.{column.name}")
            if (column.precision is not None and source.precision != column.precision) or (
                column.scale is not None and source.scale != column.scale
            ):
                issues.append(f"column_precision_scale:{table.id}.{column.name}")
        names = {column.name: column.physical_name or column.name for column in table.columns}
        grain = {names[key] for key in table.grain}
        if not any(
            key.kind in {"primary", "unique"}
            and key.enabled
            and key.validated
            and set(key.columns) == grain
            for key in item.keys
        ):
            issues.append("grain_unverified:" + table.id)
    for relation in catalog.relations:
        source, target = matched[relation.left], matched[relation.right]
        if source is None or target is None:
            continue
        left = next(table for table in catalog.tables if table.id == relation.left)
        right = next(table for table in catalog.tables if table.id == relation.right)
        left_names = {column.name: column.physical_name or column.name for column in left.columns}
        right_names = {column.name: column.physical_name or column.name for column in right.columns}
        pairs = {(left_names[a], right_names[b]) for a, b in relation.pairs}
        physical = any(
            key.kind == "foreign"
            and key.enabled
            and key.validated
            and key.target == target.id
            and set(zip(key.columns, key.target_columns, strict=True)) == pairs
            and (relation.physical_key_id is None or relation.physical_key_id == key.id)
            for key in source.keys
        )
        if not physical and relation.logical_evidence is None:
            issues.append("relationship_unverified:" + relation.id)
        if relation.cardinality == "one_to_one" and not any(
            key.kind in {"primary", "unique"}
            and key.enabled
            and key.validated
            and set(key.columns) == {a for a, _ in pairs}
            for key in source.keys
        ):
            issues.append("one_to_one_unverified:" + relation.id)
    if inventory.source_kind == "oracle":
        if inventory.verification != "verified_physical":
            issues.append("live_oracle_reconciliation_required")
        if catalog.classification != "restricted":
            issues.append("oracle_classification_must_be_restricted")
        for view in catalog.views:
            if view.policy is None or not view_policy(view).evidence:
                issues.append("explicit_security_certification_required:" + view.id)
    return Compatibility(
        issues=tuple(sorted(set(issues))),
        used_objects=tuple(sorted(used)),
        unmapped_objects=tuple(
            sorted(item.id for item in inventory.objects if item.id not in used)
        ),
    )
