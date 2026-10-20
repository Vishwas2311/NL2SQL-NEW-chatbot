"""Owner-qualified Oracle AST and exact decimal contracts use fictional driver fixtures."""

import time
from decimal import Decimal, localcontext

import oracledb
import pytest
from nl2sql.application.catalog import validate_catalog
from nl2sql.application.chat import ChatService
from nl2sql.application.query.compiler import Compiler
from nl2sql.application.query.entity_lookup import entity_query
from nl2sql.application.query.planning import PlanValidator
from nl2sql.application.query.security import SQLValidator
from nl2sql.domain.models import Catalog, Failure, Predicate, QueryPlan, TypedValue
from nl2sql.infrastructure.databases.oracle import OracleAdapter, OracleConfig
from nl2sql.infrastructure.databases.oracle_factory import (
    DBAContextPolicy,
    OracleExecutionSettings,
    oracle_executor,
)
from nl2sql.infrastructure.metadata.catalog_store import CatalogStore

from tests.contracts.test_oracle_adapter import FakeConnection, FakePolicy, FakePool


def oracle_catalog(settings):
    catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
    tables = tuple(
        table.model_copy(
            update={
                "physical_owner": "Fictional Office",
                "physical_name": table.id.title() + " Ledger",
                "columns": tuple(
                    column.model_copy(
                        update={
                            "physical_name": column.name.title().replace("_", " "),
                            "kind": "decimal"
                            if (table.id, column.name) == ("loans", "amount_minor")
                            else column.kind,
                        }
                    )
                    for column in table.columns
                ),
            }
        )
        for table in catalog.tables
    )
    metrics = tuple(
        metric.model_copy(update={"scale": 1, "unit": "USD", "decimal_places": 6})
        if metric.table == "loans" and metric.unit != "count"
        else metric
        for metric in catalog.metrics
    )
    return catalog.model_copy(
        update={"tables": tables, "metrics": metrics, "classification": "restricted"}
    )


@pytest.mark.parametrize("precision", [6, 28])
@pytest.mark.parametrize("scale", [1, 1_000_000_000])
def test_decimal_threshold_keeps_all_digits_in_compiler_and_validator(settings, precision, scale):
    catalog = oracle_catalog(settings)
    catalog = catalog.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"scale": scale})
                if metric.id == "loan_exposure"
                else metric
                for metric in catalog.metrics
            )
        }
    )
    value = "12345678901234567890123456789012.123456"
    expected = value if scale == 1 else "12345678901234567890123456789012123456000.000000"
    principal = settings.principals[0]
    compiler = Compiler(catalog)
    plan = QueryPlan(
        catalog_version=catalog.version,
        view_id="loan_snapshot",
        metrics=("loan_exposure",),
        having=Predicate(
            field="loan_exposure", op="gt", value=TypedValue(kind="decimal", value=value)
        ),
    )
    with localcontext() as context:
        context.prec = precision
        query = compiler.compile(compiler.validator.validate(plan, principal), principal, "oracle")
        assert expected in dict(query.binds).values()
        validator = SQLValidator(catalog, b"k" * 32)
        validator.validate(query, principal, time.time() + 5)
        rounded = query.model_copy(
            update={
                "binds": tuple(
                    (key, "12345678901234567890123456790000") if bound == expected else (key, bound)
                    for key, bound in query.binds
                )
            }
        )
        with pytest.raises(Failure):
            validator.validate(rounded, principal, time.time() + 5)


def test_oracle_exact_names_major_units_decimal_binds_and_independent_ast(settings, resources):
    catalog = oracle_catalog(settings)
    validate_catalog(catalog)
    principal = settings.principals[0]
    plan = QueryPlan(
        catalog_version=catalog.version,
        view_id="loan_snapshot",
        metrics=("loan_exposure",),
        dimensions=("region",),
        having=Predicate(
            field="loan_exposure", op="gt", value=TypedValue(kind="decimal", value="10.01")
        ),
    )
    compiler = Compiler(catalog)
    query = compiler.compile(compiler.validator.validate(plan, principal), principal, "oracle")
    assert '"Fictional Office"."Loans Ledger" "loans"' in query.sql
    assert '"loans"."Amount Minor"' in query.sql
    assert "10.01" not in query.sql
    assert "decimal" in dict(query.bind_types).values()
    validator = SQLValidator(catalog, b"k" * 32)
    capability = validator.validate(query, principal, time.time() + 5)
    raw = Decimal("12345678901234567890123456789012.123456")
    connection = FakeConnection(rows=[("Demo North", raw)])
    adapter = OracleAdapter(
        OracleConfig(
            dsn="synthetic", user="synthetic", password="synthetic", approved_test_environment=True
        ),
        validator,
        FakePolicy(),
        FakePool(connection),
    )
    try:
        result = adapter.execute(capability, principal)
        assert Decimal("10.01") in connection.calls[1][1].values()
        service = ChatService(
            settings,
            CatalogStore.from_snapshot(catalog),
            resources.retriever,
            resources.model,
            adapter,
            resources.sessions,
        )
        output = service._format(result.rows, plan, catalog)
        assert output[0]["loan_exposure"] == "12345678901234567890123456789012.123456"
        tampered = query.model_copy(
            update={"sql": query.sql.replace('"Loans Ledger"', '"Private Ledger"')}
        )
        with pytest.raises(Failure):
            validator.validate(tampered, principal, time.time() + 5)
    finally:
        adapter.close()
    with pytest.raises(Failure, match="decimal-source"):
        compiler.compile(compiler.validator.validate(plan, principal), principal, "sqlite")


def test_numeric_entity_id_does_not_coerce_label_to_oracle_number(settings):
    catalog = oracle_catalog(settings)
    entity = catalog.entities[0]
    tables = tuple(
        table.model_copy(
            update={
                "columns": tuple(
                    column.model_copy(update={"kind": "integer"})
                    if column.name == entity.key_column
                    else column
                    for column in table.columns
                )
            }
        )
        if table.id == entity.table
        else table
        for table in catalog.tables
    )
    catalog = catalog.model_copy(update={"tables": tables})
    sql, values = entity_query(catalog, entity, "Fictional Alice", settings.principals[0], "oracle")
    assert '"customers"."Customer Id" = ' not in sql
    assert "entity_key" not in values
    _, numeric = entity_query(catalog, entity, "1234", settings.principals[0], "oracle")
    assert numeric["entity_key"] == 1234 and numeric["phrase"] == "1234"


def test_configured_plan_budgets_and_reserved_identifiers(settings):
    catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
    plan = QueryPlan(
        catalog_version=catalog.version,
        view_id="loan_snapshot",
        metrics=("loan_exposure", "loan_count"),
        dimensions=("region",),
    )
    with pytest.raises(Failure, match="selected"):
        PlanValidator(catalog, max_metrics=1).validate(plan, settings.principals[0])
    with pytest.raises(Failure, match="join budget"):
        PlanValidator(catalog, max_join_edges=0).validate(plan, settings.principals[0])
    collision = catalog.model_copy(
        update={
            "tables": (
                catalog.tables[0].model_copy(update={"id": "component_0"}),
                *catalog.tables[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="CTE"):
        validate_catalog(collision)


def test_oracle_query_approval_precedes_pool_and_context_calls_are_bound(resources, monkeypatch):
    calls = []

    def forbidden(**_):
        raise AssertionError("Pool created before authorization")

    monkeypatch.setattr("nl2sql.infrastructure.databases.oracle.oracledb.create_pool", forbidden)
    with pytest.raises(Failure, match="approval"):
        oracle_executor(resources.database.validator, OracleExecutionSettings())

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def callproc(self, name, parameters=None):
            calls.append((name, parameters))

    class Connection:
        def cursor(self):
            return Cursor()

    policy = DBAContextPolicy("FICTIONAL.NL2SQL_CTX.APPLY", "FICTIONAL.NL2SQL_CTX.RESET")
    policy.apply(Connection(), resources.auth.principals["analyst"])
    policy.reset(Connection())
    assert calls[0][0] == "FICTIONAL.NL2SQL_CTX.APPLY"
    assert calls[0][1][0] == "analyst"
    assert calls[1] == ("FICTIONAL.NL2SQL_CTX.RESET", None)
    with pytest.raises(ValueError):
        DBAContextPolicy("FICTIONAL.BAD;DROP", "FICTIONAL.NL2SQL_CTX.RESET")


def test_oracle_pool_initialization_failure_is_safe(resources, monkeypatch):
    def unavailable(**_):
        raise oracledb.DatabaseError("PRIVATE_DSN_AND_PASSWORD")

    monkeypatch.setattr("nl2sql.infrastructure.databases.oracle.oracledb.create_pool", unavailable)
    settings = OracleExecutionSettings(
        approved_environment=True,
        owner_authorized=True,
        network_authorized=True,
        readonly_grants_verified=True,
        context_procedures_verified=True,
        dsn="fictional",
        user="fictional",
        password="fictional",
        apply_procedure="FICTIONAL.CTX.APPLY",
        reset_procedure="FICTIONAL.CTX.RESET",
    )
    with pytest.raises(Failure) as error:
        oracle_executor(resources.database.validator, settings)
    assert error.value.code == "ORACLE_UNAVAILABLE" and "PRIVATE" not in str(error.value)
