"""Deterministic analytic ranking over an already approved aggregate grain."""

import sqlglot
from sqlglot import exp

from nl2sql.domain import Catalog, CompiledQuery, ValidatedPlan
from nl2sql.sql_types import infer_bind_types


def rank_query(core: CompiledQuery, validated: ValidatedPlan, catalog: Catalog) -> CompiledQuery:
    """Aggregate before ranking; apply rank and global row bounds only afterward."""
    rank = validated.plan.ranking
    assert rank is not None
    aggregate = sqlglot.parse_one(core.sql, read=core.dialect)
    aggregate.set("order", None)
    aggregate.set("limit", None)
    order = [
        exp.Ordered(
            this=exp.column(rank.metric, quoted=True),
            desc=rank.direction == "desc",
            nulls_first=False,
        )
    ]
    if rank.method == "row_number":
        order.extend(
            exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
            for key in validated.plan.dimensions
            if key not in rank.partition_by
        )
    window = exp.Window(
        this=exp.RowNumber() if rank.method == "row_number" else exp.DenseRank(),
        partition_by=[exp.column(key, quoted=True) for key in rank.partition_by],
        order=exp.Order(expressions=order),
    )
    fields = [exp.column(key, quoted=True) for key in core.output]
    ranked = exp.select(*fields, window.as_("rank_value", quoted=True)).from_("approved_aggregate")
    result_order = (
        *rank.partition_by,
        "rank_value",
        *(key for key in validated.plan.dimensions if key not in rank.partition_by),
    )
    query = (
        exp.select(*(exp.column(key, quoted=True) for key in (*core.output, "rank_value")))
        .from_("approved_ranked")
        .where(
            exp.LTE(
                this=exp.column("rank_value", quoted=True),
                expression=exp.Placeholder(this="rank_limit"),
            )
        )
        .order_by(
            *(
                exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
                for key in result_order
            )
        )
        .limit(validated.plan.limit + 1)
        .with_("approved_aggregate", as_=aggregate)
        .with_("approved_ranked", as_=ranked)
    )
    binds = (*core.binds, ("rank_limit", rank.top_n))
    return core.model_copy(
        update={
            "sql": query.sql(dialect=core.dialect),
            "binds": binds,
            "bind_types": infer_bind_types(query, dict(binds), catalog),
            "validated_plan": validated,
            "output": (*core.output, "rank_value"),
        }
    )
