"""Independent results for the new typed temporal, formula, ranking and fact-combination paths."""

import time
from datetime import date

import pytest
from nl2sql.compiler import Compiler
from nl2sql.domain import (
    DateRange,
    Failure,
    FiscalPeriod,
    Period,
    Predicate,
    Ranking,
    TypedValue,
)
from nl2sql.planning import PlanValidator
from pydantic import ValidationError
from test_pipeline import plan_for, run_plan


def payment_plan(resources, **updates):
    values = {
        "view_id": "payment_events",
        "metrics": ["payment_amount"],
        "period": DateRange(start=date(2026, 4, 1), end_exclusive=date(2026, 10, 1)),
        **updates,
    }
    return plan_for(resources, **values)


def test_half_open_event_range_and_multiple_metrics(resources):
    plan = payment_plan(
        resources, metrics=["payment_amount", "payment_fee", "net_payments", "fee_rate"]
    )
    raw = run_plan(resources, plan)
    rows = resources.service._format(raw.rows, plan, resources.service.store.snapshot())
    assert rows == (
        {
            "region": "Demo North",
            "payment_amount": "5000.00",
            "payment_fee": "50.00",
            "net_payments": "4950.00",
            "fee_rate": "1.00",
        },
        {
            "region": "Demo South",
            "payment_amount": "4000.00",
            "payment_fee": "80.00",
            "net_payments": "3920.00",
            "fee_rate": "2.00",
        },
    )


def test_fiscal_year_uses_certified_april_boundary(resources):
    plan = plan_for(
        resources,
        view_id="payment_events",
        metrics=["payment_amount"],
        period=FiscalPeriod(year=2025),
    )
    assert run_plan(resources, plan).rows == ({"region": "Demo North", "payment_amount": 100000},)


def test_zero_ratio_denominator_is_null(resources):
    condition = Predicate(field="customer_id", op="eq", value=TypedValue(kind="text", value="C004"))
    plan = payment_plan(resources, metrics=["fee_rate"], filters=condition)
    result = run_plan(resources, plan)
    assert resources.service._format(result.rows, plan, resources.service.store.snapshot()) == (
        {"region": "Demo South", "fee_rate": None},
    )


def test_snapshot_range_retains_each_reporting_date(resources):
    plan = plan_for(
        resources,
        dimensions=["region", "reporting_date"],
        period=DateRange(start=date(2025, 9, 30), end_exclusive=date(2026, 10, 1)),
    )
    assert run_plan(resources, plan).rows == (
        {"region": "Demo North", "reporting_date": "2025-09-30", "loan_exposure": 8000000},
        {"region": "Demo North", "reporting_date": "2026-09-30", "loan_exposure": 17500050},
        {"region": "Demo South", "reporting_date": "2025-09-30", "loan_exposure": 6000000},
        {"region": "Demo South", "reporting_date": "2026-09-30", "loan_exposure": 7500000},
    )


def test_range_coverage_accepts_open_ended_catalog_without_date_overflow(resources):
    catalog = resources.service.store.snapshot().model_copy(update={"effective_to": date.max})
    plan = payment_plan(resources)
    principal = resources.auth.principals["analyst"]
    validated = PlanValidator(catalog).validate(plan, principal)
    assert validated.plan.period == plan.period


@pytest.mark.parametrize("method", ["row_number", "dense_rank"])
def test_partitioned_aggregate_ranking(resources, method):
    plan = plan_for(
        resources,
        dimensions=["region", "customer_id"],
        ranking=Ranking(metric="loan_exposure", partition_by=("region",), method=method, top_n=1),
    )
    result = run_plan(resources, plan)
    assert result.rows == (
        {"region": "Demo North", "customer_id": "C001", "loan_exposure": 12500000, "rank_value": 1},
        {"region": "Demo South", "customer_id": "C003", "loan_exposure": 7500000, "rank_value": 1},
    )


def test_dense_rank_keeps_ties(resources):
    plan = plan_for(
        resources,
        metrics=["loan_count"],
        dimensions=["region", "customer_id"],
        ranking=Ranking(
            metric="loan_count", partition_by=("region",), method="dense_rank", top_n=1
        ),
    )
    assert run_plan(resources, plan).rows == (
        {"region": "Demo North", "customer_id": "C001", "loan_count": 2, "rank_value": 1},
        {"region": "Demo South", "customer_id": "C003", "loan_count": 1, "rank_value": 1},
        {"region": "Demo South", "customer_id": "C004", "loan_count": 1, "rank_value": 1},
    )


def test_multi_fact_preaggregation_avoids_two_loans_times_two_accounts(resources):
    plan = plan_for(
        resources,
        view_id="customer_portfolio",
        operation="combine",
        metrics=["loan_exposure", "loan_count", "account_count"],
    )
    assert run_plan(resources, plan).rows == (
        {"region": "Demo North", "loan_exposure": 17500050, "loan_count": 3, "account_count": 3},
        {"region": "Demo South", "loan_exposure": 7500000, "loan_count": 2, "account_count": 1},
    )


def test_multi_fact_scope_and_typed_customer_filter(resources):
    plan = plan_for(
        resources,
        view_id="customer_portfolio",
        operation="combine",
        metrics=["loan_exposure", "account_count"],
        dimensions=["customer_id"],
        filters=Predicate(
            field="customer_id", op="eq", value=TypedValue(kind="text", value="C001")
        ),
    )
    assert run_plan(resources, plan, "north_analyst").rows == (
        {"customer_id": "C001", "loan_exposure": 12500000, "account_count": 2},
    )


@pytest.mark.parametrize(
    "case",
    [
        "snapshot_sum",
        "invalid_partition",
        "rank_average",
        "current_period",
        "range_coverage",
        "unapproved_combine",
    ],
)
def test_invalid_new_semantics_do_not_execute(resources, case):
    if case == "snapshot_sum":
        plan = plan_for(
            resources, period=DateRange(start=date(2025, 1, 1), end_exclusive=date(2026, 10, 1))
        )
    elif case == "invalid_partition":
        plan = plan_for(
            resources,
            ranking=Ranking(metric="loan_exposure", partition_by=("customer_id",), top_n=1),
        )
    elif case == "rank_average":
        plan = plan_for(
            resources,
            metrics=["average_exposure"],
            ranking=Ranking(metric="average_exposure", top_n=1),
        )
    elif case == "current_period":
        plan = plan_for(
            resources,
            view_id="account_current",
            metrics=["account_count"],
            period=Period(as_of=date(2026, 9, 30)),
        )
    elif case == "range_coverage":
        plan = payment_plan(
            resources, period=DateRange(start=date(2020, 1, 1), end_exclusive=date(2026, 10, 1))
        )
    else:
        plan = plan_for(resources, operation="combine")
    before = resources.database.execute_count
    with pytest.raises(Failure):
        run_plan(resources, plan)
    assert resources.database.execute_count == before


@pytest.mark.parametrize("operation", ["rank", "combine", "ratio", "range"])
@pytest.mark.parametrize("dialect", ["sqlite", "oracle"])
def test_extended_operator_dialects_and_sql_tamper_rejection(resources, operation, dialect):
    if operation == "rank":
        plan = plan_for(resources, ranking=Ranking(metric="loan_exposure", top_n=1))
    elif operation == "combine":
        plan = plan_for(
            resources,
            view_id="customer_portfolio",
            operation="combine",
            metrics=["loan_exposure", "account_count"],
        )
    elif operation == "ratio":
        plan = payment_plan(resources, metrics=["fee_rate"])
    else:
        plan = payment_plan(resources)
    catalog = resources.service.store.snapshot()
    principal = resources.auth.principals["analyst"]
    query = Compiler(catalog).compile(
        PlanValidator(catalog).validate(plan, principal), principal, dialect
    )
    validator = resources.database.validator
    validator.validate(query, principal, time.time() + 10)
    tampered = query.model_copy(
        update={"sql": query.sql.replace('"tenant_id" = :', '"customer_id" = :')}
    )
    with pytest.raises(Failure):
        validator.validate(tampered, principal, time.time() + 10)


def test_range_contract_rejects_reversed_dates():
    with pytest.raises(ValidationError):
        DateRange(start=date(2026, 10, 1), end_exclusive=date(2026, 4, 1))


def test_combined_current_accounts_cannot_be_presented_as_historical(resources):
    plan = plan_for(
        resources,
        view_id="customer_portfolio",
        operation="combine",
        metrics=["loan_exposure", "account_count"],
        period=Period(as_of=date(2025, 9, 30)),
    )
    with pytest.raises(Failure, match="historical"):
        run_plan(resources, plan)
    assert resources.database.execute_count == 0


@pytest.mark.parametrize("change", ["units", "time", "dependency", "output_scale"])
def test_invalid_derived_metric_contracts_never_activate(resources, change):
    from nl2sql.catalog import validate_catalog

    catalog = resources.service.store.snapshot()
    metrics = []
    for metric in catalog.metrics:
        if metric.id == "payment_fee":
            if change == "units":
                metric = metric.model_copy(update={"scale": 1})
            if change == "time":
                metric = metric.model_copy(update={"temporal": "current"})
        if metric.id == "fee_rate":
            if change == "dependency":
                metric = metric.model_copy(
                    update={
                        "expression": metric.expression.model_copy(update={"numerator": "fee_rate"})
                    }
                )
            if change == "output_scale":
                metric = metric.model_copy(update={"scale": 100})
        metrics.append(metric)
    with pytest.raises(ValueError):
        validate_catalog(catalog.model_copy(update={"metrics": tuple(metrics)}))


@pytest.mark.parametrize("dialect", ["sqlite", "oracle"])
def test_aggregate_cte_rejects_modified_outer_projection(resources, dialect):
    import sqlglot
    from sqlglot import exp

    principal = resources.auth.principals["analyst"]
    query = run_plan(resources, plan_for(resources, operation="preaggregate"), dialect="oracle")
    if dialect == "sqlite":
        catalog = resources.service.store.snapshot()
        query = Compiler(catalog).compile(query.validated_plan, principal)
    tree = sqlglot.parse_one(query.sql, read=dialect)
    tree.set(
        "expressions",
        [
            exp.column("region", table="wrong_source", quoted=True),
            exp.column("loan_exposure", quoted=True),
        ],
    )
    with pytest.raises(Failure):
        resources.database.validator.validate(
            query.model_copy(update={"sql": tree.sql(dialect=dialect)}), principal, time.time() + 5
        )
