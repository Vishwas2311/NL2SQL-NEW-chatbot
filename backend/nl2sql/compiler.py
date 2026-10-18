"""Typed relational lowering and deterministic SQLGlot AST rendering."""

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal

import sqlglot
from sqlglot import exp

from nl2sql.composite import combine_query
from nl2sql.domain import (
    Bind,
    Catalog,
    CompiledQuery,
    DateRange,
    Failure,
    FilterGroup,
    Period,
    Predicate,
    Principal,
    ValidatedPlan,
    scope_values,
    view_policy,
)
from nl2sql.physical_sql import oracle_identifiers
from nl2sql.planning import PlanValidator, component_plans
from nl2sql.ranking import rank_query
from nl2sql.sql_types import infer_bind_types


@dataclass(frozen=True)
class RelationalIR:
    """Minimal relational IR retaining certified source, joins, grain and limit."""

    root: str
    joins: tuple[str, ...]
    group: tuple[str, ...]
    measures: tuple[str, ...]
    limit: int
    preaggregate: bool


def column(table: str, name: str) -> exp.Column:
    """Identifiers originate exclusively from certified mappings."""
    return exp.column(name, table=table, quoted=True)


class Compiler:
    """Lower approved fields, relationship predicates and typed filter values."""

    def __init__(
        self, catalog: Catalog, validator: PlanValidator | None = None, bundle_version: str = ""
    ) -> None:
        self.catalog = catalog
        self.validator = validator or PlanValidator(catalog)
        self.bundle_version = bundle_version

    def compile(
        self,
        validated: ValidatedPlan,
        principal: Principal,
        dialect: Literal["sqlite", "oracle"] = "sqlite",
    ) -> CompiledQuery:
        """Apply owner-qualified Oracle mappings only after canonical compilation."""
        query = self._compile(validated, principal, dialect).model_copy(
            update={"bundle_version": self.bundle_version}
        )
        if dialect == "oracle":
            import_tree = sqlglot.parse_one(query.sql, read=dialect)
            return query.model_copy(
                update={"sql": oracle_identifiers(import_tree, self.catalog).sql(dialect=dialect)}
            )
        return query

    def _compile(
        self,
        validated: ValidatedPlan,
        principal: Principal,
        dialect: Literal["sqlite", "oracle"] = "sqlite",
    ) -> CompiledQuery:
        """Recheck proof before lowering; output still requires independent validation."""
        rechecked = self.validator.validate(validated.plan, principal)
        if rechecked != validated:
            raise Failure("INVALID_PROOF", "Query authorization is no longer valid.", 403)
        plan = validated.plan
        if plan.operation == "combine":
            components = tuple(
                self._compile(self.validator.validate(item, principal), principal, dialect)
                for item in component_plans(plan, self.catalog)
            )
            return combine_query(components, validated, principal, self.catalog)
        if plan.ranking is not None:
            core = self._compile(
                self.validator.validate(plan.model_copy(update={"ranking": None}), principal),
                principal,
                dialect,
            )
            return rank_query(core, validated, self.catalog)
        view = next(item for item in self.catalog.views if item.id == plan.view_id)
        ir = RelationalIR(
            view.root,
            validated.proof.relationships,
            plan.dimensions,
            plan.metrics,
            plan.limit,
            plan.operation == "preaggregate",
        )
        dimensions = {item.id: item for item in self.catalog.dimensions}
        metrics = {item.id: item for item in self.catalog.metrics}
        policy = view_policy(view)
        execution_policy(self.catalog, validated, dialect)
        relations = {item.id: item for item in self.catalog.relations}
        binds: list[tuple[str, Bind]] = []

        def bind(value: Bind) -> exp.Placeholder:
            name = f"p{len(binds)}"
            binds.append((name, value))
            return exp.Placeholder(this=name)

        def aggregate(key: str) -> exp.Expr:
            metric = metrics[key]
            if metric.expression is not None:
                if metric.expression.kind != "difference":
                    raise Failure(
                        "UNSUPPORTED_COMPILER_OPERATOR", "Ratio predicates are not supported."
                    )
                return exp.Sub(
                    this=aggregate(metric.expression.numerator),
                    expression=aggregate(metric.expression.denominator),
                )
            source = column(metric.table, metric.column)
            operators = {
                "sum": exp.Sum,
                "count": exp.Count,
                "avg": exp.Avg,
                "min": exp.Min,
                "max": exp.Max,
            }
            # AVG stays exact: return sum and count separately; formatter divides Decimal.
            return operators[metric.aggregate](this=source)

        def condition(node: Predicate | FilterGroup, having: bool = False) -> exp.Expr:
            if isinstance(node, FilterGroup):
                parts = [condition(child, having) for child in node.children]
                return exp.and_(*parts) if node.op == "and" else exp.or_(*parts)
            if having:
                source = aggregate(node.field)
                metric = metrics[node.field]
                scale = metric.scale
                source_kind = next(
                    field.kind
                    for table in self.catalog.tables
                    if table.id == metric.table
                    for field in table.columns
                    if field.name == metric.column
                )
            else:
                dimension = dimensions[node.field]
                source = column(dimension.table, dimension.column)
                scale = 1
                source_kind = dimension.kind
            if node.op in ("is_null", "is_not_null"):
                result = exp.Is(this=source, expression=exp.Null())
                return exp.Not(this=result) if node.op == "is_not_null" else result
            value = node.value.value
            if node.op == "in" and isinstance(value, tuple):
                return exp.In(this=source, expressions=[bind(item) for item in value])
            if not isinstance(value, (str, int)):
                raise Failure("INVALID_FILTER", "The filter value is invalid.")
            if node.value.kind == "decimal":
                # Certified values have up to 38 digits, plus a scale of up to 10**9.
                with localcontext(prec=80):
                    raw = Decimal(str(value)) * scale
                if source_kind == "decimal":
                    value = format(raw, "f")
                else:
                    value = int(raw)
            operations = {
                "eq": exp.EQ,
                "ne": exp.NEQ,
                "gt": exp.GT,
                "ge": exp.GTE,
                "lt": exp.LT,
                "le": exp.LTE,
            }
            return operations[node.op](this=source, expression=bind(value))

        selected: list[exp.Expr] = []
        for key in ir.group:
            field = dimensions[key]
            selected.append(column(field.table, field.column).as_(key, quoted=True))
        for key in ir.measures:
            metric = metrics[key]
            if metric.expression is not None and metric.expression.kind == "ratio":
                selected.extend(
                    (
                        aggregate(metric.expression.numerator).as_(key, quoted=True),
                        aggregate(metric.expression.denominator).as_(key + "_d", quoted=True),
                    )
                )
            elif metric.aggregate == "avg":
                selected.extend(
                    (
                        exp.Sum(this=column(metric.table, metric.column)).as_(key),
                        exp.Count(this=column(metric.table, metric.column)).as_(key + "_n"),
                    )
                )
            else:
                selected.append(aggregate(key).as_(key, quoted=True))
        query = exp.select(*selected).from_(exp.to_table(ir.root, quoted=True))
        for edge_id in ir.joins:
            edge = relations[edge_id]
            query = query.join(
                exp.to_table(edge.right, quoted=True),
                on=exp.and_(
                    *(
                        exp.EQ(this=column(edge.left, left), expression=column(edge.right, right))
                        for left, right in edge.pairs
                    )
                ),
                join_type="INNER",
            )
        predicates: list[exp.Expr] = []
        if policy.strategy == "tenant_scope":
            assert policy.tenant_column is not None and policy.scope_dimension is not None
            scope = dimensions[policy.scope_dimension]
            predicates.extend(
                (
                    column(view.root, policy.tenant_column).eq(bind(principal.tenant)),
                    exp.In(
                        this=column(scope.table, scope.column),
                        expressions=[bind(value) for value in scope_values(policy, principal)],
                    ),
                )
            )
        if policy.status_column is not None:
            predicates.append(
                column(view.root, policy.status_column).eq(bind(view.mandatory_status))
            )
        if isinstance(plan.period, Period) and view.time_column is not None:
            predicates.append(
                column(view.root, view.time_column).eq(bind(plan.period.as_of.isoformat()))
            )
        elif isinstance(plan.period, DateRange) and view.time_column is not None:
            predicates.extend(
                (
                    exp.GTE(
                        this=column(view.root, view.time_column),
                        expression=bind(plan.period.start.isoformat()),
                    ),
                    exp.LT(
                        this=column(view.root, view.time_column),
                        expression=bind(plan.period.end_exclusive.isoformat()),
                    ),
                )
            )
        if plan.filters is not None:
            predicates.append(condition(plan.filters))
        if predicates:
            query = query.where(exp.and_(*predicates))
        if ir.group:
            query = query.group_by(
                *(column(dimensions[key].table, dimensions[key].column) for key in ir.group)
            )
        if plan.having is not None:
            query = query.having(condition(plan.having, True))
        ordered = [
            exp.Ordered(
                this=exp.column(item.field, quoted=True),
                desc=item.direction == "desc",
                nulls_first=False,
            )
            for item in plan.sort
        ]
        ordered.extend(
            exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
            for key in ir.group
            if key not in {item.field for item in plan.sort}
        )
        if ordered:
            query = query.order_by(*ordered)
        # One extra row makes truncation explicit while returning at most the requested limit.
        query = query.limit(ir.limit + 1)
        if ir.preaggregate:
            # Single-source aggregate CTE; certified multi-fact plans use combine_query.
            query = (
                exp.select(*(exp.column(key, quoted=True) for key in (*ir.group, *ir.measures)))
                .from_("approved_aggregate")
                .with_("approved_aggregate", as_=query)
            )
        return CompiledQuery(
            sql=query.sql(dialect=dialect),
            binds=tuple(binds),
            bind_types=infer_bind_types(query, dict(binds), self.catalog),
            dialect=dialect,
            validated_plan=validated,
            output=tuple(item.alias_or_name for item in selected),
        )


def execution_policy(catalog: Catalog, validated: ValidatedPlan, dialect: str) -> None:
    """Unsupported security/decimal execution modes fail before any SQL reaches an adapter."""
    view = next(item for item in catalog.views if item.id == validated.plan.view_id)
    if view_policy(view).strategy == "database_context" and dialect != "oracle":
        raise Failure("POLICY_UNAVAILABLE", "The certified database policy requires Oracle.", 403)
    if dialect == "sqlite" and any(
        field.kind == "decimal"
        for table in catalog.tables
        if table.id in validated.proof.tables
        for field in table.columns
    ):
        raise Failure(
            "DECIMAL_SQLITE_UNSUPPORTED", "Exact decimal-source execution requires Oracle."
        )
