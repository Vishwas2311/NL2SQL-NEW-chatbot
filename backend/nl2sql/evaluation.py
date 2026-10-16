"""Independent workflow goldens; scripted plans do not measure model language skill."""

import platform
import statistics
import time
import tracemalloc
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from nl2sql.api import Resources, build_resources
from nl2sql.catalog import catalog_hash
from nl2sql.config import Settings
from nl2sql.domain import (
    DateRange,
    Failure,
    FiscalPeriod,
    FrozenModel,
    Period,
    Predicate,
    QueryPlan,
    Ranking,
    Row,
    Sort,
    TypedValue,
)
from nl2sql.model import MockModel, ModelProvider
from nl2sql.retrieval import EmbeddingProvider
from nl2sql.synthetic import initialize, synthetic_catalog


class GoldenCase(FrozenModel):
    """Expected values are hand-checked from fictional seed records, not compiler output."""

    id: str
    question: str
    expected_rows: tuple[Row, ...] = ()
    draft: QueryPlan | None = None
    principal: str = "analyst"
    expected_status: str = "completed"
    expected_error: str | None = None
    setup_question: str | None = None
    claimed_user: str | None = None


def golden_cases(version: str) -> tuple[GoldenCase, ...]:
    """Distinct aggregates, entities, dates, windows, multi-fact reports and denied requests."""

    def plan(**updates: object) -> QueryPlan:
        return QueryPlan.model_validate(
            {
                "catalog_version": version,
                "view_id": "loan_snapshot",
                "metrics": ("loan_exposure",),
                "dimensions": ("region",),
                **updates,
            }
        )

    def case(
        key: str,
        question: str,
        rows: tuple[Row, ...] = (),
        draft: QueryPlan | None = None,
        **options: object,
    ) -> GoldenCase:
        return GoldenCase.model_validate(
            {"id": key, "question": question, "expected_rows": rows, "draft": draft, **options}
        )

    def equal(field: str, value: str) -> Predicate:
        return Predicate(field=field, op="eq", value=TypedValue(kind="text", value=value))

    exposure: tuple[Row, ...] = (
        {"region": "Demo North", "loan_exposure": "175000.50"},
        {"region": "Demo South", "loan_exposure": "75000.00"},
    )
    period = DateRange(start=date(2026, 4, 1), end_exclusive=date(2026, 10, 1))

    def payment(**updates: object) -> QueryPlan:
        return plan(
            **{
                "view_id": "payment_events",
                "metrics": ("payment_amount",),
                "period": period,
                **updates,
            }
        )

    cases = [
        case("template-region", "Show total loan exposure by region", exposure),
        case("template-total", "Show total loan exposure", ({"loan_exposure": "250000.50"},)),
        case(
            "loan-count",
            "Show loan count by region",
            ({"region": "Demo North", "loan_count": 3}, {"region": "Demo South", "loan_count": 2}),
        ),
        case(
            "accounts",
            "Show account count by region",
            (
                {"region": "Demo North", "account_count": 3},
                {"region": "Demo South", "account_count": 1},
            ),
        ),
        case(
            "average",
            "Show average exposure by region",
            (
                {"region": "Demo North", "average_exposure": "58333.50"},
                {"region": "Demo South", "average_exposure": "75000.00"},
            ),
        ),
        case("paraphrase", "Summarize outstanding exposure for each region", exposure, plan()),
        case("abbreviation", "Report EOP exposure across regions", exposure, plan()),
        case(
            "mean-alias",
            "Report mean loan exposure across regions",
            (
                {"region": "Demo North", "average_exposure": "58333.50"},
                {"region": "Demo South", "average_exposure": "75000.00"},
            ),
            plan(metrics=("average_exposure",)),
        ),
        case(
            "largest",
            "Show largest exposure for every region",
            (
                {"region": "Demo North", "largest_exposure": "100000.00"},
                {"region": "Demo South", "largest_exposure": "75000.00"},
            ),
            plan(metrics=("largest_exposure",)),
        ),
        case(
            "smallest",
            "Show smallest exposure for every region",
            (
                {"region": "Demo North", "smallest_exposure": "25000.00"},
                {"region": "Demo South", "smallest_exposure": "75000.00"},
            ),
            plan(metrics=("smallest_exposure",)),
        ),
        case(
            "customer-grain",
            "Show loan exposure for each customer identifier",
            (
                {"customer_id": "C001", "loan_exposure": "125000.00"},
                {"customer_id": "C002", "loan_exposure": "50000.50"},
                {"customer_id": "C003", "loan_exposure": "75000.00"},
                {"customer_id": "C004", "loan_exposure": None},
            ),
            plan(dimensions=("customer_id",)),
        ),
        case(
            "customer-count",
            "Show loan count for each customer identifier",
            (
                {"customer_id": "C001", "loan_count": 2},
                {"customer_id": "C002", "loan_count": 1},
                {"customer_id": "C003", "loan_count": 1},
                {"customer_id": "C004", "loan_count": 1},
            ),
            plan(metrics=("loan_count",), dimensions=("customer_id",)),
        ),
        case(
            "north-scope",
            "Summarize total exposure by region for my permitted scope",
            exposure[:1],
            plan(),
            principal="north_analyst",
        ),
        case(
            "south-filter",
            "Show loan exposure in region south",
            exposure[1:],
            plan(filters=equal("region_id", "south")),
        ),
        case(
            "alias-entity",
            "Show loan exposure for Fable",
            ({"loan_exposure": "125000.00"},),
            plan(dimensions=(), filters=equal("customer", "Fable")),
        ),
        case(
            "null-amount",
            "Show loan exposure for customer C004",
            ({"loan_exposure": None},),
            plan(dimensions=(), filters=equal("customer_id", "C004")),
        ),
        case(
            "historic",
            "Show loan exposure by region at September 2025 month end",
            (
                {"region": "Demo North", "loan_exposure": "80000.00"},
                {"region": "Demo South", "loan_exposure": "60000.00"},
            ),
            plan(period=Period(as_of=date(2025, 9, 30))),
        ),
        case(
            "empty-group",
            "Show loan exposure by region at August 2026 month end",
            (),
            plan(period=Period(as_of=date(2026, 8, 31))),
            expected_status="empty",
        ),
        case(
            "empty-scalar",
            "Show total loan exposure at August 2026 month end",
            ({"loan_exposure": None},),
            plan(dimensions=(), period=Period(as_of=date(2026, 8, 31))),
        ),
        case(
            "having",
            "Show regions whose loan exposure exceeds 100000 INR",
            exposure[:1],
            plan(
                having=Predicate(
                    field="loan_exposure",
                    op="gt",
                    value=TypedValue(kind="decimal", value="100000.00"),
                )
            ),
        ),
        case(
            "top-region",
            "Show the top region by loan exposure",
            exposure[:1],
            plan(sort=(Sort(field="loan_exposure", direction="desc"),), limit=1),
        ),
        case(
            "small-region",
            "Show the smallest region by loan exposure",
            exposure[1:],
            plan(sort=(Sort(field="loan_exposure"),), limit=1),
        ),
        case(
            "event-range",
            "Show payment amount by region from April through September 2026",
            (
                {"region": "Demo North", "payment_amount": "5000.00"},
                {"region": "Demo South", "payment_amount": "4000.00"},
            ),
            payment(),
        ),
        case(
            "event-net",
            "Show net payments by region from April through September 2026",
            (
                {"region": "Demo North", "net_payments": "4950.00"},
                {"region": "Demo South", "net_payments": "3920.00"},
            ),
            payment(metrics=("net_payments",)),
        ),
        case(
            "event-percent",
            "Show fee rate by region from April through September 2026",
            (
                {"region": "Demo North", "fee_rate": "1.00"},
                {"region": "Demo South", "fee_rate": "2.00"},
            ),
            payment(metrics=("fee_rate",)),
        ),
        case(
            "zero-percent",
            "Show fee rate for customer C004 during April through September",
            ({"region": "Demo South", "fee_rate": None},),
            payment(metrics=("fee_rate",), filters=equal("customer_id", "C004")),
        ),
        case(
            "event-count",
            "Show payment count by region during April through September 2026",
            (
                {"region": "Demo North", "payment_count": 2},
                {"region": "Demo South", "payment_count": 3},
            ),
            payment(metrics=("payment_count",)),
        ),
        case(
            "fiscal-boundary",
            "Show payment amount in fiscal year starting 2025",
            ({"region": "Demo North", "payment_amount": "1000.00"},),
            payment(period=FiscalPeriod(year=2025)),
        ),
        case(
            "event-start",
            "Show payment amount on April first 2026",
            ({"region": "Demo North", "payment_amount": "2000.00"},),
            payment(period=Period(as_of=date(2026, 4, 1))),
        ),
        case(
            "event-end",
            "Show payment amount on October first 2026",
            ({"region": "Demo South", "payment_amount": "5000.00"},),
            payment(period=Period(as_of=date(2026, 10, 1))),
        ),
        case(
            "combined-facts",
            "Show loan exposure and account count by region",
            (
                {"region": "Demo North", "loan_exposure": "175000.50", "account_count": 3},
                {"region": "Demo South", "loan_exposure": "75000.00", "account_count": 1},
            ),
            plan(
                view_id="customer_portfolio",
                operation="combine",
                metrics=("loan_exposure", "account_count"),
            ),
        ),
        case(
            "combined-customer",
            "Show loan exposure and account count for Fable",
            ({"customer_id": "C001", "loan_exposure": "125000.00", "account_count": 2},),
            plan(
                view_id="customer_portfolio",
                operation="combine",
                metrics=("loan_exposure", "account_count"),
                dimensions=("customer_id",),
                filters=equal("customer", "Fable"),
            ),
        ),
        case(
            "window-global",
            "Rank regions by loan exposure and return first place",
            ({"region": "Demo North", "loan_exposure": "175000.50", "rank_value": 1},),
            plan(ranking=Ranking(metric="loan_exposure", top_n=1)),
        ),
        case(
            "window-partition",
            "Rank customer loan exposure within each region and return first place",
            (
                {
                    "region": "Demo North",
                    "customer_id": "C001",
                    "loan_exposure": "125000.00",
                    "rank_value": 1,
                },
                {
                    "region": "Demo South",
                    "customer_id": "C003",
                    "loan_exposure": "75000.00",
                    "rank_value": 1,
                },
            ),
            plan(
                dimensions=("region", "customer_id"),
                ranking=Ranking(metric="loan_exposure", partition_by=("region",), top_n=1),
            ),
        ),
        case(
            "preaggregate-cte",
            "Summarize loan exposure by region using the certified aggregate CTE",
            exposure,
            plan(operation="preaggregate"),
        ),
        case(
            "long-question",
            (
                "Please prepare a careful report of outstanding exposure "
                "for every authorized region "
                "using the certified end-of-September 2026 snapshot. "
                "Include active fictional loans "
                "only, retain exact INR amounts and do not combine balances across reporting dates."
            ),
            exposure,
            plan(),
        ),
        case(
            "followup",
            "What about 2025?",
            (
                {"region": "Demo North", "loan_exposure": "80000.00"},
                {"region": "Demo South", "loan_exposure": "60000.00"},
            ),
            setup_question="Show total loan exposure by region",
        ),
        case("ambiguous-metric", "Show exposure", expected_status="clarification_required"),
        case(
            "ambiguous-entity",
            "Show loan exposure for Cedar",
            draft=plan(filters=equal("customer", "Cedar")),
            expected_status="clarification_required",
        ),
        case(
            "unknown-entity",
            "Show loan exposure for Unknown Fiction",
            draft=plan(filters=equal("customer", "Unknown Fiction")),
            expected_status="clarification_required",
        ),
        case(
            "hidden-entity",
            "Show loan exposure for customer C003 in my scope",
            draft=plan(filters=equal("customer_id", "C003")),
            principal="north_analyst",
            expected_status="clarification_required",
        ),
        case("write-denial", "Delete all loans", expected_status="unsupported"),
        case("unsupported", "Show unicorn populations", expected_status="unsupported"),
        case(
            "identity-forgery",
            "Show total loan exposure",
            claimed_user="other",
            expected_error="IDENTITY_MISMATCH",
        ),
        case(
            "unsafe-range",
            "Sum loan exposure across 2025 and 2026",
            draft=plan(period=DateRange(start=date(2025, 1, 1), end_exclusive=date(2026, 10, 1))),
            expected_error="GRAIN_CONFLICT",
        ),
        case(
            "stale-plan",
            "Show outstanding exposure with the retired catalog",
            draft=plan(catalog_version="retired"),
            expected_error="CATALOG_STALE",
        ),
    ]
    return tuple(cases)


class CaseResult(FrozenModel):
    """One workflow outcome, with explicit denominators for aggregate scores."""

    id: str
    question: str
    status: str
    passed: bool
    eligible: bool
    answered: bool
    safe_rejection: bool
    model_calls: int
    database_calls: int
    duration_ms: float
    database_ms: float | None
    retrieval_correct: bool | None
    joins_correct: bool | None
    plan_valid: bool | None
    sql_execution_correct: bool | None


def _run_case(resources: Resources, case: GoldenCase) -> CaseResult:
    principal = resources.auth.principals[case.principal]
    session_id: str | None = None
    if case.setup_question is not None:
        session_id = resources.service.chat(
            case.setup_question, None, principal, None, {}
        ).session_id
    before = resources.database.execute_count
    spans: dict[str, float] = {}
    started = time.perf_counter()
    success = False
    status = "failed"
    joins_correct: bool | None = None
    plan_valid: bool | None = None
    try:
        answer = resources.service.chat(
            case.question, session_id, principal, case.claimed_user, spans
        )
        status = answer.status
        success = (
            case.expected_error is None
            and status == case.expected_status
            and answer.rows == case.expected_rows
        )
        if answer.provenance is not None:
            saved = resources.sessions.state(answer.session_id, principal.id).last_plan
            assert saved is not None
            proof = resources.service.compiler.validator.validate(saved, principal).proof
            plan_valid = True
            expected_edges = {"customer_region"}
            if saved.view_id in {"loan_snapshot", "customer_portfolio"}:
                expected_edges.add("loans_customer")
            if saved.view_id in {"account_current", "customer_portfolio"}:
                expected_edges.add("accounts_customer")
            if saved.view_id == "payment_events":
                expected_edges.add("payments_customer")
            joins_correct = set(proof.relationships) == expected_edges
    except Failure as error:
        status = error.code
        success = error.code == case.expected_error
    expects_answer = case.expected_error is None and case.expected_status in {"completed", "empty"}
    retrieval_correct: bool | None = None
    if case.draft is not None and case.expected_error is None:
        selected = resources.retriever.retrieve(case.question, principal)
        retrieval_correct = set(case.draft.metrics) <= {item.metric_id for item in selected}
    database_calls = resources.database.execute_count - before
    return CaseResult(
        id=case.id,
        question=case.question,
        status=status,
        passed=success,
        eligible=expects_answer,
        answered=expects_answer and status in {"completed", "empty"},
        safe_rejection=not expects_answer and success and database_calls == 0,
        model_calls=int(spans.get("model_calls", 0)),
        database_calls=database_calls,
        duration_ms=(time.perf_counter() - started) * 1000,
        database_ms=spans.get("database_ms"),
        retrieval_correct=retrieval_correct,
        joins_correct=joins_correct,
        plan_valid=plan_valid,
        sql_execution_correct=success if expects_answer and database_calls else None,
    )


def evaluate_workflows(
    root: Path,
    encoder: EmbeddingProvider | None = None,
    provider: ModelProvider | None = None,
) -> dict[str, object]:
    """Score one run per distinct case. Repeated timings are never additional questions."""
    initialize(root / "data", root / "catalog.json")
    settings = Settings.model_validate_json((root / "data/settings.json").read_text())
    cases = golden_cases(synthetic_catalog().version)
    mock = provider or MockModel(
        {case.question: case.draft.model_dump_json() for case in cases if case.draft is not None}
    )
    resources = build_resources(settings, mock, encoder)
    tracemalloc.start()
    try:
        records = [_run_case(resources, case) for case in cases]
        _, peak = tracemalloc.get_traced_memory()
        digest = catalog_hash(resources.service.store.snapshot())
    finally:
        tracemalloc.stop()
        resources.close()
    latencies = sorted(record.duration_ms for record in records)
    db_times = [record.database_ms for record in records if record.database_ms is not None]
    eligible = sum(record.eligible for record in records)
    answered = sum(record.answered for record in records)
    correct = sum(record.eligible and record.passed for record in records)
    retrieval = [
        record.retrieval_correct for record in records if record.retrieval_correct is not None
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "provider": "deterministic_mock" if provider is None else "injected_provider_unqualified",
        "provider_adapter": type(mock).__name__,
        "database": "synthetic_sqlite",
        "catalog_digest": digest,
        "distinct_questions": len(cases),
        "runs": len(records),
        "passed": sum(record.passed for record in records),
        "eligible_questions": eligible,
        "answered": answered,
        "correct_results": correct,
        "business_result_accuracy_all_eligible": correct / eligible,
        "answered_only_accuracy": correct / answered if answered else None,
        "supported_question_coverage": answered / eligible,
        "safe_rejection_rate": sum(record.safe_rejection for record in records)
        / (len(records) - eligible),
        "metric_retrieval_recall": sum(retrieval) / len(retrieval),
        "join_correctness": all(
            record.joins_correct for record in records if record.joins_correct is not None
        ),
        "plan_validity": sum(record.plan_valid is True for record in records) / eligible,
        "sql_execution_correctness": sum(record.sql_execution_correct is True for record in records)
        / eligible,
        "p50_ms": statistics.median(latencies),
        "p95_ms": latencies[max(0, int(len(latencies) * 0.95 + 0.999) - 1)],
        "database_p50_ms": statistics.median(db_times),
        "model_calls": mock.calls if isinstance(mock, MockModel) else None,
        "successful_response_model_calls": sum(record.model_calls for record in records),
        "input_tokens": None,
        "output_tokens": None,
        "python_traced_peak_bytes": peak,
        "limitations": [
            "Scripted QueryPlans do not measure Gemma natural-language accuracy.",
            "No real Oracle or A-G model ablations are measured in this workflow suite.",
            "Corpus is a local regression suite, not enterprise-held-out approval.",
        ],
        "cases": [record.model_dump() for record in records],
    }


def compare_models(
    root: Path,
    factories: dict[str, Callable[[], ModelProvider]],
) -> dict[str, object]:
    """Compare explicitly supplied adapters; no provider or network call is automatic."""
    if not factories or len(factories) > 8:
        raise ValueError("Compare between one and eight configured providers")
    return {
        "runs": {
            name: evaluate_workflows(root / str(index), provider=factory())
            for index, (name, factory) in enumerate(sorted(factories.items()))
        },
        "qualification": "Synthetic workflows include scripted invalid-output fixtures; "
        "use a separately approved held-out corpus for model promotion",
    }
