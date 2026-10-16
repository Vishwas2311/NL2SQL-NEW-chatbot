"""Typed search evidence derived only from the certified semantic catalog."""

from typing import Literal

from nl2sql.domain import Catalog, FrozenModel, Principal

RecordKind = Literal[
    "domain",
    "table",
    "column",
    "dimension",
    "metric",
    "alias",
    "view",
    "relationship",
    "reporting_date",
    "grain",
    "business_term",
]


class SearchRecord(FrozenModel):
    """Searchable evidence carries its authorization dependencies, never new permissions."""

    id: str
    kind: RecordKind
    catalog_version: str
    parent_id: str | None = None
    related_ids: tuple[str, ...] = ()
    domain: str
    description: str
    provenance: str = "certified_semantic_catalog"
    approved: bool = True
    metric_scope: tuple[str, ...]
    embedding_text: str


class RetrievalCandidate(FrozenModel):
    """A bounded rank signal, not confidence that SQL is correct."""

    id: str
    kind: RecordKind
    score: float
    source: str
    parent_id: str | None = None
    related_ids: tuple[str, ...] = ()
    catalog_version: str
    metric_scope: tuple[str, ...]
    confidence_signals: tuple[str, ...] = ()


def schema_records(catalog: Catalog) -> tuple[SearchRecord, ...]:
    """Physical dictionary additions never enter this function until explicitly mapped/certified."""
    if not catalog.approved:
        raise ValueError("Search requires a certified catalog")
    records: dict[str, SearchRecord] = {}
    tables = {table.id: table for table in catalog.tables}

    def add(
        kind: RecordKind,
        key: str,
        text: str,
        metric: str,
        domain: str,
        parent: str | None = None,
        related: tuple[str, ...] = (),
    ) -> None:
        identity = kind + ":" + key
        old = records.get(identity)
        scope = tuple(sorted({metric, *(old.metric_scope if old else ())}))
        records[identity] = SearchRecord(
            id=identity,
            kind=kind,
            catalog_version=catalog.version,
            parent_id=parent,
            related_ids=related,
            domain=domain,
            description=text,
            metric_scope=scope,
            embedding_text=" ".join((kind, key.replace("_", " "), text)),
        )

    for metric in catalog.metrics:
        add("domain", metric.domain, metric.domain, metric.id, metric.domain)
        add(
            "metric",
            metric.id,
            " ".join((metric.label, *metric.aliases, metric.definition)),
            metric.id,
            metric.domain,
            "table:" + metric.table,
        )
        for alias in metric.aliases:
            add(
                "alias",
                metric.id + ":" + alias,
                alias,
                metric.id,
                metric.domain,
                "metric:" + metric.id,
            )
        add(
            "business_term",
            metric.id,
            metric.definition,
            metric.id,
            metric.domain,
            "metric:" + metric.id,
        )
        relevant = {metric.table: {metric.column}}
        for view in catalog.views:
            if metric.id not in view.metrics:
                continue
            add(
                "view",
                view.id,
                view.id.replace("_", " "),
                metric.id,
                metric.domain,
                "table:" + view.root,
                tuple("relationship:" + key for key in view.relationships),
            )
            add("grain", view.id, " ".join(view.grain), metric.id, metric.domain, "view:" + view.id)
            relevant.setdefault(view.root, set()).update(view.grain)
            if view.time_column:
                relevant[view.root].add(view.time_column)
                add(
                    "reporting_date",
                    view.id,
                    view.time_kind + " " + view.time_column,
                    metric.id,
                    metric.domain,
                    "view:" + view.id,
                )
            for dimension in catalog.dimensions:
                if dimension.id in view.dimensions:
                    relevant.setdefault(dimension.table, set()).add(dimension.column)
                    add(
                        "dimension",
                        dimension.id,
                        dimension.id,
                        metric.id,
                        metric.domain,
                        f"column:{dimension.table}.{dimension.column}",
                    )
            for relation in catalog.relations:
                if relation.id in view.relationships and relation.certified:
                    add(
                        "relationship",
                        relation.id,
                        relation.cardinality + " " + relation.temporal,
                        metric.id,
                        metric.domain,
                        "view:" + view.id,
                        ("table:" + relation.left, "table:" + relation.right),
                    )
                    for left, right in relation.pairs:
                        relevant.setdefault(relation.left, set()).add(left)
                        relevant.setdefault(relation.right, set()).add(right)
        for table_id, columns in relevant.items():
            source = tables[table_id]
            add(
                "table",
                table_id,
                source.description,
                metric.id,
                metric.domain,
                "domain:" + metric.domain,
            )
            for column in source.columns:
                if column.name in columns:
                    add(
                        "column",
                        f"{table_id}.{column.name}",
                        column.description,
                        metric.id,
                        metric.domain,
                        "table:" + table_id,
                    )
    return tuple(records[key] for key in sorted(records))


def authorized_records(
    records: tuple[SearchRecord, ...],
    principal: Principal,
) -> tuple[SearchRecord, ...]:
    """Remove hidden links as well as hidden records before context or vector exposure."""
    grants = set(principal.metrics)
    allowed = {record.id for record in records if grants.intersection(record.metric_scope)}
    return tuple(
        record.model_copy(
            update={
                "metric_scope": tuple(key for key in record.metric_scope if key in grants),
                "related_ids": tuple(key for key in record.related_ids if key in allowed),
                "parent_id": record.parent_id if record.parent_id in allowed else None,
            }
        )
        for record in records
        if record.id in allowed
    )
