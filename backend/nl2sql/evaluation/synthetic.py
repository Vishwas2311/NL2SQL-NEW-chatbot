"""Deterministic, fictional banking data and its local-only certified catalog."""

import json
import secrets
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Literal

from nl2sql.domain.fingerprints import digest
from nl2sql.domain.models import (
    Catalog,
    Column,
    Dimension,
    Metric,
    Principal,
    Relation,
    SemanticView,
    Table,
)
from nl2sql.evaluation.synthetic_extensions import EXTRA_METRICS, extend_catalog, seed_events
from nl2sql.infrastructure.metadata.catalog_store import validate_sqlite_schema
from nl2sql.settings import Settings, TokenGrant

ALL_METRICS = (
    "loan_exposure",
    "loan_count",
    "average_exposure",
    "largest_exposure",
    "smallest_exposure",
    "account_count",
    *EXTRA_METRICS,
)


def synthetic_catalog() -> Catalog:
    """Certification evidence is synthetic test approval, never company approval."""

    def table(
        name: str,
        names: tuple[str, ...],
        integers: tuple[str, ...],
        grain: tuple[str, ...],
        dates: tuple[str, ...] = (),
    ) -> Table:
        return Table(
            id=name,
            grain=grain,
            columns=tuple(
                Column(
                    name=key,
                    kind="integer" if key in integers else "date" if key in dates else "text",
                )
                for key in names
            ),
        )

    tables = (
        table("regions", ("tenant_id", "region_id", "name"), (), ("tenant_id", "region_id")),
        table(
            "customers",
            ("tenant_id", "customer_id", "name", "alias", "region_id"),
            (),
            ("tenant_id", "customer_id"),
        ),
        table(
            "loans",
            ("tenant_id", "loan_id", "customer_id", "as_of", "amount_minor", "status"),
            ("amount_minor",),
            ("tenant_id", "loan_id", "as_of"),
            ("as_of",),
        ),
        table(
            "accounts",
            ("tenant_id", "account_id", "customer_id", "status"),
            (),
            ("tenant_id", "account_id"),
        ),
    )
    relations = tuple(
        Relation(
            id=root + "_customer",
            left=root,
            right="customers",
            cardinality="many_to_one",
            pairs=(("tenant_id", "tenant_id"), ("customer_id", "customer_id")),
        )
        for root in ("loans", "accounts")
    ) + (
        Relation(
            id="customer_region",
            left="customers",
            right="regions",
            cardinality="many_to_one",
            pairs=(("tenant_id", "tenant_id"), ("region_id", "region_id")),
        ),
    )
    dimensions = (
        Dimension(id="region", table="regions", column="name", kind="text"),
        Dimension(id="region_id", table="regions", column="region_id", kind="text"),
        Dimension(
            id="customer_id", table="customers", column="customer_id", kind="text", entity=True
        ),
        Dimension(id="customer", table="customers", column="name", kind="text", entity=True),
    )
    metrics: list[Metric] = []
    specifications: tuple[
        tuple[str, str, tuple[str, ...], Literal["sum", "count", "avg", "min", "max"]], ...
    ] = (
        ("loan_exposure", "Loan exposure", ("outstanding exposure", "total exposure"), "sum"),
        ("loan_count", "Loan count", ("number of loans",), "count"),
        ("average_exposure", "Average exposure", ("mean loan exposure",), "avg"),
        ("largest_exposure", "Largest exposure", ("maximum loan exposure",), "max"),
        ("smallest_exposure", "Smallest exposure", ("minimum loan exposure",), "min"),
    )
    for key, label, aliases, aggregate in specifications:
        metrics.append(
            Metric(
                id=key,
                label=label,
                aliases=aliases,
                domain="credit",
                table="loans",
                column="loan_id" if aggregate == "count" else "amount_minor",
                aggregate=aggregate,
                unit="count" if aggregate == "count" else "INR",
                scale=1 if aggregate == "count" else 100,
                temporal="snapshot",
                definition=(
                    "Active fictional INR loans at one reporting snapshot; NULL amounts excluded."
                ),
            )
        )
    metrics.append(
        Metric(
            id="account_count",
            label="Account count",
            aliases=("number of accounts",),
            domain="deposits",
            table="accounts",
            column="account_id",
            aggregate="count",
            unit="count",
            temporal="current",
            definition="Active fictional accounts now.",
        )
    )
    fields = tuple(item.id for item in dimensions)
    views = (
        SemanticView(
            id="loan_snapshot",
            version="1.0.0",
            domain="credit",
            root="loans",
            grain=tables[2].grain,
            metrics=tuple(item.id for item in metrics[:-1]),
            dimensions=fields,
            relationships=("loans_customer", "customer_region"),
            time_column="as_of",
            evidence="Synthetic golden fixture v1; not enterprise approval",
        ),
        SemanticView(
            id="account_current",
            version="1.0.0",
            domain="deposits",
            root="accounts",
            grain=tables[3].grain,
            metrics=("account_count",),
            dimensions=fields,
            relationships=("accounts_customer", "customer_region"),
            evidence="Synthetic golden fixture v1; not enterprise approval",
        ),
    )
    return extend_catalog(
        Catalog(
            version="synthetic-v1",
            approved=True,
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 12, 31),
            default_as_of=date(2026, 9, 30),
            tables=tables,
            relations=relations,
            dimensions=dimensions,
            metrics=tuple(metrics),
            views=views,
        )
    )


def seed_database(path: Path) -> None:
    """Create once; never overwrite an existing user's database."""
    if path.exists():
        raise FileExistsError(f"Refusing to replace existing database: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript("""
            PRAGMA foreign_keys=ON;
            CREATE TABLE regions(tenant_id TEXT, region_id TEXT, name TEXT,
                                 PRIMARY KEY(tenant_id,region_id));
            CREATE TABLE customers(tenant_id TEXT, customer_id TEXT, name TEXT, alias TEXT,
                region_id TEXT, PRIMARY KEY(tenant_id,customer_id),
                FOREIGN KEY(tenant_id,region_id) REFERENCES regions(tenant_id,region_id));
            CREATE TABLE loans(tenant_id TEXT, loan_id TEXT, customer_id TEXT, as_of TEXT,
                amount_minor INTEGER, status TEXT, PRIMARY KEY(tenant_id,loan_id,as_of),
                FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id));
            CREATE TABLE accounts(tenant_id TEXT, account_id TEXT, customer_id TEXT, status TEXT,
                PRIMARY KEY(tenant_id,account_id),
                FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id));
            CREATE INDEX loan_snapshot ON loans(tenant_id,as_of,status);
        """)
        connection.executemany(
            "INSERT INTO regions VALUES (?,?,?)",
            (
                ("demo", "north", "Demo North"),
                ("demo", "south", "Demo South"),
                ("other", "north", "Other North"),
            ),
        )
        connection.executemany(
            "INSERT INTO customers VALUES (?,?,?,?,?)",
            (
                ("demo", "C001", "Fable Textiles", "Fable", "north"),
                ("demo", "C002", "Lantern Foods", "Lantern", "north"),
                ("demo", "C003", "Cedar Works", "Cedar", "south"),
                ("demo", "C004", "Cedar Services", "Cedar", "south"),
                ("other", "C001", "Other Fiction", "Fable", "north"),
            ),
        )
        connection.executemany(
            "INSERT INTO loans VALUES (?,?,?,?,?,?)",
            (
                ("demo", "L1", "C001", "2026-09-30", 10000000, "active"),
                ("demo", "L2", "C001", "2026-09-30", 2500000, "active"),
                ("demo", "L3", "C002", "2026-09-30", 5000050, "active"),
                ("demo", "L4", "C003", "2026-09-30", 7500000, "active"),
                ("demo", "L5", "C004", "2026-09-30", None, "active"),
                ("demo", "L6", "C003", "2026-09-30", 99999999, "closed"),
                ("demo", "L1", "C001", "2025-09-30", 8000000, "active"),
                ("demo", "L4", "C003", "2025-09-30", 6000000, "active"),
                ("other", "L1", "C001", "2026-09-30", 999999999, "active"),
            ),
        )
        connection.executemany(
            "INSERT INTO accounts VALUES (?,?,?,?)",
            (
                ("demo", "A1", "C001", "active"),
                ("demo", "A2", "C001", "active"),
                ("demo", "A3", "C002", "active"),
                ("demo", "A4", "C003", "active"),
                ("demo", "A5", "C003", "closed"),
                ("other", "A1", "C001", "active"),
            ),
        )
        seed_events(connection)
        validate_sqlite_schema(synthetic_catalog(), connection)
        connection.commit()


def initialize(data_dir: Path, catalog_path: Path) -> None:
    """Generate random local credentials into ignored files; never print bearer tokens."""
    settings_path = data_dir / "settings.json"
    if settings_path.exists() or (data_dir / "banking.db").exists():
        raise FileExistsError("Local data already exists; choose another output directory")
    catalog = synthetic_catalog()
    payload = catalog.model_dump_json(indent=2) + "\n"
    if catalog_path.exists() and catalog_path.read_text(encoding="utf-8") != payload:
        raise FileExistsError("Refusing to replace a different catalog")
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(payload, encoding="utf-8")
    seed_database(data_dir / "banking.db")
    principals = (
        Principal(id="analyst", tenant="demo", regions=("north", "south"), metrics=ALL_METRICS),
        Principal(id="north_analyst", tenant="demo", regions=("north",), metrics=ALL_METRICS),
    )
    tokens = {principal.id: secrets.token_urlsafe(32) for principal in principals}
    settings = Settings(
        data_classification="synthetic",
        data_dir=data_dir.resolve(),
        catalog_path=catalog_path.resolve(),
        catalog_digest=digest(payload),
        principals=principals,
        tokens=tuple(
            TokenGrant(sha256=digest(tokens[principal.id]), principal_id=principal.id)
            for principal in principals
        ),
    )
    settings_path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    (data_dir / "demo-credentials.json").write_text(json.dumps(tokens, indent=2), encoding="utf-8")
