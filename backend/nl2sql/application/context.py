"""Assemble authorized planning context without inference or storage calls."""

import json

from nl2sql.application.ports import Candidate
from nl2sql.domain.models import Catalog, Failure, Principal, QueryPlan
from nl2sql.domain.search import SearchRecord, authorized_records, schema_records


def build_context(
    catalog: Catalog,
    principal: Principal,
    candidates: tuple[Candidate, ...],
    records: tuple[SearchRecord, ...] | None = None,
    max_bytes: int = 64_000,
) -> str:
    """Only approved, authorized semantic records; descriptions remain untrusted data."""
    ids = {candidate.metric_id for candidate in candidates} & set(principal.metrics)
    metrics = [
        metric.model_dump(
            mode="json",
            include={
                "id",
                "label",
                "definition",
                "temporal",
                "unit",
                "scale",
                "decimal_places",
                "table",
                "column",
                "aggregate",
            },
        )
        for metric in catalog.metrics
        if metric.id in ids
    ]
    views = [
        view.model_dump(
            mode="json",
            include={
                "id",
                "version",
                "dimensions",
                "grain",
                "time_column",
                "time_kind",
                "root",
                "relationships",
            },
        )
        | {
            "metrics": sorted(set(view.metrics) & ids),
            "operation": "combine" if view.components else "aggregate",
        }
        for view in catalog.views
        if ids.intersection(view.metrics)
    ]
    selected = authorized_records(
        records if records is not None else schema_records(catalog),
        principal.model_copy(update={"metrics": tuple(sorted(ids))}),
    )
    visible = {record.id for record in selected}
    context: dict[str, object] = {
        "catalog_version": catalog.version,
        "classification": catalog.classification,
        "metrics": metrics,
        "views": views,
        "default_as_of": catalog.default_as_of.isoformat(),
        "fiscal_start_month": catalog.fiscal_start_month,
        "schema": QueryPlan.model_json_schema(),
        "dimensions": [
            item.model_dump() for item in catalog.dimensions if "dimension:" + item.id in visible
        ],
        "relationships": [
            item.model_dump(include={"id", "left", "right", "pairs", "cardinality", "temporal"})
            for item in catalog.relations
            if "relationship:" + item.id in visible
        ],
        "schema_records": [],
        "truncated": False,
    }

    def serialize() -> str:
        return json.dumps(context, separators=(",", ":"), sort_keys=True)

    encoded_bytes = len(serialize().encode())
    if encoded_bytes > max_bytes:
        raise Failure("MODEL_CONTEXT_BUDGET", "Certified planning context exceeds its budget.", 422)
    evidence: list[dict[str, object]] = []
    context["schema_records"] = evidence
    for record in selected:
        item: dict[str, object] = record.model_dump(exclude={"embedding_text", "metric_scope"})
        item["description"] = record.description[:512]
        # Count each entry once instead of serializing the full schema repeatedly.
        entry_bytes = len(json.dumps(item, separators=(",", ":"), sort_keys=True).encode())
        addition = entry_bytes + int(bool(evidence))
        if encoded_bytes + addition > max_bytes - 16:
            context["truncated"] = True
            break
        evidence.append(item)
        encoded_bytes += addition
    return serialize()
