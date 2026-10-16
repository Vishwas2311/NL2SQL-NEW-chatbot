"""Negative cases assert no unsafe draft reaches business database execution."""

import time
from datetime import date

import pytest
from nl2sql.compiler import Compiler
from nl2sql.domain import Failure, Period, Predicate, Sort, TypedValue
from nl2sql.planning import PlanValidator
from pydantic import ValidationError
from test_pipeline import plan_for


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"catalog_version": "old"}, "CATALOG_STALE"),
        ({"view_version": "old"}, "VIEW_STALE"),
        ({"metrics": ["invented_metric"]}, "DENIED"),
        ({"dimensions": ["private_salary"]}, "GRAIN_CONFLICT"),
        ({"view_id": "account_current"}, "UNKNOWN_METRIC"),
        ({"period": Period(as_of=date(2020, 1, 1))}, "TIME_UNSUPPORTED"),
        ({"sort": [Sort(field="private_salary")]}, "INVALID_SORT"),
        (
            {"metrics": ["average_exposure"], "operation": "preaggregate"},
            "UNSUPPORTED_COMPILER_OPERATOR",
        ),
        (
            {"metrics": ["average_exposure"], "sort": [Sort(field="average_exposure")]},
            "UNSUPPORTED_COMPILER_OPERATOR",
        ),
    ],
)
def test_invalid_plans_never_execute(resources, updates, code):
    before = resources.database.execute_count
    with pytest.raises(Failure) as error:
        PlanValidator(resources.service.store.snapshot()).validate(
            plan_for(resources, **updates), resources.auth.principals["analyst"]
        )
    assert error.value.code == code
    assert resources.database.execute_count == before


@pytest.mark.parametrize(
    "value",
    [
        TypedValue(kind="decimal", value="NaN"),
        TypedValue(kind="decimal", value="1.001"),
        TypedValue(kind="text", value="1 OR 1=1"),
        TypedValue(kind="decimal", value="1e999999999"),
    ],
)
def test_invalid_monetary_having(resources, value):
    plan = plan_for(resources, having=Predicate(field="loan_exposure", op="gt", value=value))
    with pytest.raises(Failure):
        PlanValidator(resources.service.store.snapshot()).validate(
            plan, resources.auth.principals["analyst"]
        )


@pytest.mark.parametrize(
    "update",
    [
        {"limit": 0},
        {"limit": 1001},
        {"limit": True},
        {"sql": "SELECT * FROM private"},
        {"tenant_id": "other"},
        {"metrics": ["loan_exposure", "loan_exposure"]},
        {"operation": "arbitrary_sql"},
        {"schema_version": "2.0"},
    ],
)
def test_plan_structure_rejects_untrusted_fields(resources, update):
    with pytest.raises(ValidationError):
        plan_for(resources, **update)


@pytest.mark.parametrize(
    "attack",
    [
        "SELECT * FROM customers",
        "DELETE FROM loans",
        "SELECT 1; DROP TABLE loans",
        "SELECT load_extension('evil')",
        "SELECT * FROM loans UNION SELECT * FROM accounts",
        "WITH secret AS (SELECT * FROM customers) SELECT * FROM secret",
        "SELECT * FROM loans@external",
        "SELECT * FROM loans CROSS JOIN accounts",
        "SELECT * FROM loans FOR UPDATE",
        "SELECT readfile('/etc/passwd')",
    ],
)
def test_unsafe_sql_rejected_without_execution(resources, attack):
    principal = resources.auth.principals["analyst"]
    validated = PlanValidator(resources.service.store.snapshot()).validate(
        plan_for(resources), principal
    )
    draft = Compiler(resources.service.store.snapshot()).compile(validated, principal)
    before = resources.database.execute_count
    with pytest.raises(Failure):
        resources.database.validator.validate(
            draft.model_copy(update={"sql": attack}), principal, time.time() + 5
        )
    assert resources.database.execute_count == before


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_join",
        "or_join",
        "missing_policy",
        "wrong_metric",
        "wrong_bind",
        "wrong_limit",
        "comment",
    ],
)
def test_semantic_tampering_rejected(resources, mutation):
    principal = resources.auth.principals["analyst"]
    catalog = resources.service.store.snapshot()
    draft = Compiler(catalog).compile(
        PlanValidator(catalog).validate(plan_for(resources), principal), principal
    )
    sql = draft.sql
    if mutation == "wrong_join":
        sql = sql.replace(
            '"loans"."customer_id" = "customers"."customer_id"',
            '"loans"."loan_id" = "customers"."customer_id"',
        )
    elif mutation == "or_join":
        sql = sql.replace('"tenant_id" AND', '"tenant_id" OR')
    elif mutation == "missing_policy":
        sql = sql.replace('"loans"."tenant_id" = :p0', '"loans"."tenant_id" = :p1')
    elif mutation == "wrong_metric":
        sql = sql.replace("SUM(", "MAX(")
    elif mutation == "wrong_bind":
        draft = draft.model_copy(
            update={
                "binds": tuple(
                    (key, "other" if key == "p0" else value) for key, value in draft.binds
                )
            }
        )
    elif mutation == "wrong_limit":
        sql = sql.replace("LIMIT 101", "LIMIT 999")
    else:
        sql += " -- approved"
    with pytest.raises(Failure):
        resources.database.validator.validate(
            draft.model_copy(update={"sql": sql}), principal, time.time() + 5
        )


@pytest.mark.parametrize("dialect", ["sqlite", "oracle"])
@pytest.mark.parametrize("mutation", ["null_order", "qualified_column", "not_null_value"])
def test_remaining_ast_semantics_are_independent_of_compiler(resources, dialect, mutation):
    import sqlglot
    from sqlglot import exp

    catalog = resources.service.store.snapshot()
    principal = resources.auth.principals["analyst"]
    plan = plan_for(
        resources,
        filters=Predicate(
            field="customer_id", op="is_not_null", value=TypedValue(kind="null", value=None)
        ),
    )
    query = Compiler(catalog).compile(
        PlanValidator(catalog).validate(plan, principal), principal, dialect
    )
    validator = resources.database.validator
    validator.validate(query, principal, time.time() + 5)
    tree = sqlglot.parse_one(query.sql, read=dialect)
    if mutation == "null_order":
        next(tree.find_all(exp.Ordered)).set("nulls_first", True)
    elif mutation == "qualified_column":
        next(tree.find_all(exp.Column)).set("db", exp.to_identifier("another_schema"))
    else:
        next(tree.find_all(exp.Not)).this.set("expression", exp.Placeholder(this="p0"))
    before = resources.database.execute_count
    with pytest.raises(Failure):
        validator.validate(
            query.model_copy(update={"sql": tree.sql(dialect=dialect)}), principal, time.time() + 5
        )
    assert resources.database.execute_count == before


def test_capability_signature_expiry_principal_and_permission_change(resources):
    principal = resources.auth.principals["analyst"]
    catalog = resources.service.store.snapshot()
    draft = Compiler(catalog).compile(
        PlanValidator(catalog).validate(plan_for(resources), principal), principal
    )
    cap = resources.database.validator.validate(draft, principal, time.time() + 5)
    changed = principal.model_copy(update={"regions": ("north",)})
    for candidate, user in (
        (cap.model_copy(update={"signature": "fake"}), principal),
        (cap.model_copy(update={"expires_at": 0}), principal),
        (cap, resources.auth.principals["north_analyst"]),
        (cap, changed),
    ):
        with pytest.raises(Failure):
            resources.database.execute(candidate, user)
    assert resources.database.execute_count == 0


def test_deadline_exhausted_before_capability_issued(resources):
    principal = resources.auth.principals["analyst"]
    catalog = resources.service.store.snapshot()
    draft = Compiler(catalog).compile(
        PlanValidator(catalog).validate(plan_for(resources), principal), principal
    )
    with pytest.raises(Failure, match="deadline"):
        resources.database.validator.validate(draft, principal, time.time() - 1)
