"""Dictionary fixtures contain only made-up objects; no office connection is made."""

import sqlite3
from contextlib import closing
from types import SimpleNamespace

import oracledb
import pytest
from nl2sql.domain.models import Failure
from nl2sql.domain.physical import inventory_digest, stable_id
from nl2sql.infrastructure.metadata.discovery import FileDiscovery, SyntheticDiscovery
from nl2sql.infrastructure.metadata.oracle_discovery import (
    DICTIONARY,
    OracleDiscovery,
    OracleDiscoverySettings,
)

from tests.contracts.test_oracle_adapter import FakeConnection, FakePool


def dictionary_rows():
    rows = {key: [] for key, *_ in DICTIONARY}
    rows["tables"] = [("Fictional Office", "Sales Ledger"), ("Fictional Office", "Regions")]
    rows["columns"] = [
        ("Fictional Office", table, column, kind, precision, scale, 100, "N", position)
        for table, column, kind, precision, scale, position in (
            ("Sales Ledger", "Tenant Key", "VARCHAR2", None, None, 1),
            ("Sales Ledger", "Record ID", "NUMBER", 12, 0, 2),
            ("Sales Ledger", "Area Key", "VARCHAR2", None, None, 3),
            ("Sales Ledger", "Exact Amount", "NUMBER", 38, 6, 4),
            ("Regions", "Tenant Key", "VARCHAR2", None, None, 1),
            ("Regions", "Area Key", "VARCHAR2", None, None, 2),
        )
    ]
    rows["constraints"] = [
        ("Fictional Office", table, name, kind, target_owner, target, "ENABLED", "VALIDATED")
        for table, name, kind, target_owner, target in (
            ("Sales Ledger", "pk_sales", "P", None, None),
            ("Regions", "pk_regions", "P", None, None),
            ("Sales Ledger", "fk_sales_regions", "R", "Fictional Office", "pk_regions"),
        )
    ]
    rows["key_columns"] = [
        ("Fictional Office", table, constraint, column, position)
        for table, constraint, columns in (
            ("Sales Ledger", "pk_sales", ("Tenant Key", "Record ID")),
            ("Regions", "pk_regions", ("Tenant Key", "Area Key")),
            ("Sales Ledger", "fk_sales_regions", ("Tenant Key", "Area Key")),
        )
        for position, column in enumerate(columns, 1)
    ]
    rows["objects"] = [
        ("Fictional Office", table, "TABLE", "2026-10-16T00:00:00", "VALID")
        for table in ("Sales Ledger", "Regions")
    ]
    return rows


class DictionaryCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def execute(self, sql, parameters=None, **options):
        self.connection.calls.append((sql, parameters, options))
        if sql == "SET TRANSACTION READ ONLY":
            return
        assert parameters["owner_0"] == "Fictional Office"
        assert "Fictional Office" not in sql
        key = next(
            key
            for key, view, projection, _ in DICTIONARY
            if sql.startswith("SELECT " + projection + " FROM " + view + " ")
        )
        self.rows = self.connection.dictionary[key]

    def fetchmany(self, size):
        return self.rows[:size]


class DictionaryConnection(FakeConnection):
    def __init__(self):
        super().__init__()
        self.dictionary = dictionary_rows()

    def cursor(self):
        return DictionaryCursor(self)


def test_oracle_dictionary_preserves_quoted_names_decimal_and_composite_keys():
    connection = DictionaryConnection()
    pool = FakePool(connection)
    settings = OracleDiscoverySettings(
        approved_environment=True,
        owner_authorized=True,
        network_authorized=True,
        owners=("Fictional Office",),
    )
    inventory = OracleDiscovery(settings, pool).discover()
    sales = next(item for item in inventory.objects if item.name == "Sales Ledger")
    amount = next(item for item in sales.columns if item.name == "Exact Amount")
    assert (amount.data_type, amount.precision, amount.scale) == ("NUMBER", 38, 6)
    foreign = next(key for key in sales.keys if key.kind == "foreign")
    assert foreign.columns == foreign.target_columns == ("Tenant Key", "Area Key")
    assert foreign.target == stable_id("o", "Fictional Office", "Regions")
    assert pool.released == 1 and pool.dropped == 0
    assert all(
        "FROM ALL_" in sql or sql == "SET TRANSACTION READ ONLY" for sql, *_ in connection.calls
    )
    assert len(connection.calls) == len(DICTIONARY) + 1


def test_oracle_approval_guard_precedes_any_acquisition():
    pool = FakePool(DictionaryConnection())
    with pytest.raises(Failure, match="authorization"):
        OracleDiscovery(OracleDiscoverySettings(owners=("Fictional Office",)), pool)
    assert pool.acquired == 0


def test_discovery_row_budget_is_fail_closed():
    settings = OracleDiscoverySettings(
        approved_environment=True,
        owner_authorized=True,
        network_authorized=True,
        owners=("Fictional Office",),
        max_rows=1,
    )
    pool = FakePool(DictionaryConnection())
    with pytest.raises(Failure, match="budget"):
        OracleDiscovery(settings, pool).discover()
    assert pool.released == 1


@pytest.mark.parametrize("required", [False, True])
def test_dictionary_permission_failures_are_safe_and_release_connection(required):
    class LimitedCursor(DictionaryCursor):
        def execute(self, sql, parameters=None, **options):
            dictionary = "ALL_CONSTRAINTS" if required else "ALL_COL_COMMENTS"
            if " FROM " + dictionary + " " in sql:
                raise oracledb.DatabaseError(
                    SimpleNamespace(full_code="ORA-01031", message="PRIVATE_DICTIONARY_PASSWORD")
                )
            return super().execute(sql, parameters, **options)

    class LimitedConnection(DictionaryConnection):
        def cursor(self):
            return LimitedCursor(self)

    pool = FakePool(LimitedConnection())
    settings = OracleDiscoverySettings(
        approved_environment=True,
        owner_authorized=True,
        network_authorized=True,
        owners=("Fictional Office",),
    )
    if required:
        with pytest.raises(Failure) as error:
            OracleDiscovery(settings, pool).discover()
        assert error.value.code == "DISCOVERY_UNAVAILABLE"
        assert "PRIVATE" not in str(error.value)
    else:
        inventory = OracleDiscovery(settings, pool).discover()
        assert "optional_dictionary_unavailable:column_comments" in inventory.warnings
        assert "PRIVATE" not in inventory.model_dump_json()
    assert pool.released == 1


def test_synthetic_discovery_row_changes_and_file_roundtrip(settings, tmp_path):
    source = SyntheticDiscovery(settings.data_dir / "banking.db")
    first = source.discover()
    with closing(sqlite3.connect(settings.data_dir / "banking.db")) as conn, conn:
        conn.execute("UPDATE loans SET amount_minor=amount_minor+1 WHERE loan_id='L1'")
    assert inventory_digest(first) == inventory_digest(source.discover())
    file = tmp_path / "physical-inventory.json"
    file.write_text(first.model_dump_json())
    assert FileDiscovery(file).discover() == first
    with pytest.raises(ValueError, match="budget"):
        FileDiscovery(file, max_bytes=1).discover()
    with closing(sqlite3.connect(settings.data_dir / "banking.db")) as conn, conn:
        conn.execute("ALTER TABLE loans ADD COLUMN reviewed_flag TEXT")
    assert inventory_digest(first) != inventory_digest(source.discover())


def test_identifiers_never_collapse_case_unicode_or_punctuation():
    values = [
        stable_id("o", "OWNER", name) for name in ("Sales", "sales", "Î£ales", "Sales!", "sales?")
    ]
    assert len(set(values)) == 5 and all(len(value) <= 63 for value in values)
