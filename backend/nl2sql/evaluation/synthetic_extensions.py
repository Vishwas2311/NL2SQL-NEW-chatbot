"""Additional certified fictional event, derived-metric and multi-fact fixtures."""

import sqlite3

from nl2sql.domain.models import (
    Catalog,
    Column,
    Dimension,
    Metric,
    MetricExpression,
    QueryPlan,
    Relation,
    ReportTemplate,
    ScopePolicy,
    SemanticView,
    Table,
)

EXTRA_METRICS = ("payment_amount", "payment_fee", "payment_count", "net_payments", "fee_rate")


def extend_catalog(catalog: Catalog) -> Catalog:
    """New definitions are local synthetic evidence, never enterprise certification."""
    payment_table = Table(
        id="payments",
        grain=("tenant_id", "payment_id"),
        columns=(
            *(
                Column(name=key, kind="text")
                for key in ("tenant_id", "payment_id", "customer_id", "status")
            ),
            Column(name="paid_on", kind="date"),
            Column(name="amount_minor", kind="integer"),
            Column(name="fee_minor", kind="integer"),
        ),
    )
    metrics = list(catalog.metrics)
    metrics[0] = metrics[0].model_copy(
        update={"aliases": (*metrics[0].aliases, "EOP exposure", "end of period exposure")}
    )
    for key, label, column, aggregate in (
        ("payment_amount", "Payment amount", "amount_minor", "sum"),
        ("payment_fee", "Payment fee", "fee_minor", "sum"),
        ("payment_count", "Payment count", "payment_id", "count"),
    ):
        metrics.append(
            Metric.model_validate(
                {
                    "id": key,
                    "label": label,
                    "aliases": (),
                    "domain": "payments",
                    "table": "payments",
                    "column": column,
                    "aggregate": aggregate,
                    "unit": "count" if aggregate == "count" else "INR",
                    "scale": 1 if aggregate == "count" else 100,
                    "temporal": "event",
                    "definition": (
                        "Active fictional payments on half-open ISO business-date intervals."
                    ),
                }
            )
        )
    metrics.extend(
        (
            Metric(
                id="net_payments",
                label="Net payments",
                aliases=("net receipts",),
                domain="payments",
                table="payments",
                column="amount_minor",
                aggregate="sum",
                unit="INR",
                scale=100,
                temporal="event",
                definition="SUM(payment amount) minus SUM(fee); missing aggregates remain NULL.",
                expression=MetricExpression(
                    kind="difference", numerator="payment_amount", denominator="payment_fee"
                ),
            ),
            Metric(
                id="fee_rate",
                label="Fee rate",
                aliases=("fee percentage",),
                domain="payments",
                table="payments",
                column="fee_minor",
                aggregate="sum",
                unit="percent",
                temporal="event",
                definition=(
                    "100 * SUM(fee) / SUM(payment amount); "
                    "zero or missing denominator returns NULL."
                ),
                expression=MetricExpression(
                    kind="ratio", numerator="payment_fee", denominator="payment_amount"
                ),
            ),
        )
    )
    common = catalog.views[1].dimensions
    views = (
        catalog.views[0].model_copy(update={"dimensions": (*common, "reporting_date")}),
        catalog.views[1],
        SemanticView(
            id="payment_events",
            version="1.0.0",
            domain="payments",
            root="payments",
            grain=payment_table.grain,
            metrics=EXTRA_METRICS,
            dimensions=(*common, "payment_date"),
            relationships=("payments_customer", "customer_region"),
            time_column="paid_on",
            time_kind="event",
            evidence="Fictional independent event/fee/fiscal fixtures",
        ),
        SemanticView(
            id="customer_portfolio",
            version="1.0.0",
            domain="credit",
            root="customers",
            grain=("tenant_id", "customer_id"),
            metrics=("loan_exposure", "loan_count", "account_count"),
            dimensions=common,
            relationships=("customer_region",),
            components=("loan_snapshot", "account_current"),
            evidence="Separately aggregate dated loans and current accounts to customer grain",
        ),
    )
    return catalog.model_copy(
        update={
            "version": "synthetic-v2",
            "classification": "synthetic",
            "templates": tuple(
                ReportTemplate(
                    id=key,
                    question=question,
                    plan=QueryPlan(
                        catalog_version="synthetic-v2",
                        view_id=view,
                        metrics=(metric,),
                        dimensions=dimensions,
                    ),
                )
                for key, question, view, metric, dimensions in (
                    (
                        "exposure_region",
                        "Show total loan exposure by region",
                        "loan_snapshot",
                        "loan_exposure",
                        ("region",),
                    ),
                    (
                        "loan_count_region",
                        "Show loan count by region",
                        "loan_snapshot",
                        "loan_count",
                        ("region",),
                    ),
                    (
                        "account_count_region",
                        "Show account count by region",
                        "account_current",
                        "account_count",
                        ("region",),
                    ),
                    (
                        "exposure_total",
                        "Show total loan exposure",
                        "loan_snapshot",
                        "loan_exposure",
                        (),
                    ),
                    (
                        "average_region",
                        "Show average exposure by region",
                        "loan_snapshot",
                        "average_exposure",
                        ("region",),
                    ),
                )
            ),
            "fiscal_start_month": 4,
            "tables": (*catalog.tables, payment_table),
            "metrics": tuple(metrics),
            "views": tuple(
                view.model_copy(
                    update={
                        "policy": ScopePolicy(status_column=None if view.components else "status")
                    }
                )
                for view in views
            ),
            "dimensions": (
                *catalog.dimensions,
                Dimension(id="reporting_date", table="loans", column="as_of", kind="date"),
                Dimension(id="payment_date", table="payments", column="paid_on", kind="date"),
            ),
            "relations": (
                *catalog.relations,
                Relation(
                    id="payments_customer",
                    left="payments",
                    right="customers",
                    pairs=(("tenant_id", "tenant_id"), ("customer_id", "customer_id")),
                    cardinality="many_to_one",
                ),
            ),
        }
    )


def seed_events(connection: sqlite3.Connection) -> None:
    """Dates, zero/NULL amounts, excluded states and cross-tenant collisions are intentional."""
    connection.executescript("""
        CREATE TABLE payments(tenant_id TEXT, payment_id TEXT, customer_id TEXT, status TEXT,
            paid_on TEXT, amount_minor INTEGER, fee_minor INTEGER, PRIMARY KEY(tenant_id,payment_id),
            FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id));
        CREATE INDEX payment_dates ON payments(tenant_id,paid_on,status);
    """)
    connection.executemany(
        "INSERT INTO payments VALUES (?,?,?,?,?,?,?)",
        (
            ("demo", "P1", "C001", "active", "2026-03-31", 100000, 1000),
            ("demo", "P2", "C001", "active", "2026-04-01", 200000, 2000),
            ("demo", "P3", "C002", "active", "2026-06-30", 300000, 3000),
            ("demo", "P4", "C003", "active", "2026-09-30", 400000, 8000),
            ("demo", "P5", "C004", "active", "2026-09-30", 0, 0),
            ("demo", "P6", "C004", "active", "2026-09-30", None, None),
            ("demo", "P7", "C003", "closed", "2026-09-30", 999999, 9999),
            ("demo", "P8", "C003", "active", "2026-10-01", 500000, 5000),
            ("other", "P1", "C001", "active", "2026-04-01", 99999999, 99999),
        ),
    )
