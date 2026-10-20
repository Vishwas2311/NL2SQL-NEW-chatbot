"""Independent AST/semantic checks and signed, expiring execution capabilities."""

import hashlib
import hmac
import time
from collections.abc import Callable
from decimal import Decimal, localcontext

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from nl2sql.application.catalog import JoinGraph
from nl2sql.application.query.physical_sql import oracle_identifiers
from nl2sql.application.query.planning import PlanValidator, component_plans, principal_hash
from nl2sql.application.query.sql_types import infer_bind_types
from nl2sql.domain.fingerprints import catalog_hash
from nl2sql.domain.models import (
    Bind,
    Capability,
    Catalog,
    CompiledQuery,
    DateRange,
    Failure,
    FilterGroup,
    Period,
    Predicate,
    Principal,
    QueryPlan,
    scope_values,
    view_policy,
)


def _deny() -> Failure:
    return Failure("INVALID_SQL", "The generated query did not pass safety validation.", 422)


def _canonical(tree: exp.Expr, dialect: str) -> str:
    normalized = tree.copy()
    for ordered in normalized.find_all(exp.Ordered):
        ordered.set("desc", bool(ordered.args.get("desc")))
    return normalized.sql(dialect=dialect, identify=True, normalize=True)


def _combine(op: str, children: list[str]) -> str:
    return op + "(" + ",".join(sorted(children)) + ")"


def _atom(field: str, op: str, values: tuple[Bind | None, ...]) -> str:
    return repr((field, op, values))


def _expected_filter(node: Predicate | FilterGroup, catalog: Catalog, having: bool = False) -> str:
    if isinstance(node, FilterGroup):
        parts = _expected_parts(node, node.op, catalog, having)
        return _combine(node.op, parts)
    if having:
        metric = next(item for item in catalog.metrics if item.id == node.field)
        field = _metric_field(metric.id, catalog)
        scale = metric.scale
        kind = next(
            column.kind
            for table in catalog.tables
            if table.id == metric.table
            for column in table.columns
            if column.name == metric.column
        )
    else:
        dimension = next(item for item in catalog.dimensions if item.id == node.field)
        field = f"{dimension.table}.{dimension.column}"
        scale = 1
        kind = dimension.kind
    value = node.value.value
    values: tuple[Bind | None, ...]
    if isinstance(value, tuple):
        values = tuple(value)
    elif node.value.kind == "decimal":
        with localcontext(prec=80):
            raw = Decimal(str(value)) * scale
        values = (format(raw, "f") if kind == "decimal" else int(raw),)
    else:
        values = (value,)
    return _atom(field, node.op, values)


def _field(node: exp.Expr) -> str:
    if isinstance(node, exp.Column) and node.table:
        return f"{node.table}.{node.name}"
    if isinstance(node, (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)):
        return f"{node.key}({_field(node.this)})"
    if isinstance(node, exp.Sub):
        return f"sub({_field(node.this)},{_field(node.expression)})"
    raise _deny()


def _metric_field(key: str, catalog: Catalog) -> str:
    metric = next(item for item in catalog.metrics if item.id == key)
    if metric.expression is not None:
        if metric.expression.kind != "difference":
            raise _deny()
        numerator = _metric_field(metric.expression.numerator, catalog)
        denominator = _metric_field(metric.expression.denominator, catalog)
        return f"sub({numerator},{denominator})"
    return f"{metric.aggregate}({metric.table}.{metric.column})"


def _expected_parts(
    node: Predicate | FilterGroup, op: str, catalog: Catalog, having: bool = False
) -> list[str]:
    if isinstance(node, FilterGroup) and node.op == op:
        return [
            part for child in node.children for part in _expected_parts(child, op, catalog, having)
        ]
    return [_expected_filter(node, catalog, having)]


def _actual_filter(node: exp.Expr, binds: dict[str, Bind]) -> str:
    if isinstance(node, exp.Paren):
        return _actual_filter(node.this, binds)
    if isinstance(node, (exp.And, exp.Or)):
        parts: list[str] = []

        def flatten(item: exp.Expr) -> None:
            if isinstance(item, exp.Paren):
                flatten(item.this)
            elif type(item) is type(node):
                flatten(item.this)
                flatten(item.expression)
            else:
                parts.append(_actual_filter(item, binds))

        flatten(node)
        return _combine(node.key, parts)
    if (
        isinstance(node, exp.Not)
        and isinstance(node.this, exp.Is)
        and isinstance(node.this.expression, exp.Null)
    ):
        return _atom(_field(node.this.this), "is_not_null", (None,))
    if isinstance(node, exp.Is) and isinstance(node.expression, exp.Null):
        return _atom(_field(node.this), "is_null", (None,))
    if isinstance(node, exp.In):
        values: list[Bind] = []
        for item in node.expressions:
            if not isinstance(item, exp.Placeholder) or item.name not in binds:
                raise _deny()
            values.append(binds[item.name])
        return _atom(_field(node.this), "in", tuple(values))
    operators: dict[type[exp.Expr], str] = {
        exp.EQ: "eq",
        exp.NEQ: "ne",
        exp.GT: "gt",
        exp.GTE: "ge",
        exp.LT: "lt",
        exp.LTE: "le",
    }
    if type(node) not in operators or not isinstance(node.expression, exp.Placeholder):
        raise _deny()
    if node.expression.name not in binds:
        raise _deny()
    return _atom(_field(node.this), operators[type(node)], (binds[node.expression.name],))


class SQLValidator:
    """Accept a bounded compiler grammar, independently check semantics, then sign."""

    def __init__(
        self,
        catalog: Catalog,
        secret: bytes,
        bundle_version: str = "",
        guard: Callable[[CompiledQuery, Principal], None] | None = None,
    ) -> None:
        self.catalog = catalog
        self.secret = secret
        self.plan_validator = PlanValidator(catalog)
        self.bundle_version = bundle_version
        self.guard = guard

    def _signature(self, query: CompiledQuery, expires: float) -> str:
        payload = f"{query.model_dump_json()}:{expires}".encode()
        return hmac.new(self.secret, payload, hashlib.sha256).hexdigest()

    def validate(self, query: CompiledQuery, principal: Principal, deadline: float) -> Capability:
        """All drafts, including template queries, require this independent pass."""
        if query.bundle_version != self.bundle_version:
            raise _deny()
        if self.guard is not None:
            self.guard(query, principal)
        current = self.plan_validator.validate(query.validated_plan.plan, principal)
        if current != query.validated_plan:
            raise _deny()
        try:
            statements = sqlglot.parse(query.sql, read=query.dialect)
        except ParseError as error:
            raise _deny() from error
        if len(statements) != 1 or not isinstance(statements[0], exp.Select):
            raise _deny()
        tree = statements[0]
        if query.dialect == "oracle":
            tree = oracle_identifiers(tree, self.catalog, reverse=True)
            assert isinstance(tree, exp.Select)
        if any(node.comments for node in tree.walk()):
            raise _deny()
        plan = current.plan
        if plan.operation == "combine":
            self._composite(tree, query, principal, deadline)
            expires = min(time.time() + 30, deadline)
            return Capability(
                query=query, expires_at=expires, signature=self._signature(query, expires)
            )
        if plan.ranking is not None:
            self._ranking(tree, query, principal, deadline)
            expires = min(time.time() + 30, deadline)
            return Capability(
                query=query, expires_at=expires, signature=self._signature(query, expires)
            )
        view = next(item for item in self.catalog.views if item.id == plan.view_id)
        if plan.operation == "preaggregate":
            ctes = list(tree.find_all(exp.CTE))
            if len(ctes) != 1 or ctes[0].alias != "approved_aggregate":
                raise _deny()
            wrapper = tree.copy()
            next(wrapper.find_all(exp.CTE)).set("this", exp.select(exp.Literal.number(1)))
            expected = (
                exp.select(
                    *(exp.column(key, quoted=True) for key in (*plan.dimensions, *plan.metrics))
                )
                .from_("approved_aggregate")
                .with_("approved_aggregate", as_=exp.select(exp.Literal.number(1)))
            )
            if _canonical(wrapper, query.dialect) != _canonical(expected, query.dialect):
                raise _deny()
            if not isinstance(ctes[0].this, exp.Select):
                raise _deny()
            tree = ctes[0].this
        elif tree.find(exp.CTE) is not None:
            raise _deny()
        if sum(1 for _ in tree.find_all(exp.Select)) != 1:
            raise _deny()
        self._structure(tree, query)
        self._projections(tree, query)
        self._relationships(tree, query)
        binds = dict(query.binds)
        if len(binds) != len(query.binds):
            raise _deny()
        placeholders = {item.name for item in tree.find_all(exp.Placeholder)}
        if placeholders != set(binds):
            raise _deny()
        if query.bind_types != infer_bind_types(tree, binds, self.catalog):
            raise _deny()
        scope_policy = view_policy(view)
        policy: list[str] = []
        if scope_policy.strategy == "tenant_scope":
            scope = next(
                item for item in self.catalog.dimensions if item.id == scope_policy.scope_dimension
            )
            policy.extend(
                (
                    _atom(f"{view.root}.{scope_policy.tenant_column}", "eq", (principal.tenant,)),
                    _atom(
                        f"{scope.table}.{scope.column}", "in", scope_values(scope_policy, principal)
                    ),
                )
            )
        if scope_policy.status_column is not None:
            policy.append(
                _atom(f"{view.root}.{scope_policy.status_column}", "eq", (view.mandatory_status,))
            )
        if isinstance(plan.period, Period):
            policy.append(
                _atom(f"{view.root}.{view.time_column}", "eq", (plan.period.as_of.isoformat(),))
            )
        elif isinstance(plan.period, DateRange):
            policy.extend(
                (
                    _atom(
                        f"{view.root}.{view.time_column}", "ge", (plan.period.start.isoformat(),)
                    ),
                    _atom(
                        f"{view.root}.{view.time_column}",
                        "lt",
                        (plan.period.end_exclusive.isoformat(),),
                    ),
                )
            )
        if plan.filters is not None:
            policy.extend(_expected_parts(plan.filters, "and", self.catalog))
        where = tree.args.get("where")
        if (
            policy
            and (
                not isinstance(where, exp.Where)
                or _actual_filter(where.this, binds) != _combine("and", policy)
            )
        ) or (not policy and where is not None):
            raise _deny()
        having = tree.args.get("having")
        if plan.having is None:
            if having is not None:
                raise _deny()
        elif not isinstance(having, exp.Having) or _actual_filter(
            having.this, binds
        ) != _expected_filter(plan.having, self.catalog, True):
            raise _deny()
        expires = min(time.time() + 30, deadline)
        if expires <= time.time():
            raise Failure("QUERY_TIMEOUT", "The request deadline was exceeded.", 504)
        return Capability(
            query=query, expires_at=expires, signature=self._signature(query, expires)
        )

    def _structure(self, tree: exp.Select, query: CompiledQuery) -> None:
        allowed_args = {
            "expressions",
            "from_",
            "joins",
            "where",
            "group",
            "having",
            "order",
            "limit",
        }
        if any(value for key, value in tree.args.items() if key not in allowed_args):
            raise _deny()
        self._nodes(tree, query)

    def _ranking(
        self, tree: exp.Select, query: CompiledQuery, principal: Principal, deadline: float
    ) -> None:
        """Compare the complete wrapper to an independently stated analytic contract."""
        plan = query.validated_plan.plan
        rank = plan.ranking
        assert rank is not None
        ctes = list(tree.find_all(exp.CTE))
        if len(ctes) != 2 or [item.alias for item in ctes] != [
            "approved_aggregate",
            "approved_ranked",
        ]:
            raise _deny()
        aggregate = ctes[0].this
        if (
            not isinstance(aggregate, exp.Select)
            or aggregate.args.get("limit")
            or aggregate.args.get("order")
        ):
            raise _deny()
        fields = tuple(item.alias_or_name for item in aggregate.expressions)
        if query.output != (*fields, "rank_value"):
            raise _deny()

        def quote(key: str) -> str:
            return '"' + key + '"'

        selected = ", ".join(quote(key) for key in fields)
        partition = (
            "PARTITION BY " + ", ".join(quote(key) for key in rank.partition_by) + " "
            if rank.partition_by
            else ""
        )
        window_order = f"{quote(rank.metric)} {rank.direction.upper()} NULLS LAST"
        if rank.method == "row_number":
            window_order += "".join(
                ", " + quote(key) + " ASC NULLS LAST"
                for key in plan.dimensions
                if key not in rank.partition_by
            )
        output_order = (
            *rank.partition_by,
            "rank_value",
            *(key for key in plan.dimensions if key not in rank.partition_by),
        )
        expected_sql = (
            f"WITH approved_aggregate AS (SELECT 1), approved_ranked AS "
            f"(SELECT {selected}, {rank.method.upper()}() "
            f"OVER ({partition}ORDER BY {window_order}) "
            'AS "rank_value" FROM approved_aggregate) '
            f'SELECT {selected}, "rank_value" FROM approved_ranked '
            'WHERE "rank_value" <= :rank_limit '
            f"ORDER BY {', '.join(quote(key) + ' ASC NULLS LAST' for key in output_order)} "
            f"LIMIT {plan.limit + 1}"
        )
        wrapper = tree.copy()
        next(wrapper.find_all(exp.CTE)).set("this", exp.select(exp.Literal.number(1)))
        expected = sqlglot.parse_one(expected_sql)
        if _canonical(wrapper, query.dialect) != _canonical(expected, query.dialect):
            raise _deny()
        binds = dict(query.binds)
        if binds.pop("rank_limit", None) != rank.top_n or len(dict(query.binds)) != len(
            query.binds
        ):
            raise _deny()
        original = aggregate.copy().limit(plan.limit + 1)
        original = original.order_by(
            *(
                exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
                for key in plan.dimensions
            )
        )
        core_plan = plan.model_copy(update={"ranking": None})
        core = query.model_copy(
            update={
                "sql": original.sql(dialect=query.dialect),
                "binds": tuple(binds.items()),
                "bind_types": infer_bind_types(original, binds, self.catalog),
                "output": fields,
                "validated_plan": self.plan_validator.validate(core_plan, principal),
            }
        )
        if query.bind_types != infer_bind_types(tree, dict(query.binds), self.catalog):
            raise _deny()
        self.validate(self._physical_core(core), principal, deadline)

    def _nodes(self, tree: exp.Select, query: CompiledQuery) -> None:
        allowed_nodes = (
            exp.Select,
            exp.From,
            exp.Table,
            exp.Identifier,
            exp.Column,
            exp.Alias,
            exp.Join,
            exp.And,
            exp.Or,
            exp.Paren,
            exp.EQ,
            exp.NEQ,
            exp.GT,
            exp.GTE,
            exp.LT,
            exp.LTE,
            exp.In,
            exp.Is,
            exp.Not,
            exp.Null,
            exp.Placeholder,
            exp.Where,
            exp.Group,
            exp.Having,
            exp.Order,
            exp.Ordered,
            exp.Limit,
            exp.Fetch,
            exp.LimitOptions,
            exp.Literal,
            exp.Sum,
            exp.Count,
            exp.Min,
            exp.Max,
            exp.Avg,
            exp.Sub,
        )
        if any(not isinstance(node, allowed_nodes) for node in tree.walk()):
            raise _deny()
        self._physical(tree, query)

    def _composite(
        self, tree: exp.Select, query: CompiledQuery, principal: Principal, deadline: float
    ) -> None:
        """Independently verify every source aggregate, then the exact customer-grain join."""
        plan = query.validated_plan.plan
        sources = component_plans(plan, self.catalog)
        ctes = list(tree.find_all(exp.CTE))
        names = tuple(f"component_{index}" for index in range(len(sources)))
        if tuple(item.alias for item in ctes) != names or query.output != (
            *plan.dimensions,
            *plan.metrics,
        ):
            raise _deny()
        binds = dict(query.binds)
        if len(binds) != len(query.binds) or set(binds) != {
            item.name for item in tree.find_all(exp.Placeholder)
        }:
            raise _deny()
        if query.bind_types != infer_bind_types(tree, binds, self.catalog):
            raise _deny()
        for source, cte in zip(sources, ctes, strict=True):
            body = cte.this
            if not isinstance(body, exp.Select) or body.args.get("limit") or body.args.get("order"):
                raise _deny()
            parameters = {item.name: binds[item.name] for item in body.find_all(exp.Placeholder)}
            restored = body.copy().limit(plan.limit + 1)
            restored = restored.order_by(
                *(
                    exp.Ordered(this=exp.column(key, quoted=True), nulls_first=False)
                    for key in source.dimensions
                )
            )
            core = CompiledQuery(
                bundle_version=self.bundle_version,
                sql=restored.sql(dialect=query.dialect),
                dialect=query.dialect,
                binds=tuple(parameters.items()),
                bind_types=infer_bind_types(restored, parameters, self.catalog),
                output=tuple(item.alias_or_name for item in body.expressions),
                validated_plan=self.plan_validator.validate(source, principal),
            )
            self.validate(self._physical_core(core), principal, deadline)
        expected = self._composite_contract(plan, sources, principal, binds)
        wrapper = tree.copy()
        for cte in wrapper.find_all(exp.CTE):
            cte.set("this", exp.select(exp.Literal.number(1)))
        if _canonical(wrapper, query.dialect) != _canonical(expected, query.dialect):
            raise _deny()

    def _composite_contract(
        self,
        plan: QueryPlan,
        sources: tuple[QueryPlan, ...],
        principal: Principal,
        binds: dict[str, Bind],
    ) -> exp.Expr:
        names = tuple(f"component_{index}" for index in range(len(sources)))
        dimensions = {item.id: item for item in self.catalog.dimensions}
        metrics = {item.id: item for item in self.catalog.metrics}

        def quoted(key: str) -> str:
            return '"' + key + '"'

        fields = [
            f"{quoted(dimensions[key].table)}.{quoted(dimensions[key].column)} AS {quoted(key)}"
            for key in plan.dimensions
        ]
        for key in plan.metrics:
            index = next(index for index, source in enumerate(sources) if key in source.metrics)
            expression = f"SUM({quoted(names[index])}.{quoted(key)})"
            if metrics[key].aggregate == "count":
                expression = f"COALESCE({expression}, 0)"
            fields.append(expression + " AS " + quoted(key))
        view = next(item for item in self.catalog.views if item.id == plan.view_id)
        policy = view_policy(view)
        assert policy.scope_dimension is not None
        common = dimensions[view.common_key]
        scope = dimensions[policy.scope_dimension]
        physical_joins = ""
        for edge in JoinGraph(self.catalog).resolve(
            view, {dimensions[key].table for key in plan.dimensions} | {scope.table}
        ):
            on = " AND ".join(
                f"{quoted(edge.left)}.{quoted(left)} = {quoted(edge.right)}.{quoted(right)}"
                for left, right in edge.pairs
            )
            physical_joins += f" INNER JOIN {quoted(edge.right)} ON {on}"
        joins = "".join(
            f" LEFT JOIN {name} ON {quoted(view.root)}.{quoted(common.column)} = "
            f"{quoted(name)}.{quoted(view.common_key)}"
            for name in names
        )
        region_slots = ", ".join(
            f":outer_region_{index}" for index in range(len(scope_values(policy, principal)))
        )
        if binds.get("outer_tenant") != principal.tenant or any(
            binds.get(f"outer_region_{index}") != region
            for index, region in enumerate(scope_values(policy, principal))
        ):
            raise _deny()
        present = " OR ".join(
            f"NOT {quoted(name)}.{quoted(view.common_key)} IS NULL" for name in names
        )
        status = ""
        if policy.status_column is not None:
            if binds.get("outer_status") != view.mandatory_status:
                raise _deny()
            status = f" AND {quoted(view.root)}.{quoted(policy.status_column)} = :outer_status"
        group = (
            " GROUP BY "
            + ", ".join(
                f"{quoted(dimensions[key].table)}.{quoted(dimensions[key].column)}"
                for key in plan.dimensions
            )
            if plan.dimensions
            else ""
        )
        order = [f"{quoted(item.field)} {item.direction.upper()} NULLS LAST" for item in plan.sort]
        order.extend(
            f"{quoted(key)} ASC NULLS LAST"
            for key in plan.dimensions
            if key not in {item.field for item in plan.sort}
        )
        ordering = " ORDER BY " + ", ".join(order) if order else ""
        expected_sql = (
            "WITH "
            + ", ".join(f"{name} AS (SELECT 1)" for name in names)
            + f" SELECT {', '.join(fields)} FROM {quoted(view.root)}{physical_joins}{joins}"
            + f" WHERE {quoted(view.root)}.{quoted(str(policy.tenant_column))} = :outer_tenant "
            + f"AND {quoted(scope.table)}.{quoted(scope.column)} IN ({region_slots}) "
            + f"AND ({present}){status}"
            + group
            + ordering
            + f" LIMIT {plan.limit + 1}"
        )
        return sqlglot.parse_one(expected_sql)

    def _physical(self, tree: exp.Select, query: CompiledQuery) -> None:
        if any(
            field.db or field.catalog or field.args.get("join_mark")
            for field in tree.find_all(exp.Column)
        ):
            raise _deny()
        tables = list(tree.find_all(exp.Table))
        if any(table.db or table.catalog or table.alias for table in tables):
            raise _deny()
        if tuple(table.name for table in tables) != query.validated_plan.proof.tables:
            raise _deny()
        limit = tree.args.get("limit")
        if not isinstance(limit, (exp.Limit, exp.Fetch)):
            raise _deny()
        literals = list(tree.find_all(exp.Literal))
        if (
            len(literals) != 1
            or literals[0].is_string
            or literals[0].this != str(query.validated_plan.plan.limit + 1)
        ):
            raise _deny()
        if list(limit.find_all(exp.Literal)) != literals:
            raise _deny()

    def _physical_core(self, query: CompiledQuery) -> CompiledQuery:
        if query.dialect != "oracle":
            return query
        tree = sqlglot.parse_one(query.sql, read="oracle")
        return query.model_copy(
            update={"sql": oracle_identifiers(tree, self.catalog).sql(dialect="oracle")}
        )

    def _projections(self, tree: exp.Select, query: CompiledQuery) -> None:
        plan = query.validated_plan.plan
        dimensions = {item.id: item for item in self.catalog.dimensions}
        metrics = {item.id: item for item in self.catalog.metrics}
        expected: list[tuple[str, str]] = []
        for key in plan.dimensions:
            field = dimensions[key]
            expected.append((key, f"{field.table}.{field.column}"))
        for key in plan.metrics:
            metric = metrics[key]
            field = f"{metric.table}.{metric.column}"
            if metric.expression is not None and metric.expression.kind == "ratio":
                expected.extend(
                    (
                        (key, _metric_field(metric.expression.numerator, self.catalog)),
                        (key + "_d", _metric_field(metric.expression.denominator, self.catalog)),
                    )
                )
            elif metric.aggregate == "avg":
                expected.extend(((key, f"sum({field})"), (key + "_n", f"count({field})")))
            else:
                expected.append((key, _metric_field(key, self.catalog)))
        actual = [
            (item.alias, _field(item.this))
            for item in tree.expressions
            if isinstance(item, exp.Alias)
        ]
        if len(actual) != len(tree.expressions) or actual != expected:
            raise _deny()
        if query.output != tuple(key for key, _ in expected):
            raise _deny()
        group = tree.args.get("group")
        actual_group = (
            tuple(_field(item) for item in group.expressions)
            if isinstance(group, exp.Group)
            else ()
        )
        if actual_group != tuple(
            f"{dimensions[key].table}.{dimensions[key].column}" for key in plan.dimensions
        ):
            raise _deny()
        order = tree.args.get("order")
        actual_order: list[tuple[str, bool]] = []
        if isinstance(order, exp.Order):
            for item in order.expressions:
                if (
                    not isinstance(item, exp.Ordered)
                    or not isinstance(item.this, exp.Column)
                    or item.this.table
                    or item.args.get("nulls_first") is not False
                ):
                    raise _deny()
                actual_order.append((item.this.name, bool(item.args.get("desc"))))
        expected_order = [(item.field, item.direction == "desc") for item in plan.sort]
        expected_order.extend(
            (key, False) for key in plan.dimensions if key not in {item.field for item in plan.sort}
        )
        if actual_order != expected_order:
            raise _deny()

    def _relationships(self, tree: exp.Select, query: CompiledQuery) -> None:
        edges = {edge.id: edge for edge in self.catalog.relations}
        joins = list(tree.find_all(exp.Join))
        if len(joins) != len(query.validated_plan.proof.relationships):
            raise _deny()
        for join, edge_id in zip(joins, query.validated_plan.proof.relationships, strict=True):
            edge = edges[edge_id]
            if (
                join.this.name != edge.right
                or join.args.get("kind") != "INNER"
                or join.args.get("side")
            ):
                raise _deny()
            on = join.args.get("on")
            if not isinstance(on, exp.Expr):
                raise _deny()
            allowed = (exp.And, exp.EQ, exp.Column, exp.Identifier, exp.Paren)
            if any(not isinstance(node, allowed) for node in on.walk()):
                raise _deny()
            actual = {(_field(item.this), _field(item.expression)) for item in on.find_all(exp.EQ)}
            expected = {
                (f"{edge.left}.{left}", f"{edge.right}.{right}") for left, right in edge.pairs
            }
            if actual != expected:
                raise _deny()

    def verify(self, capability: Capability, principal: Principal) -> CompiledQuery:
        """Execution reasserts expiry, signature, catalog and current grant identity."""
        if (
            capability.expires_at <= time.time()
            or not hmac.compare_digest(
                capability.signature, self._signature(capability.query, capability.expires_at)
            )
            or capability.query.validated_plan.proof.principal_digest != principal_hash(principal)
            or capability.query.validated_plan.proof.catalog_digest != catalog_hash(self.catalog)
        ):
            raise Failure("CAPABILITY_DENIED", "Query authorization expired or changed.", 403)
        if capability.query.bundle_version != self.bundle_version:
            raise _deny()
        if self.guard is not None:
            self.guard(capability.query, principal)
        return capability.query
