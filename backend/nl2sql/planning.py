"""Semantic validation independent of natural language and SQL syntax."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from nl2sql.catalog import JoinGraph, catalog_hash, digest
from nl2sql.domain import (
    Catalog,
    DateRange,
    Failure,
    FilterGroup,
    FiscalPeriod,
    Period,
    Predicate,
    Principal,
    Proof,
    QueryPlan,
    SemanticView,
    ValidatedPlan,
    scope_values,
    view_policy,
)


def principal_hash(principal: Principal) -> str:
    """Changing grants invalidates capabilities and stored authorization assumptions."""
    return digest(principal.model_dump_json())


def leaves(condition: Predicate | FilterGroup | None, depth: int = 0) -> tuple[Predicate, ...]:
    """Bound recursion, work and generated bind count."""
    if depth > 4:
        raise Failure("FILTER_COMPLEXITY", "Please simplify the filters.")
    if condition is None:
        return ()
    if isinstance(condition, Predicate):
        return (condition,)
    result = tuple(item for child in condition.children for item in leaves(child, depth + 1))
    if len(result) > 40:
        raise Failure("FILTER_COMPLEXITY", "Please simplify the filters.")
    return result


def check_value(
    predicate: Predicate,
    kind: str,
    monetary: bool = False,
    decimal_places: int = 2,
    precision: int = 38,
) -> None:
    """Validate tagged values without converting arbitrary strings into code."""
    value = predicate.value
    if predicate.op in ("is_null", "is_not_null"):
        if value.kind != "null" or value.value is not None:
            raise Failure("INVALID_FILTER", "NULL tests require a null value.")
        return
    if predicate.op == "in":
        if (
            kind != "text"
            or value.kind != "text_list"
            or not isinstance(value.value, tuple)
            or not 1 <= len(value.value) <= 50
        ):
            raise Failure("INVALID_FILTER", "Use a bounded list of text values.")
        return
    if kind == "integer" and not monetary:
        if (
            value.kind != "integer"
            or not isinstance(value.value, int)
            or isinstance(value.value, bool)
        ):
            raise Failure("INVALID_FILTER", "An integer value is required.")
    elif monetary or kind == "decimal":
        if value.kind != "decimal" or not isinstance(value.value, str):
            raise Failure("INVALID_FILTER", "An exact decimal string is required.")
        try:
            number = Decimal(value.value)
            exponent = number.as_tuple().exponent
            if (
                not number.is_finite()
                or not isinstance(exponent, int)
                or exponent < -decimal_places
                or (number != 0 and number.adjusted() >= precision - decimal_places)
            ):
                raise InvalidOperation
        except InvalidOperation as error:
            raise Failure(
                "INVALID_FILTER", "Use a finite decimal within the certified precision and scale."
            ) from error
    elif kind == "date":
        try:
            if value.kind != "date" or not isinstance(value.value, str):
                raise ValueError
            date.fromisoformat(value.value)
        except ValueError as error:
            raise Failure("INVALID_FILTER", "Use an ISO reporting date.") from error
    elif value.kind != "text" or not isinstance(value.value, str) or len(value.value) > 200:
        raise Failure("INVALID_FILTER", "A bounded text value is required.")


def resolve_period(
    plan: QueryPlan, view: SemanticView, catalog: Catalog
) -> Period | DateRange | None:
    """Resolve fiscal boundaries once; snapshots must retain their reporting-date grain."""
    period = plan.period
    if isinstance(period, FiscalPeriod):
        if catalog.fiscal_start_month is None or view.time_kind != "event":
            raise Failure(
                "TIME_UNSUPPORTED", "No compatible certified fiscal calendar is available."
            )
        period = DateRange(
            start=date(period.year, catalog.fiscal_start_month, 1),
            end_exclusive=date(period.year + 1, catalog.fiscal_start_month, 1),
        )
    if view.time_column is None:
        if period is not None:
            raise Failure("TIME_UNSUPPORTED", "This view contains current data only.")
        return None
    if period is None:
        if view.time_kind == "event":
            raise Failure("CLARIFICATION", "Specify a reporting date or date range.")
        period = Period(as_of=catalog.default_as_of)
    if isinstance(period, DateRange):
        if (
            period.start < catalog.effective_from
            or period.end_exclusive - timedelta(days=1) > catalog.effective_to
        ):
            raise Failure("TIME_UNSUPPORTED", "This reporting range is outside catalog coverage.")
        if view.time_kind == "snapshot" and "reporting_date" not in plan.dimensions:
            raise Failure("GRAIN_CONFLICT", "Snapshot ranges must group by reporting date.")
    elif not catalog.effective_from <= period.as_of <= catalog.effective_to:
        raise Failure("TIME_UNSUPPORTED", "This reporting date is outside catalog coverage.")
    return period


def component_plans(plan: QueryPlan, catalog: Catalog) -> tuple[QueryPlan, ...]:
    """Certified multi-fact queries aggregate each component to customer grain before joining."""
    view = next(item for item in catalog.views if item.id == plan.view_id)
    result: list[QueryPlan] = []
    for key in view.components:
        source = next(item for item in catalog.views if item.id == key)
        selected = tuple(metric for metric in plan.metrics if metric in source.metrics)
        if selected:
            result.append(
                QueryPlan(
                    catalog_version=plan.catalog_version,
                    view_id=source.id,
                    view_version=source.version,
                    metrics=selected,
                    dimensions=(view.common_key,),
                    filters=plan.filters,
                    period=plan.period if source.time_column else None,
                    limit=plan.limit,
                )
            )
    return tuple(result)


class PlanValidator:
    """Certify field, date, grain, graph and authorization proofs before compilation."""

    def __init__(
        self,
        catalog: Catalog,
        max_rows: int = 1000,
        max_metrics: int = 5,
        max_dimensions: int = 5,
        max_join_edges: int = 6,
    ) -> None:
        self.catalog = catalog
        self.graph = JoinGraph(catalog)
        self.catalog_digest = catalog_hash(catalog)
        self.max_rows = max_rows
        if not (
            1 <= max_rows <= 1000
            and 1 <= max_metrics <= 5
            and 1 <= max_dimensions <= 5
            and 0 <= max_join_edges <= 6
        ):
            raise ValueError("Plan budgets exceed supported compiler ceilings")
        self.limits = (max_metrics, max_dimensions, max_join_edges)

    def validate(self, plan: QueryPlan, principal: Principal) -> ValidatedPlan:
        """Every turn, including templates and follow-ups, traverses these gates."""
        if len(plan.metrics) > self.limits[0] or len(plan.dimensions) > self.limits[1]:
            raise Failure(
                "PLAN_COMPLEXITY", "Reduce the number of selected measures or dimensions."
            )
        result = self._validate(plan, principal)
        if len(result.proof.relationships) > self.limits[2]:
            raise Failure("PLAN_COMPLEXITY", "This report exceeds the approved join budget.")
        return result

    def _validate(self, plan: QueryPlan, principal: Principal) -> ValidatedPlan:
        if plan.catalog_version != self.catalog.version:
            raise Failure("CATALOG_STALE", "The catalog changed; please ask again.", 409)
        if not set(plan.metrics) <= set(principal.metrics):
            raise Failure("DENIED", "This request is outside your authorized scope.", 403)
        views = {view.id: view for view in self.catalog.views if view.certified}
        view = views.get(plan.view_id)
        if view is None or plan.view_version != view.version:
            raise Failure("VIEW_STALE", "This business view is unavailable.", 409)
        policy = view_policy(view)
        if policy.strategy == "tenant_scope" and not scope_values(policy, principal):
            raise Failure("DENIED", "No authorized data scope is available.", 403)
        if not set(plan.metrics) <= set(view.metrics):
            raise Failure("UNKNOWN_METRIC", "The requested metric is unsupported.")
        if not set(plan.dimensions) <= set(view.dimensions):
            raise Failure("GRAIN_CONFLICT", "These dimensions are incompatible with the metric.")
        if plan.limit > self.max_rows:
            raise Failure("LIMIT_EXCEEDED", "Please request fewer result rows.")
        metrics = {item.id: item for item in self.catalog.metrics}
        dimensions = {item.id: item for item in self.catalog.dimensions}
        if view.components:
            return self._composite(plan, principal, view)
        if plan.operation == "combine":
            raise Failure(
                "UNSUPPORTED_COMPILER_OPERATOR", "Only certified composite views support combine."
            )
        period = resolve_period(plan, view, self.catalog)
        if plan.operation == "preaggregate" and any(
            metrics[key].aggregate not in ("sum", "count") or metrics[key].expression is not None
            for key in plan.metrics
        ):
            raise Failure(
                "UNSUPPORTED_COMPILER_OPERATOR", "Preaggregation supports sums and counts."
            )
        targets = {dimensions[key].table for key in plan.dimensions}
        if policy.scope_dimension is not None and policy.strategy == "tenant_scope":
            targets.add(dimensions[policy.scope_dimension].table)
        for predicate in leaves(plan.filters):
            if predicate.field not in view.dimensions:
                raise Failure("UNKNOWN_FIELD", "This filter is unavailable.")
            dimension = dimensions[predicate.field]
            column = next(
                column
                for table in self.catalog.tables
                if table.id == dimension.table
                for column in table.columns
                if column.name == dimension.column
            )
            check_value(
                predicate,
                dimension.kind,
                decimal_places=column.scale or 0,
                precision=column.precision or 38,
            )
            targets.add(dimension.table)
        for predicate in leaves(plan.having):
            if predicate.field not in plan.metrics:
                raise Failure("INVALID_HAVING", "HAVING must reference a selected metric.")
            check_value(
                predicate,
                "integer",
                metrics[predicate.field].unit not in {"count", "percent"},
                decimal_places=metrics[predicate.field].decimal_places,
            )
        if any(item.field not in (*plan.dimensions, *plan.metrics) for item in plan.sort):
            raise Failure("INVALID_SORT", "Sort by a selected output field.")
        averages = {key for key in plan.metrics if metrics[key].aggregate == "avg"}
        averages.update(
            metric.id
            for metric in metrics.values()
            if metric.id in plan.metrics
            and metric.expression is not None
            and metric.expression.kind == "ratio"
        )
        if averages.intersection(item.field for item in plan.sort) or averages.intersection(
            item.field for item in leaves(plan.having)
        ):
            raise Failure(
                "UNSUPPORTED_COMPILER_OPERATOR",
                "Average/ratio sorting and HAVING are not qualified.",
            )
        if plan.ranking is not None:
            rank = plan.ranking
            if (
                rank.metric not in plan.metrics
                or rank.metric in averages
                or not plan.dimensions
                or plan.sort
                or plan.operation != "aggregate"
            ):
                raise Failure(
                    "INVALID_RANKING", "Rank a selected additive metric with explicit dimensions."
                )
            if len(set(rank.partition_by)) != len(rank.partition_by) or not set(
                rank.partition_by
            ) < set(plan.dimensions):
                raise Failure(
                    "INVALID_RANKING",
                    "Ranking partitions must be a proper subset of grouping fields.",
                )
        historical = period is not None and (
            not isinstance(period, Period) or period.as_of != self.catalog.default_as_of
        )
        relations = self.graph.resolve(view, targets, historical=historical)
        resolved = plan.model_copy(update={"period": period})
        return ValidatedPlan(
            plan=resolved,
            proof=Proof(
                catalog_digest=self.catalog_digest,
                principal_digest=principal_hash(principal),
                view_id=view.id,
                view_version=view.version,
                relationships=tuple(edge.id for edge in relations),
                tables=(view.root, *(edge.right for edge in relations)),
                grain=plan.dimensions,
            ),
        )

    def _composite(
        self, plan: QueryPlan, principal: Principal, view: SemanticView
    ) -> ValidatedPlan:
        if (
            plan.operation != "combine"
            or plan.ranking is not None
            or plan.having is not None
            or view_policy(view).strategy != "tenant_scope"
        ):
            raise Failure(
                "UNSUPPORTED_COMPILER_OPERATOR",
                "Composite views require the combine operation without HAVING/windows.",
            )
        metrics = {item.id: item for item in self.catalog.metrics}
        if any(
            metrics[key].aggregate not in ("sum", "count") or metrics[key].expression is not None
            for key in plan.metrics
        ):
            raise Failure(
                "GRAIN_CONFLICT", "Composite views support primitive additive measures only."
            )
        if isinstance(plan.period, (DateRange, FiscalPeriod)):
            raise Failure(
                "GRAIN_CONFLICT", "Composite snapshot metrics require one reporting date."
            )
        period = plan.period or Period(as_of=self.catalog.default_as_of)
        if period.as_of != self.catalog.default_as_of and any(
            metrics[key].temporal == "current" for key in plan.metrics
        ):
            raise Failure("TIME_UNSUPPORTED", "Current measures cannot answer a historical report.")
        plan = plan.model_copy(update={"period": period})
        components = [
            self.validate(item, principal) for item in component_plans(plan, self.catalog)
        ]
        if len(components) < 2:
            raise Failure(
                "UNSUPPORTED_COMPILER_OPERATOR",
                "Use a single-source view for a single fact source.",
            )
        if any(item.field not in (*plan.dimensions, *plan.metrics) for item in plan.sort):
            raise Failure("INVALID_SORT", "Sort by a selected output field.")
        policy = view_policy(view)
        targets = {item.table for item in self.catalog.dimensions if item.id in plan.dimensions}
        if policy.scope_dimension is not None:
            targets.update(
                item.table for item in self.catalog.dimensions if item.id == policy.scope_dimension
            )
        joins = self.graph.resolve(
            view, targets, historical=period.as_of != self.catalog.default_as_of
        )
        return ValidatedPlan(
            plan=plan,
            proof=Proof(
                catalog_digest=self.catalog_digest,
                principal_digest=principal_hash(principal),
                view_id=view.id,
                view_version=view.version,
                grain=plan.dimensions,
                relationships=tuple(
                    dict.fromkeys(
                        [edge.id for edge in joins]
                        + [key for item in components for key in item.proof.relationships]
                    )
                ),
                tables=tuple(
                    dict.fromkeys(
                        [view.root, *(edge.right for edge in joins)]
                        + [key for item in components for key in item.proof.tables]
                    )
                ),
            ),
        )
