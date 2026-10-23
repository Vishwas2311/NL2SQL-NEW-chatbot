"""Allowlisted Oracle dictionary reads, independent of business-query credentials."""

import hashlib
import time
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, cast

import oracledb
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from nl2sql.domain.models import Failure
from nl2sql.domain.physical import (
    PhysicalColumn,
    PhysicalIndex,
    PhysicalInventory,
    PhysicalKey,
    PhysicalObject,
    stable_id,
)
from nl2sql.infrastructure.databases.oracle import OracleConnection, OraclePool

DictionaryValue = str | int | None
DictionaryRow = dict[str, DictionaryValue]


class OracleDiscoverySettings(BaseSettings):
    """Approval flags attest externally obtained permissions; they do not grant DB rights."""

    model_config = SettingsConfigDict(env_prefix="NL2SQL_DISCOVERY_", extra="forbid", env_file=None)
    source_id: str = "office-oracle"
    approved_environment: bool = False
    owner_authorized: bool = False
    network_authorized: bool = False
    dsn: SecretStr | None = None
    user: SecretStr | None = None
    password: SecretStr | None = None
    owners: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=15, ge=1, le=120)
    max_rows: int = Field(default=100_000, ge=1, le=500_000)
    max_bytes: int = Field(default=20_000_000, ge=1000, le=100_000_000)


# These projections never read business rows, statistics/sample values or default expressions.
DICTIONARY = (
    ("tables", "ALL_TABLES", "OWNER,TABLE_NAME", True),
    ("views", "ALL_VIEWS", "OWNER,VIEW_NAME,TEXT_LENGTH", True),
    (
        "columns",
        "ALL_TAB_COLUMNS",
        "OWNER,TABLE_NAME,COLUMN_NAME,DATA_TYPE,DATA_PRECISION,DATA_SCALE,"
        "DATA_LENGTH,NULLABLE,COLUMN_ID",
        True,
    ),
    (
        "constraints",
        "ALL_CONSTRAINTS",
        "OWNER,TABLE_NAME,CONSTRAINT_NAME,CONSTRAINT_TYPE,R_OWNER,"
        "R_CONSTRAINT_NAME,STATUS,VALIDATED",
        True,
    ),
    (
        "key_columns",
        "ALL_CONS_COLUMNS",
        "OWNER,TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,POSITION",
        True,
    ),
    ("objects", "ALL_OBJECTS", "OWNER,OBJECT_NAME,OBJECT_TYPE,LAST_DDL_TIME,STATUS", True),
    ("indexes", "ALL_INDEXES", "OWNER,TABLE_NAME,INDEX_NAME,UNIQUENESS", False),
    ("table_comments", "ALL_TAB_COMMENTS", "OWNER,TABLE_NAME,COMMENTS", False),
    ("column_comments", "ALL_COL_COMMENTS", "OWNER,TABLE_NAME,COLUMN_NAME,COMMENTS", False),
    (
        "dependencies",
        "ALL_DEPENDENCIES",
        "OWNER,NAME,REFERENCED_OWNER,REFERENCED_NAME,REFERENCED_TYPE",
        False,
    ),
    ("view_text", "ALL_VIEWS", "OWNER,VIEW_NAME,TEXT_VC", False),
)


class OracleDiscovery:
    """A supplied test pool exercises the same guard and SQL without making a connection."""

    def __init__(self, settings: OracleDiscoverySettings, pool: OraclePool | None = None) -> None:
        if not (
            settings.approved_environment
            and settings.owner_authorized
            and settings.network_authorized
        ):
            raise Failure(
                "ORACLE_NOT_APPROVED",
                "Oracle metadata access requires organizational authorization.",
                "denied",
            )
        if not settings.owners or any(
            not owner or len(owner) > 128 or "\x00" in owner for owner in settings.owners
        ):
            raise ValueError("Explicit valid allowlisted schema owners are required")
        self.settings = settings
        self.pool = pool

    def discover(self) -> PhysicalInventory:
        """Use one read-only consistent transaction; roll back and release on every path."""
        started = time.monotonic()
        settings = self.settings
        if self.pool is not None:
            try:
                connection = self.pool.acquire()
                try:
                    return self._discover(connection, started)
                finally:
                    try:
                        connection.rollback()
                        self.pool.release(connection)
                    except oracledb.Error:
                        try:
                            self.pool.drop(connection)
                        except oracledb.Error:
                            pass
                        raise Failure(
                            "DISCOVERY_CLEANUP",
                            "Discovery connection cleanup failed.",
                            "unavailable",
                        ) from None
            except oracledb.Error:
                raise Failure(
                    "DISCOVERY_UNAVAILABLE",
                    "Oracle metadata discovery is unavailable.",
                    "unavailable",
                ) from None
        if settings.dsn is None or settings.user is None or settings.password is None:
            raise Failure(
                "ORACLE_CONFIGURATION",
                "Approved discovery credentials are required.",
                "unavailable",
            )
        try:
            with closing(
                cast(
                    OracleConnection,
                    oracledb.connect(
                        dsn=settings.dsn.get_secret_value(),
                        user=settings.user.get_secret_value(),
                        password=settings.password.get_secret_value(),
                        tcp_connect_timeout=settings.timeout_seconds,
                    ),
                )
            ) as connection:
                try:
                    return self._discover(connection, started)
                finally:
                    connection.rollback()
        except oracledb.Error as error:
            raise Failure(
                "DISCOVERY_UNAVAILABLE", "Oracle metadata discovery is unavailable.", "unavailable"
            ) from error

    def _discover(self, connection: OracleConnection, started: float) -> PhysicalInventory:
        warnings: list[str] = []
        records: dict[str, tuple[DictionaryRow, ...]] = {}
        total_bytes = total_rows = 0
        with connection.cursor() as cursor:
            connection.call_timeout = self.settings.timeout_seconds * 1000
            connection.rollback()
            cursor.execute("SET TRANSACTION READ ONLY")
            for key, dictionary, projection, required in DICTIONARY:
                remaining = self.settings.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise Failure(
                        "DISCOVERY_TIMEOUT", "Metadata discovery exceeded its deadline.", "timeout"
                    )
                connection.call_timeout = max(1, int(remaining * 1000))
                binds: dict[str, str | int | date] = {
                    f"owner_{i}": owner for i, owner in enumerate(self.settings.owners)
                }
                binds["row_budget"] = self.settings.max_rows + 1
                owners = ",".join(":" + name for name in binds if name.startswith("owner_"))
                sql = (
                    f"SELECT {projection} FROM {dictionary} WHERE OWNER IN ({owners}) "
                    "AND ROWNUM <= :row_budget"
                )
                try:
                    cursor.execute(sql, binds, fetch_decimals=True, fetch_lobs=False)
                    rows = cursor.fetchmany(self.settings.max_rows + 1)
                except oracledb.Error as error:
                    code = str(getattr(error.args[0], "full_code", "")) if error.args else ""
                    if not required and code in {"ORA-00942", "ORA-00904", "ORA-01031"}:
                        warnings.append(f"optional_dictionary_unavailable:{key}")
                        records[key] = ()
                        continue
                    raise Failure(
                        "DISCOVERY_UNAVAILABLE",
                        "Required Oracle metadata is unavailable.",
                        "unavailable",
                    ) from error
                total_rows += len(rows)
                if total_rows > self.settings.max_rows:
                    raise Failure(
                        "DISCOVERY_LIMIT",
                        "Metadata discovery exceeded its record budget.",
                        "too_large",
                    )
                values: list[DictionaryRow] = []
                for row in rows:
                    converted = tuple(dictionary_scalar(value) for value in row)
                    total_bytes += sum(len(str(value).encode()) for value in converted)
                    if total_bytes > self.settings.max_bytes:
                        raise Failure(
                            "DISCOVERY_LIMIT",
                            "Metadata discovery exceeded its byte budget.",
                            "too_large",
                        )
                    values.append(dict(zip(projection.lower().split(","), converted, strict=True)))
                records[key] = tuple(values)
        if time.monotonic() - started > self.settings.timeout_seconds:
            raise Failure(
                "DISCOVERY_TIMEOUT", "Metadata discovery exceeded its deadline.", "timeout"
            )
        return inventory_from_dictionary(
            self.settings.source_id, self.settings.owners, records, tuple(warnings)
        )


def dictionary_scalar(value: object) -> DictionaryValue:
    """Oracle metadata numbers are integral; never coerce unknown objects or float values."""
    if value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        return int(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise Failure(
        "DISCOVERY_TYPE", "Oracle metadata contained an unsupported value.", "unavailable"
    )


def inventory_from_dictionary(
    source_id: str,
    owners: tuple[str, ...],
    records: dict[str, tuple[DictionaryRow, ...]],
    warnings: tuple[str, ...],
) -> PhysicalInventory:
    """Pure conversion is independently testable with dictionary fixtures."""
    objects: list[PhysicalObject] = []
    grouped = _group_dictionary(records)
    constraints = {
        (str(row["owner"]), str(row["constraint_name"])): row for row in records["constraints"]
    }
    key_columns: dict[tuple[str, str], list[DictionaryRow]] = {}
    for row in records["key_columns"]:
        key_columns.setdefault((str(row["owner"]), str(row["constraint_name"])), []).append(row)
    for rows in key_columns.values():
        rows.sort(key=lambda row: int(str(row["position"])))
    for kind, source, name_field in (
        ("table", "tables", "table_name"),
        ("view", "views", "view_name"),
    ):
        for row in records[source]:
            owner, name = str(row["owner"]), str(row[name_field])
            objects.append(
                _dictionary_object(
                    owner, name, kind, grouped[(owner, name)], constraints, key_columns
                )
            )
    missing = set(owners) - {item.owner for item in objects}
    if missing:
        warnings = (*warnings, "owner_visibility_unverified")
    return PhysicalInventory(
        source_id=source_id,
        source_kind="oracle",
        owners=owners,
        objects=tuple(sorted(objects, key=lambda item: item.id)),
        warnings=warnings,
        verification="pending_verification" if missing else "verified_physical",
    )


def _group_dictionary(
    records: dict[str, tuple[DictionaryRow, ...]],
) -> dict[tuple[str, str], dict[str, tuple[DictionaryRow, ...]]]:
    """Index once; avoid rescanning every column for every table in a large schema."""
    grouped: dict[tuple[str, str], dict[str, list[DictionaryRow]]] = {}
    for key, rows in records.items():
        field = (
            "object_name"
            if key == "objects"
            else "view_name"
            if key in {"views", "view_text"}
            else "name"
            if key == "dependencies"
            else "table_name"
        )
        for row in rows:
            identity = (str(row["owner"]), str(row[field]))
            grouped.setdefault(identity, {}).setdefault(key, []).append(row)
    return {
        identity: {key: tuple(parts.get(key, ())) for key in records}
        for identity, parts in grouped.items()
    }


def _dictionary_object(
    owner: str,
    name: str,
    kind: str,
    records: dict[str, tuple[DictionaryRow, ...]],
    constraints: dict[tuple[str, str], DictionaryRow],
    key_columns: dict[tuple[str, str], list[DictionaryRow]],
) -> PhysicalObject:
    def belongs(row: DictionaryRow) -> bool:
        return row.get("owner") == owner and row.get("table_name") == name

    comments = {
        str(row["column_name"]): row.get("comments")
        for row in records.get("column_comments", ())
        if belongs(row)
    }
    columns = tuple(
        PhysicalColumn.model_validate(
            {
                "id": stable_id("c", owner, name, str(row["column_name"])),
                "name": row["column_name"],
                "data_type": row["data_type"],
                "position": row["column_id"],
                "nullable": row["nullable"] == "Y",
                "precision": row["data_precision"],
                "scale": row["data_scale"],
                "length": row["data_length"],
                "comment": comments.get(str(row["column_name"])),
            }
        )
        for row in records["columns"]
        if belongs(row)
    )
    keys: list[PhysicalKey] = []
    kinds: dict[str, Literal["primary", "unique", "foreign"]] = {
        "P": "primary",
        "U": "unique",
        "R": "foreign",
    }
    for row in records["constraints"]:
        key = (owner, str(row["constraint_name"]))
        if not belongs(row) or row["constraint_type"] not in ("P", "U", "R"):
            continue
        names = tuple(str(item["column_name"]) for item in key_columns.get(key, ()))
        target_key = (str(row["r_owner"]), str(row["r_constraint_name"]))
        target = constraints.get(target_key)
        target_names = tuple(str(item["column_name"]) for item in key_columns.get(target_key, ()))
        keys.append(
            PhysicalKey(
                id=stable_id("k", *key),
                name=key[1],
                kind=kinds[str(row["constraint_type"])],
                columns=names,
                enabled=row["status"] == "ENABLED",
                validated=row["validated"] == "VALIDATED"
                and (
                    row["constraint_type"] != "R"
                    or (
                        target is not None
                        and target["status"] == "ENABLED"
                        and target["validated"] == "VALIDATED"
                    )
                ),
                target=stable_id("o", target_key[0], str(target["table_name"])) if target else None,
                target_columns=target_names,
                target_owner=target_key[0] if row["constraint_type"] == "R" else None,
                target_constraint=target_key[1] if row["constraint_type"] == "R" else None,
            )
        )
    empty: DictionaryRow = {}
    metadata = next(
        (
            row
            for row in records["objects"]
            if row["owner"] == owner
            and row["object_name"] == name
            and str(row["object_type"]).lower() == kind
        ),
        empty,
    )
    view = next(
        (
            row
            for row in records.get("view_text", ())
            if row["owner"] == owner and row["view_name"] == name
        ),
        empty,
    )
    definition = view.get("text_vc")
    view_length = next((row.get("text_length") for row in records["views"]), None)
    table_comment = next(
        (row.get("comments") for row in records.get("table_comments", ()) if belongs(row)), None
    )
    return PhysicalObject.model_validate(
        {
            "id": stable_id("o", owner, name),
            "owner": owner,
            "name": name,
            "kind": kind,
            "verification": "pending_verification"
            if not columns
            or metadata.get("status") != "VALID"
            or (
                kind == "view"
                and (not definition or view_length is None or int(str(view_length)) > 4000)
            )
            else "verified_physical",
            "columns": columns,
            "keys": tuple(keys),
            "comment": table_comment,
            "last_ddl_at": metadata.get("last_ddl_time"),
            "definition_digest": hashlib.sha256(str(definition).encode()).hexdigest()
            if definition
            else None,
            "indexes": tuple(
                PhysicalIndex(name=str(row["index_name"]), unique=row["uniqueness"] == "UNIQUE")
                for row in records.get("indexes", ())
                if belongs(row)
            ),
            "dependencies": tuple(
                stable_id("o", str(row["referenced_owner"]), str(row["referenced_name"]))
                for row in records.get("dependencies", ())
                if row["owner"] == owner and row["name"] == name
            ),
            "evidence": "Oracle ALL_* dictionary; bounded TEXT_VC; DDL version retained",
        }
    )
