"""Authenticated application pipeline; no business logic in transport routers."""

import re
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from nl2sql.application.context import build_context
from nl2sql.application.graph import GraphTraversal
from nl2sql.application.inference import InferencePlanner
from nl2sql.application.ports import (
    Candidate,
    QueryExecutor,
    SchemaRetriever,
    SessionRepository,
)
from nl2sql.application.query.compiler import Compiler
from nl2sql.application.query.planning import PlanValidator, principal_hash
from nl2sql.application.query.security import SQLValidator
from nl2sql.application.results import format_rows
from nl2sql.application.routing import certified_template, followup
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
    TypedValue,
)
from nl2sql.domain.planning import ClarificationRequest, PendingQuestion
from nl2sql.domain.sessions import SessionState
from nl2sql.settings import Settings
from nl2sql.telemetry import REQUEST_DEADLINE, measured, stage_metrics


class ChatService:
    """One complete compiler-first use case, with safe follow-up context reduction."""

    def __init__(
        self,
        settings: Settings,
        catalog: Catalog,
        retriever: SchemaRetriever,
        model: InferencePlanner,
        database: QueryExecutor,
        sessions: SessionRepository,
        *,
        sql_validator: SQLValidator,
        traversal: GraphTraversal | None = None,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.model = model
        self.database = database
        self.sql_validator = sql_validator
        self.sessions = sessions
        self.compiler = Compiler(
            catalog,
            PlanValidator(
                catalog,
                settings.max_rows,
                settings.max_metrics,
                settings.max_dimensions,
                settings.max_join_edges,
                traversal,
            ),
            sql_validator.bundle_version,
        )

    @property
    def bundle_version(self) -> str:
        """Provenance is owned by the same pinned compiler that generates the query."""
        return self.compiler.bundle_version

    def _select_plan(
        self,
        question: str,
        principal: Principal,
        state: SessionState,
        catalog: Catalog,
        deadline: float,
        spans: dict[str, float],
    ) -> tuple[QueryPlan | ClarificationRequest, Literal["template", "model", "followup"]]:
        carried = followup(question, state, catalog)
        if carried is not None:
            return carried, "followup"
        template = certified_template(question, catalog)
        if template is not None:
            return template, "template"
        if re.match(
            r"^\s*(?:please\s+)?(?:"
            r"(?:delete|drop|truncate|insert)\s+"
            r"(?:all|from|into|table|view|index|schema|database|rows|records)\b"
            r"|update\s+\S+\s+set\b"
            r"|grant\s+(?:access|select|insert|update|delete|all|execute)\b"
            r"|execute\s+(?:immediate|procedure|package)\b)",
            question,
            re.I,
        ):
            raise Failure("UNSUPPORTED", "Only approved read-only business reports are supported.")
        if state.scope_digest != principal_hash(principal):
            state = state.model_copy(update={"last_plan": None, "pending": None})
        started = time.perf_counter()
        referential = bool(re.search(r"\b(that|those|same|instead|break|now|it)\b", question, re.I))
        if referential and state.last_plan is None and state.pending is None:
            raise Failure("CLARIFICATION", "Ask a complete question with the metric and period.")
        retrieval_text = (state.pending.question + " " + question) if state.pending else question
        candidates = self.retriever.retrieve(retrieval_text, principal)
        if referential and state.last_plan is not None:
            candidates = tuple(
                dict(
                    (item.metric_id, item)
                    for item in (
                        *candidates,
                        *(Candidate(key, "followup", 1.0) for key in state.last_plan.metrics),
                    )
                ).values()
            )
        spans["retrieval_ms"] = (time.perf_counter() - started) * 1000
        if not candidates:
            raise Failure("UNSUPPORTED", "No authorized certified metric matches this question.")
        exact = {item.metric_id for item in candidates if item.method == "exact"}
        words = set(normalize(question).split()) - {
            "show",
            "give",
            "me",
            "the",
            "what",
            "is",
            "please",
        }
        grounded = {item.metric_id for item in candidates}
        meanings = [
            metric
            for metric in catalog.metrics
            if metric.id in grounded
            and words
            and words <= set(normalize(" ".join((metric.label, *metric.aliases))).split())
        ]
        if not exact and len(words) <= 1 < len(meanings):
            raise Failure("CLARIFICATION", "Specify the certified business metric and period.")
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
                state.last_plan,
                state.pending,
                self.settings.model_output_mode != "json_schema",
            ),
            deadline,
            principal,
        )
        spans["model_ms"] = result.latency_ms
        spans["model_calls"] = float(result.calls)
        if result.input_tokens is not None:
            spans["input_tokens"] = float(result.input_tokens)
        if result.output_tokens is not None:
            spans["output_tokens"] = float(result.output_tokens)
        if isinstance(result.plan, ClarificationRequest):
            if not set(result.plan.metric_ids) <= grounded:
                raise Failure(
                    "UNGROUNDED_PLAN",
                    "The clarification selected an unavailable metric.",
                    "invalid",
                )
            return result.plan, "model"
        if not set(result.plan.metrics) <= grounded:
            raise Failure("UNGROUNDED_PLAN", "The model selected an ungrounded metric.", "invalid")
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

    def chat(
        self,
        question: str,
        session_id: str | None,
        principal: Principal,
        claimed_user_id: str | None,
        spans: dict[str, float],
    ) -> Answer:
        """Bind observability to one turn, including direct CLI/evaluation callers."""
        deadline = min(
            REQUEST_DEADLINE.get() or float("inf"),
            time.time() + self.settings.request_timeout_seconds,
        )
        with stage_metrics(spans, deadline):
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
                "IDENTITY_MISMATCH", "The supplied user does not match authentication.", "denied"
            )
        if not principal.metrics:
            raise Failure(
                "DENIED", "No certified reporting metrics are currently authorized.", "denied"
            )
        deadline = REQUEST_DEADLINE.get() or time.time() + self.settings.request_timeout_seconds
        state = (
            self.sessions.state(session_id, principal.id)
            if session_id
            else self.sessions.create(principal.id, question)
        )
        catalog = self.compiler.catalog
        if (state.last_plan is not None and state.last_plan.catalog_version != catalog.version) or (
            state.last_plan is not None
            and not set(state.last_plan.metrics) <= set(principal.metrics)
        ):
            state = state.model_copy(update={"last_plan": None, "pending": None})
        if state.scope_digest != principal_hash(principal) or (
            state.pending is not None and state.pending.catalog_version != catalog.version
        ):
            state = state.model_copy(update={"pending": None})
        if state.last_plan is not None:
            try:
                self.compiler.validator.validate(state.last_plan, principal)
            except Failure:
                state = state.model_copy(update={"last_plan": None, "pending": None})
        plan: QueryPlan | None = state.last_plan
        pending: PendingQuestion | None = None
        try:
            draft, route = self._select_plan(question, principal, state, catalog, deadline, spans)
            if isinstance(draft, ClarificationRequest):
                pending = PendingQuestion(
                    question=state.pending.question if state.pending else question,
                    catalog_version=catalog.version,
                    metric_ids=draft.metric_ids,
                )
                prompts = {
                    "metric": "Specify the business metric you want to report.",
                    "period": "Specify the reporting date or date range.",
                    "dimension": "Specify how the results should be grouped.",
                    "filter": "Specify the filter and its exact value.",
                    "entity": "Specify the exact authorized entity name or identifier.",
                }
                raise Failure("CLARIFICATION", prompts[draft.reason])
            started = time.perf_counter()
            validated = self.compiler.validator.validate(draft, principal)
            resolved = self._resolve_entities(validated.plan, principal, deadline)
            validated = self.compiler.validator.validate(resolved, principal)
            spans["plan_ms"] = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            compiled = self.compiler.compile(validated, principal, self.database.dialect)
            spans["compile_ms"] = (time.perf_counter() - started) * 1000
            started = time.perf_counter()
            capability = self.sql_validator.validate(compiled, principal, deadline)
            spans["validate_ms"] = (time.perf_counter() - started) * 1000
            executed = self.database.execute(capability, principal)
            self.sql_validator.verify(capability, principal)
            spans["database_ms"] = executed.duration_ms
            rows = format_rows(executed.rows, validated.plan, catalog)
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
        self.sessions.append(
            state, principal.id, question, answer, plan, principal_hash(principal), pending
        )
        return answer
