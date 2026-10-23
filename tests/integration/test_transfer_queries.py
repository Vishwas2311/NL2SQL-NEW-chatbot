"""Regression cases for office transfer: structural grounding and six-edge execution."""

import time
from contextlib import closing
from datetime import date

import pytest
from nl2sql.application.query.compiler import Compiler
from nl2sql.application.query.planning import PlanValidator
from nl2sql.application.query.security import SQLValidator
from nl2sql.bootstrap.resources import build_resources
from nl2sql.domain.fingerprints import digest
from nl2sql.domain.models import (
    Catalog,
    Column,
    Dimension,
    Metric,
    Principal,
    QueryPlan,
    Relation,
    ScopePolicy,
    SemanticView,
    Table,
)
from nl2sql.infrastructure.databases.oracle import OracleAdapter, OracleConfig
from nl2sql.infrastructure.databases.sqlite import SQLiteDatabase
from nl2sql.infrastructure.inference.model import MockModel
from nl2sql.settings import Settings

from tests.contracts.test_oracle_adapter import FakeConnection, FakePolicy, FakePool


def test_column_only_term_reaches_model_without_exposing_ungranted_metrics(settings):
    catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
    tables = tuple(
        table.model_copy(
            update={
                "columns": tuple(
                    column.model_copy(update={"description": "auditcalendarmarker"})
                    if table.id == "payments" and column.name == "paid_on"
                    else column
                    for column in table.columns
                )
            }
        )
        for table in catalog.tables
    )
    text = catalog.model_copy(update={"tables": tables}).model_dump_json()
    settings.catalog_path.write_text(text, encoding="utf-8")
    limited = settings.principals[0].model_copy(
        update={"id": "limited", "metrics": ("account_count",)}
    )
    configuration = settings.model_copy(
        update={"catalog_digest": digest(text), "principals": (*settings.principals, limited)}
    )
    question = "auditcalendarmarker"
    plan = QueryPlan.model_validate(
        {
            "catalog_version": catalog.version,
            "view_id": "payment_events",
            "metrics": ["payment_amount"],
            "dimensions": ["region"],
            "period": {"kind": "range", "start": "2026-04-01", "end_exclusive": "2026-10-01"},
        }
    )
    model = MockModel({question: plan.model_dump_json()})
    resources = build_resources(configuration, model)
    try:
        answer = resources.service.chat(
            question, None, resources.auth.principals["analyst"], None, {}
        )
        assert answer.status == "completed" and model.calls == 1
        assert answer.rows[0]["payment_amount"] == "5000.00"
        assert resources.service.chat(question, None, limited, None, {}).status == "unsupported"
        assert model.calls == 1
    finally:
        resources.close()


@pytest.mark.parametrize("dialect", ["sqlite", "oracle"])
def test_six_certified_joins_reach_execution(tmp_path, dialect):
    import sqlite3

    columns = (
        Column(name="tenant_id", kind="text"),
        Column(name="id", kind="integer"),
        Column(name="region", kind="text"),
        Column(name="value", kind="integer"),
    )
    relations = tuple(
        Relation(
            id=f"e{i}",
            left=f"t{i}",
            right=f"t{i + 1}",
            pairs=(("tenant_id", "tenant_id"), ("id", "id")),
            cardinality="one_to_one",
        )
        for i in range(6)
    )
    catalog = Catalog(
        version="audit-chain",
        approved=True,
        effective_from=date(2020, 1, 1),
        effective_to=date(2030, 1, 1),
        default_as_of=date(2026, 10, 23),
        tables=tuple(
            Table(id=f"t{i}", columns=columns, grain=("tenant_id", "id")) for i in range(7)
        ),
        relations=relations,
        dimensions=(Dimension(id="scope_region", table="t6", column="region", kind="text"),),
        metrics=(
            Metric(
                id="audit_total",
                label="Audit total",
                aliases=(),
                domain="audit",
                table="t0",
                column="value",
                aggregate="sum",
                unit="count",
                temporal="current",
                definition="Synthetic total",
            ),
        ),
        views=(
            SemanticView(
                id="audit_view",
                version="1.0.0",
                domain="audit",
                root="t0",
                grain=("id",),
                metrics=("audit_total",),
                dimensions=("scope_region",),
                relationships=tuple(edge.id for edge in relations),
                evidence="synthetic",
                policy=ScopePolicy(scope_dimension="scope_region", status_column=None),
            ),
        ),
        entities=(),
        classification="synthetic",
    )
    user = Principal(id="audit", tenant="T1", regions=("R1",), metrics=("audit_total",))
    plan = QueryPlan(
        catalog_version=catalog.version,
        view_id="audit_view",
        metrics=("audit_total",),
        dimensions=("scope_region",),
    )
    validated = PlanValidator(catalog).validate(plan, user)
    assert len(validated.proof.relationships) == 6
    query = Compiler(catalog).compile(validated, user, dialect)
    validator = SQLValidator(catalog, b"synthetic-test-key")
    capability = validator.validate(query, user, time.time() + 10)
    if dialect == "sqlite":
        path = tmp_path / "business.db"
        with closing(sqlite3.connect(path)) as connection, connection:
            for i in range(7):
                connection.execute(
                    f"CREATE TABLE t{i}(tenant_id TEXT, id INTEGER, region TEXT, value INTEGER)"
                )
                connection.execute(f"INSERT INTO t{i} VALUES ('T1', 1, 'R1', 7)")
        database = SQLiteDatabase(path, validator, Settings())
    else:
        database = OracleAdapter(
            OracleConfig(
                dsn="synthetic",
                user="synthetic",
                password="synthetic",
                approved_test_environment=True,
            ),
            validator,
            FakePolicy(),
            FakePool(FakeConnection(names=("scope_region", "audit_total"), rows=[("R1", 7)])),
        )
    try:
        assert database.execute(capability, user).rows == (
            {"scope_region": "R1", "audit_total": 7},
        )
    finally:
        database.close()
