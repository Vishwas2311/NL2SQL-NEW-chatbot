"""Known-answer SQL, temporal, grain, null, sorting and predicate regression tests."""

import time
from datetime import date

import pytest
from nl2sql.application.query.compiler import Compiler
from nl2sql.application.query.planning import PlanValidator
from nl2sql.domain.models import FilterGroup, Period, Predicate, QueryPlan, Sort, TypedValue


def plan_for(resources, **updates) -> QueryPlan:
    catalog = resources.service.store.snapshot()
    return QueryPlan.model_validate(
        {
            "catalog_version": catalog.version,
            "view_id": "loan_snapshot",
            "metrics": ["loan_exposure"],
            "dimensions": ["region"],
            **updates,
        }
    )


def run_plan(resources, plan, identity="analyst", dialect="sqlite"):
    principal = resources.auth.principals[identity]
    catalog = resources.service.store.snapshot()
    validated = PlanValidator(catalog).validate(plan, principal)
    compiled = Compiler(catalog).compile(validated, principal, dialect)
    capability = resources.database.validator.validate(compiled, principal, time.time() + 5)
    if dialect == "oracle":
        return compiled
    return resources.database.execute(capability, principal)


def test_exposure_result_and_zero_model_calls(resources):
    answer = resources.service.chat(
        "Show total loan exposure by region",
        None,
        resources.auth.principals["analyst"],
        "analyst",
        {},
    )
    assert answer.rows == (
        {"region": "Demo North", "loan_exposure": "175000.50"},
        {"region": "Demo South", "loan_exposure": "75000.00"},
    )
    assert answer.provenance.route == "template"
    assert resources.model.calls == 0


@pytest.mark.parametrize(
    "metric,expected",
    [
        ("loan_count", (3, 2)),
        ("largest_exposure", (10000000, 7500000)),
        ("smallest_exposure", (2500000, 7500000)),
    ],
)
def test_aggregates(resources, metric, expected):
    result = run_plan(resources, plan_for(resources, metrics=[metric]))
    assert tuple(row[metric] for row in result.rows) == expected


def test_null_and_average_financial_precision(resources):
    answer = resources.service.chat(
        "Show average exposure by region", None, resources.auth.principals["analyst"], None, {}
    )
    assert answer.rows == (
        {"region": "Demo North", "average_exposure": "58333.50"},
        {"region": "Demo South", "average_exposure": "75000.00"},
    )


def test_account_view_does_not_join_loan_facts(resources):
    plan = plan_for(resources, view_id="account_current", metrics=["account_count"])
    result = run_plan(resources, plan)
    assert result.rows == (
        {"region": "Demo North", "account_count": 3},
        {"region": "Demo South", "account_count": 1},
    )


def test_historical_snapshot_and_followup(resources):
    owner = resources.auth.principals["analyst"]
    first = resources.service.chat("Show total loan exposure by region", None, owner, None, {})
    second = resources.service.chat("what about 2025?", first.session_id, owner, None, {})
    assert second.rows == (
        {"region": "Demo North", "loan_exposure": "80000.00"},
        {"region": "Demo South", "loan_exposure": "60000.00"},
    )
    assert second.provenance.reporting_as_of == date(2025, 9, 30)
    assert second.provenance.route == "followup"


def test_region_policy_and_composite_tenant_keys(resources):
    result = run_plan(resources, plan_for(resources), "north_analyst")
    assert result.rows == ({"region": "Demo North", "loan_exposure": 17500050},)


def test_filters_having_and_limit(resources):
    plan = plan_for(
        resources,
        having=Predicate(
            field="loan_exposure", op="gt", value=TypedValue(kind="decimal", value="100000.00")
        ),
        sort=[Sort(field="loan_exposure", direction="desc")],
        limit=1,
    )
    result = run_plan(resources, plan)
    assert result.rows == ({"region": "Demo North", "loan_exposure": 17500050},)
    assert not result.truncated


def test_nested_boolean_filter(resources):
    condition = FilterGroup(
        op="or",
        children=(
            Predicate(field="region_id", op="eq", value=TypedValue(kind="text", value="north")),
            FilterGroup(
                op="and",
                children=(
                    Predicate(
                        field="region_id", op="eq", value=TypedValue(kind="text", value="south")
                    ),
                    Predicate(
                        field="customer_id", op="eq", value=TypedValue(kind="text", value="C003")
                    ),
                ),
            ),
        ),
    )
    result = run_plan(resources, plan_for(resources, filters=condition))
    assert result.rows == (
        {"region": "Demo North", "loan_exposure": 17500050},
        {"region": "Demo South", "loan_exposure": 7500000},
    )


def test_bound_sql_injection_returns_no_rows(resources):
    value = "north') OR 1=1 --"
    plan = plan_for(
        resources,
        filters=Predicate(field="region_id", op="eq", value=TypedValue(kind="text", value=value)),
    )
    assert run_plan(resources, plan).rows == ()
    compiled = run_plan(resources, plan, dialect="oracle")
    assert value not in compiled.sql
    assert value in dict(compiled.binds).values()


def test_cte_aggregate_preserves_grain(resources):
    result = run_plan(resources, plan_for(resources, operation="preaggregate"))
    assert result.rows == (
        {"region": "Demo North", "loan_exposure": 17500050},
        {"region": "Demo South", "loan_exposure": 7500000},
    )


def test_truncated_result_is_explicit(resources):
    result = run_plan(resources, plan_for(resources, limit=1))
    assert len(result.rows) == 1
    assert result.truncated


@pytest.mark.parametrize(
    "op,value,expected",
    [
        ("in", TypedValue(kind="text_list", value=("north",)), 1),
        ("is_null", TypedValue(kind="null", value=None), 0),
        ("is_not_null", TypedValue(kind="null", value=None), 2),
        ("ne", TypedValue(kind="text", value="north"), 1),
    ],
)
def test_typed_predicates(resources, op, value, expected):
    result = run_plan(
        resources, plan_for(resources, filters=Predicate(field="region_id", op=op, value=value))
    )
    assert len(result.rows) == expected


@pytest.mark.parametrize(
    "metric",
    ["loan_exposure", "loan_count", "largest_exposure", "smallest_exposure", "average_exposure"],
)
def test_oracle_parser_rendering_only(resources, metric):
    compiled = run_plan(resources, plan_for(resources, metrics=[metric]), dialect="oracle")
    assert "FETCH FIRST" in compiled.sql
    assert ":p0" in compiled.sql
    assert '"tenant_id"' in compiled.sql


def test_scalar_empty_aggregate_is_null_not_fabricated_zero(resources):
    plan = plan_for(resources, dimensions=[], period=Period(as_of=date(2026, 8, 31)))
    assert run_plan(resources, plan).rows == ({"loan_exposure": None},)
