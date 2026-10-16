"""Join independent fact aggregates at certified customer grain, never raw fact rows."""

import sqlglot
from sqlglot import exp

from nl2sql.catalog import JoinGraph
from nl2sql.domain import (
    Catalog,
    CompiledQuery,
    Principal,
    ValidatedPlan,
    scope_values,
    view_policy,
)
from nl2sql.sql_types import infer_bind_types


def combine_query(
    components: tuple[CompiledQuery, ...],
    validated: ValidatedPlan,
    principal: Principal,
    catalog: Catalog,
) -> CompiledQuery:
    """Component policy filters run before preaggregation; outer policy is also mandatory."""
    plan = validated.plan
    dimensions = {item.id: item for item in catalog.dimensions}
    metrics = {item.id: item for item in catalog.metrics}
    view = next(item for item in catalog.views if item.id == plan.view_id)
    policy = view_policy(view)
    assert policy.tenant_column is not None and policy.scope_dimension is not None
    common = dimensions[view.common_key]
    scope = dimensions[policy.scope_dimension]
    selected: list[exp.Expr] = []
    for key in plan.dimensions:
        selected.append(
            exp.column(dimensions[key].column, table=dimensions[key].table, quoted=True).as_(
                key, quoted=True
            )
        )
    for key in plan.metrics:
        index = next(
            index
            for index, core in enumerate(components)
            if key in core.validated_plan.plan.metrics
        )
        value: exp.Expr = exp.Sum(this=exp.column(key, table=f"component_{index}", quoted=True))
        if metrics[key].aggregate == "count":
            value = exp.Coalesce(this=value, expressions=[exp.Literal.number(0)])
        selected.append(value.as_(key, quoted=True))
    query = exp.select(*selected).from_(view.root)
    targets = {dimensions[key].table for key in plan.dimensions} | {scope.table}
    for edge in JoinGraph(catalog).resolve(view, targets):
        query = query.join(
            edge.right,
            join_type="INNER",
            on=exp.and_(
                *(
                    exp.EQ(
                        this=exp.column(left, table=edge.left, quoted=True),
                        expression=exp.column(right, table=edge.right, quoted=True),
                    )
                    for left, right in edge.pairs
                )
            ),
        )
    binds: list[tuple[str, str | int]] = []
    present: list[exp.Expr] = []
    for index, core in enumerate(components):
        name = f"component_{index}"
        aggregate = sqlglot.parse_one(core.sql, read=core.dialect)
        aggregate.set("limit", None)
        aggregate.set("order", None)
        for placeholder in aggregate.find_all(exp.Placeholder):
            placeholder.set("this", f"{name}_{placeholder.name}")
        binds.extend((f"{name}_{key}", value) for key, value in core.binds)
        query = query.with_(name, as_=aggregate)
        query = query.join(
            name,
            join_type="LEFT",
            on=exp.EQ(
                this=exp.column(common.column, table=view.root, quoted=True),
                expression=exp.column(view.common_key, table=name, quoted=True),
            ),
        )
        present.append(
            exp.Not(
                this=exp.Is(
                    this=exp.column(view.common_key, table=name, quoted=True), expression=exp.Null()
                )
            )
        )
    binds.append(("outer_tenant", principal.tenant))
    policies: list[exp.Expr] = [
        exp.EQ(
            this=exp.column(policy.tenant_column, table=view.root, quoted=True),
            expression=exp.Placeholder(this="outer_tenant"),
        )
    ]
    region_values: list[exp.Expr] = []
    for index, region in enumerate(scope_values(policy, principal)):
        key = f"outer_region_{index}"
        binds.append((key, region))
        region_values.append(exp.Placeholder(this=key))
    policies.extend(
        (
            exp.In(
                this=exp.column(scope.column, table=scope.table, quoted=True),
                expressions=region_values,
            ),
            exp.or_(*present),
        )
    )
    if policy.status_column is not None:
        binds.append(("outer_status", view.mandatory_status))
        policies.append(
            exp.EQ(
                this=exp.column(policy.status_column, table=view.root, quoted=True),
                expression=exp.Placeholder(this="outer_status"),
            )
        )
    query = query.where(exp.and_(*policies))
    if plan.dimensions:
        query = query.group_by(
            *(
                exp.column(dimensions[key].column, table=dimensions[key].table, quoted=True)
                for key in plan.dimensions
            )
        )
    order = [
        exp.Ordered(
            this=exp.column(item.field, quoted=True),
            desc=item.direction == "desc",
            nulls_first=False,
        )
        for item in plan.sort
    ]
    order.extend(
        exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
        for key in plan.dimensions
        if key not in {item.field for item in plan.sort}
    )
    if order:
        query = query.order_by(*order)
    query = query.limit(plan.limit + 1)
    return CompiledQuery(
        sql=query.sql(dialect=components[0].dialect),
        dialect=components[0].dialect,
        binds=tuple(binds),
        bind_types=infer_bind_types(query, dict(binds), catalog),
        output=(*plan.dimensions, *plan.metrics),
        validated_plan=validated,
    )
