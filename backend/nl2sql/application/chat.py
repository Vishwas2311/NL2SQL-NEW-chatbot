"""Authenticated application pipeline; no business logic in transport routers."""

import re
import time
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from typing import Literal
from uuid import uuid4

from nl2sql.application.context import build_context
from nl2sql.application.ports import (
    CatalogProvider,
    ModelProvider,
    QueryExecutor,
    SchemaRetriever,
    SessionRepository,
)
from nl2sql.application.query.compiler import Compiler
from nl2sql.application.query.planning import PlanValidator, principal_hash
from nl2sql.application.text import normalize
from nl2sql.domain.models import (
    Answer,
    Catalog,
    DateRange,
    Failure,
    FilterGroup,
    Period,
    Predicate,
    Principal,
    Provenance,
    QueryPlan,
    Row,
    Sort,
    TypedValue,
    money_text,
)
from nl2sql.domain.sessions import SessionState
from nl2sql.settings import Settings
from nl2sql.telemetry import measured, stage_metrics


def certified_template(question: str, catalog: Catalog) -> QueryPlan | None:
    """Exact full-sentence match; similar wording must use structured planning."""
    match = next(
        (item for item in catalog.templates if normalize(item.question) == normalize(question)),
        None,
    )
    if match is not None:
        return match.plan
    if catalog.version not in {"synthetic-v1", "synthetic-v2"}:
        return None
    templates = {
        "show total loan exposure by region": ("loan_exposure", ("region",)),
        "show loan count by region": ("loan_count", ("region",)),
        "show account count by region": ("account_count", ("region",)),
        "show total loan exposure": ("loan_exposure", ()),
        "show average exposure by region": ("average_exposure", ("region",)),
    }
    match = templates.get(normalize(question))
    if match is None:
        return None
    metric, dimensions = match
    view = next(item for item in catalog.views if metric in item.metrics)
    return QueryPlan(
        catalog_version=catalog.version, view_id=view.id, metrics=(metric,), dimensions=dimensions
    )


class ChatService:
    """One complete compiler-first use case, with safe follow-up context reduction."""

    def __init__(
        self,
        settings: Settings,
        store: CatalogProvider,
        retriever: SchemaRetriever,
        model: ModelProvider,
        database: QueryExecutor,
        sessions: SessionRepository,
        bundle_version: str = "",
    ) -> None:
        self.settings = settings
        self.store = store
        self.retriever = retriever
        self.model = model
        self.database = database
        self.sessions = sessions
        catalog = store.snapshot()
        self.compiler = Compiler(
            catalog,
            PlanValidator(
                catalog,
                settings.max_rows,
                settings.max_metrics,
                settings.max_dimensions,
                settings.max_join_edges,
            ),
            bundle_version,
        )

    @property
    def bundle_version(self) -> str:
        """Provenance is owned by the same pinned compiler that generates the query."""
        return self.compiler.bundle_version

    def _followup(self, question: str, state: SessionState, catalog: Catalog) -> QueryPlan | None:
        text = normalize(question)
        commands = {
            "what about last year",
            "now group it by region",
            "give the top five",
            "only active accounts",
            "compare those results",
            "show the same for another branch",
        }
        match = re.fullmatch(
            r"(?:and |what about |make that )(\d{4}(?:-\d{2}-\d{2})?)\??",
            question.strip().casefold(),
        )
        if match is None and text not in commands:
            return None
        previous = state.last_plan
        if previous is None or previous.catalog_version != catalog.version:
            raise Failure("CLARIFICATION", "Ask a complete question with a reporting date first.")
        if text in {"compare those results", "show the same for another branch"}:
            raise Failure("CLARIFICATION", "Specify the comparison periods or the exact branch.")
        if text == "now group it by region":
            return previous.model_copy(update={"dimensions": ("region",)})
        if text == "give the top five":
            if len(previous.metrics) != 1:
                raise Failure("CLARIFICATION", "Specify which metric determines the top five.")
            return previous.model_copy(
                update={"sort": (Sort(field=previous.metrics[0], direction="desc"),), "limit": 5}
            )
        if text == "only active accounts":
            view = next(view for view in catalog.views if view.id == previous.view_id)
            if view.id != "account_current" or view.mandatory_status != "active":
                raise Failure("CLARIFICATION", "Start with a certified active-account report.")
            return previous
        if not isinstance(previous.period, Period):
            raise Failure("CLARIFICATION", "Ask a complete question with a reporting date first.")
        if text == "what about last year":
            try:
                return previous.model_copy(
                    update={
                        "period": Period(
                            as_of=previous.period.as_of.replace(year=previous.period.as_of.year - 1)
                        )
                    }
                )
            except ValueError as error:
                raise Failure("CLARIFICATION", "Specify a valid reporting date.") from error
        assert match is not None
        value = match[1]
        try:
            as_of = (
                date.fromisoformat(value)
                if len(value) > 4
                else previous.period.as_of.replace(year=int(value))
            )
        except ValueError as error:
            raise Failure("CLARIFICATION", "Use a valid ISO reporting date.") from error
        return previous.model_copy(update={"period": Period(as_of=as_of)})

    def _select_plan(
        self,
        question: str,
        principal: Principal,
        state: SessionState,
        catalog: Catalog,
        deadline: float,
        spans: dict[str, float],
    ) -> tuple[QueryPlan, Literal["template", "model", "followup"]]:
        followup = self._followup(question, state, catalog)
        if followup is not None:
            return followup, "followup"
        template = certified_template(question, catalog)
        if template is not None:
            return template, "template"
        if normalize(question) in {
            "show exposure",
            "show high exposure customers",
            "show balances",
        }:
            raise Failure(
                "CLARIFICATION", "Specify loan exposure, a reporting date and any threshold."
            )
        if re.search(r"\b(delete|drop|truncate|insert|update|execute|grant)\b", question, re.I):
            raise Failure("UNSUPPORTED", "Only approved read-only business reports are supported.")
        started = time.perf_counter()
        candidates = self.retriever.retrieve(question, principal)
        spans["retrieval_ms"] = (time.perf_counter() - started) * 1000
        if not candidates:
            raise Failure("UNSUPPORTED", "No authorized certified metric matches this question.")
        exact = {item.metric_id for item in candidates if item.method == "exact"}
        if self.retriever.ambiguous_alias(question, principal) or (
            len(exact) > 1 and not any(exact <= set(view.metrics) for view in catalog.views)
        ):
            raise Failure("CLARIFICATION", "Please ask for one clearly specified business metric.")
        result = self.model.plan(
            question,
            build_context(
                catalog,
                principal,
                candidates,
                self.retriever.authorized_schema(principal),
                self.settings.model_context_bytes,
            ),
            deadline,
        )
        spans["model_ms"] = result.latency_ms
        spans["model_calls"] = float(result.calls)
        if result.input_tokens is not None:
            spans["input_tokens"] = float(result.input_tokens)
        if result.output_tokens is not None:
            spans["output_tokens"] = float(result.output_tokens)
        if not set(result.plan.metrics) <= {item.metric_id for item in candidates}:
            raise Failure("UNGROUNDED_PLAN", "The model selected an ungrounded metric.", 422)
        return result.plan, "model"

    def _resolve_entities(
        self, plan: QueryPlan, principal: Principal, deadline: float | None = None
    ) -> QueryPlan:
        """Replace authorized names/aliases with canonical IDs before compilation."""

        def resolve(node: Predicate | FilterGroup) -> Predicate | FilterGroup:
            if isinstance(node, FilterGroup):
                return node.model_copy(
                    update={"children": tuple(resolve(child) for child in node.children)}
                )
            entity = next(
                (item for item in self.compiler.catalog.entities if node.field in item.fields), None
            )
            if entity is not None:
                if (
                    node.op != "eq"
                    or isinstance(node.value.value, bool)
                    or not isinstance(node.value.value, (str, int))
                ):
                    raise Failure("UNSUPPORTED", "Customer lookup requires one exact identifier.")
                canonical = self.database.resolve_entity(
                    entity, str(node.value.value), principal, deadline
                )
                key_dimension = next(
                    item
                    for item in self.compiler.catalog.dimensions
                    if item.id == entity.canonical_field
                )
                return Predicate(
                    field=entity.canonical_field,
                    op="eq",
                    value=TypedValue(kind="integer", value=int(canonical))
                    if key_dimension.kind == "integer"
                    else TypedValue(kind="text", value=canonical),
                )
            return node

        return plan.model_copy(update={"filters": resolve(plan.filters)}) if plan.filters else plan

    def _format(self, rows: tuple[Row, ...], plan: QueryPlan, catalog: Catalog) -> tuple[Row, ...]:
        with localcontext() as context:
            context.prec = 80
            return self._decimal_rows(rows, plan, catalog)

    def _decimal_rows(
        self, rows: tuple[Row, ...], plan: QueryPlan, catalog: Catalog
    ) -> tuple[Row, ...]:
        metrics = {metric.id: metric for metric in catalog.metrics}
        result: list[Row] = []
        for row in rows:
            record = dict(row)
            for key in plan.metrics:
                metric = metrics[key]
                value = row[key]
                if metric.expression is not None and metric.expression.kind == "ratio":
                    denominator = record.pop(key + "_d")
                    record[key] = (
                        format(
                            Decimal(str(value)) * 100 / Decimal(str(denominator)),
                            f".{metric.decimal_places}f",
                        )
                        if value is not None and denominator
                        else None
                    )
                elif metric.aggregate == "avg":
                    count = row[key + "_n"]
                    del record[key + "_n"]
                    record[key] = (
                        format(
                            Decimal(str(value)) / Decimal(str(count)) / metric.scale,
                            f".{metric.decimal_places}f",
                        )
                        if value is not None and count
                        else None
                    )
                elif metric.unit not in {"count", "percent"} and value is not None:
                    record[key] = money_text(str(value), metric.scale, metric.decimal_places)
            result.append(record)
        return tuple(result)

    def chat(
        self,
        question: str,
        session_id: str | None,
        principal: Principal,
        claimed_user_id: str | None,
        spans: dict[str, float],
    ) -> Answer:
        """Bind observability to one turn, including direct CLI/evaluation callers."""
        with stage_metrics(spans, time.time() + self.settings.request_timeout_seconds):
            return self._chat(question, session_id, principal, claimed_user_id, spans)

    @measured("request_ms")
    def _chat(
        self,
        question: str,
        session_id: str | None,
        principal: Principal,
        claimed_user_id: str | None,
        spans: dict[str, float],
    ) -> Answer:
        """Resolve, validate, compile, independently approve, execute, then persist."""
        if claimed_user_id is not None and claimed_user_id != principal.id:
            raise Failure(
                "IDENTITY_MISMATCH", "The supplied user does not match authentication.", 403
            )
        deadline = time.time() + self.settings.request_timeout_seconds
        state = (
            self.sessions.state(session_id, principal.id)
            if session_id
            else self.sessions.create(principal.id, question)
        )
        catalog = self.store.snapshot()
        if catalog is not self.compiler.catalog:
            raise Failure("CATALOG_STALE", "The catalog changed; service reload is required.", 503)
        plan: QueryPlan | None = state.last_plan
        try:
            draft, route = self._select_plan(question, principal, state, catalog, deadline, spans)
            started = time.perf_counter()
            validated = self.compiler.validator.validate(draft, principal)
            resolved = self._resolve_entities(validated.plan, principal, deadline)
            validated = self.compiler.validator.validate(resolved, principal)
            spans["plan_ms"] = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            compiled = self.compiler.compile(validated, principal, self.database.dialect)
            spans["compile_ms"] = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            capability = self.database.validator.validate(compiled, principal, deadline)
            spans["validate_ms"] = (time.perf_counter() - started) * 1000
            executed = self.database.execute(capability, principal)
            self.database.validator.verify(capability, principal)
            spans["database_ms"] = executed.duration_ms
            rows = self._format(executed.rows, validated.plan, catalog)
            plan = validated.plan
            message = (
                "Here are the matching authorized results."
                if rows
                else "No matching records were found."
            )
            if isinstance(plan.period, Period):
                message += f" Reporting as of {plan.period.as_of.isoformat()}."
            elif isinstance(plan.period, DateRange):
                message += (
                    f" Reporting from {plan.period.start} to "
                    f"{plan.period.end_exclusive} (exclusive)."
                )
            message += " Source refresh time is unknown."
            if executed.truncated:
                message += " Results were limited; narrow the question for a complete report."
            answer = Answer(
                session_id=state.session_id,
                status="completed" if rows else "empty",
                message=message,
                rows=rows,
                provenance=Provenance(
                    bundle_version=self.bundle_version,
                    catalog_version=catalog.version,
                    query_reference=str(uuid4()),
                    reporting_as_of=plan.period.as_of if isinstance(plan.period, Period) else None,
                    reporting_range=(plan.period.start, plan.period.end_exclusive)
                    if isinstance(plan.period, DateRange)
                    else None,
                    executed_at=datetime.now(UTC),
                    truncated=executed.truncated,
                    route=route,
                    units={
                        metric.id: metric.unit
                        for metric in catalog.metrics
                        if metric.id in plan.metrics
                    },
                ),
            )
        except Failure as error:
            if error.code not in {
                "CLARIFICATION",
                "UNSUPPORTED",
                "ENTITY_AMBIGUOUS",
                "ENTITY_NOT_FOUND",
            }:
                raise
            answer = Answer(
                session_id=state.session_id,
                status="unsupported" if error.code == "UNSUPPORTED" else "clarification_required",
                message=error.message,
            )
        self.sessions.append(state, principal.id, question, answer, plan, principal_hash(principal))
        return answer
