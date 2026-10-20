"""Explicitly gated Oracle adapter. No connection occurs during normal app startup."""

import json
import time
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from threading import Event, Thread
from typing import Literal, Protocol, cast

import oracledb

from nl2sql.application.query.entity_lookup import entity_query, exact_entity
from nl2sql.application.query.security import SQLValidator
from nl2sql.domain.models import (
    Capability,
    EntityMapping,
    ExecutionResult,
    Failure,
    Principal,
    Row,
    Scalar,
)


class OracleCursor(Protocol):
    """Narrow typed boundary for incomplete third-party driver annotations."""

    @property
    def description(self) -> list[tuple[object, ...]] | None:
        """Driver column metadata."""
        ...

    def execute(
        self,
        statement: str,
        parameters: Mapping[str, str | int | date | Decimal] | None = None,
        *,
        fetch_decimals: bool = False,
        fetch_lobs: bool = False,
    ) -> object:
        """Execute only internally approved statements."""
        ...

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        """Fetch bounded typed results."""
        ...

    def callproc(self, name: str, parameters: list[str] | None = None) -> object:
        """Only separately approved DBA context procedures are configurable."""
        ...


class OracleConnection(Protocol):
    """The subset of the driver needed by the read-only adapter."""

    call_timeout: int

    def close(self) -> None:
        """Close a standalone metadata connection."""
        ...

    def cursor(self) -> AbstractContextManager[OracleCursor]:
        """Create a driver-managed cursor."""
        ...

    def rollback(self) -> None:
        """End read-only transaction and discard state."""
        ...

    def cancel(self) -> None:
        """Break an executing call from the bounded request watchdog."""
        ...


class OraclePool(Protocol):
    """Typed pool acquisition and closure boundary."""

    def acquire(self) -> OracleConnection:
        """Acquire a pooled connection with a bounded wait."""
        ...

    def release(self, connection: OracleConnection) -> None:
        """Return a cleaned connection to the pool."""
        ...

    def drop(self, connection: OracleConnection) -> None:
        """Never recycle a connection whose principal-context cleanup failed."""
        ...

    def close(self) -> None:
        """Close the pool."""
        ...


class OracleContextPolicy(Protocol):
    """DBA-supplied VPD/context setup and reset must be independently qualified."""

    def apply(self, connection: OracleConnection, principal: Principal) -> None:
        """Set approved DB-enforced principal/tenant context."""
        ...

    def reset(self, connection: OracleConnection) -> None:
        """Remove all principal context before returning to pool."""
        ...


@dataclass(frozen=True)
class OracleConfig:
    """Credentials must be supplied by an approved secret manager at integration."""

    dsn: str
    user: str
    password: str = field(repr=False)
    approved_test_environment: bool = False
    pool_max: int = 4
    timeout_ms: int = 3000
    max_result_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        """Reject unbounded driver/resource configuration."""
        if (
            not 1 <= self.pool_max <= 16
            or not 1 <= self.timeout_ms <= 30_000
            or not 1000 <= self.max_result_bytes <= 10_000_000
        ):
            raise ValueError("Invalid Oracle resource budget")


class OracleAdapter:
    """Prepare read-only transactions and cleanup; real behavior remains enterprise-gated."""

    dialect: Literal["oracle"] = "oracle"

    def __init__(
        self,
        config: OracleConfig,
        validator: SQLValidator,
        policy: OracleContextPolicy,
        pool: OraclePool | None = None,
    ) -> None:
        if not config.approved_test_environment:
            raise Failure("ORACLE_NOT_APPROVED", "Oracle test access is not approved.", 503)
        self.config = config
        self.validator = validator
        self.policy = policy
        self.pool = pool or cast(
            OraclePool,
            oracledb.create_pool(
                user=config.user,
                password=config.password,
                dsn=config.dsn,
                min=0,
                max=config.pool_max,
                increment=1,
                getmode=oracledb.POOL_GETMODE_TIMEDWAIT,
                wait_timeout=1000,
            ),
        )

    def execute(
        self, capability: Capability, principal: Principal, cancellation: Event | None = None
    ) -> ExecutionResult:
        """Requires DB-enforced read grants/VPD; estimates never replace hard controls."""
        query = self.validator.verify(capability, principal)
        if query.dialect != "oracle":
            raise Failure("DIALECT_ERROR", "An Oracle query is required.")
        if len(query.validated_plan.proof.relationships) > 5:
            raise Failure("PREFLIGHT_REJECTED", "The query exceeds the resource budget.")
        cancelled = cancellation or Event()
        if cancelled.is_set():
            raise Failure("QUERY_CANCELLED", "The query was cancelled.", 409)
        started = time.perf_counter()
        deadline = min(capability.expires_at, time.time() + self.config.timeout_ms / 1000)
        try:
            connection = self.pool.acquire()
        except oracledb.Error as error:
            raise Failure("ORACLE_UNAVAILABLE", "Oracle acquisition failed.", 503) from error
        finished = Event()
        cancel_failed = Event()

        def watch() -> None:
            while not finished.wait(0.01):
                if cancelled.is_set() or time.time() >= deadline:
                    try:
                        connection.cancel()
                    except oracledb.Error:
                        cancel_failed.set()
                    return

        watcher = Thread(target=watch, name="oracle-query-deadline", daemon=True)
        watcher.start()
        try:
            self.validator.verify(capability, principal)
            self._check_deadline(deadline, cancelled)
            connection.call_timeout = max(1, int((deadline - time.time()) * 1000))
            connection.rollback()
            self.policy.apply(connection, principal)
            parameters: dict[str, str | int | date | Decimal] = dict(query.binds)
            for key, kind in query.bind_types:
                if kind == "date":
                    parameters[key] = date.fromisoformat(str(parameters[key]))
                elif kind == "decimal":
                    parameters[key] = Decimal(str(parameters[key]))
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                self._check_deadline(deadline, cancelled)
                cursor.execute(query.sql, parameters, fetch_decimals=True, fetch_lobs=False)
                names = tuple(str(item[0]).lower() for item in cursor.description or ())
                if names != query.output:
                    raise Failure(
                        "RESULT_SCHEMA", "Oracle output did not match the approved schema.", 503
                    )
                records = cursor.fetchmany(query.validated_plan.plan.limit + 1)
                self._check_deadline(deadline, cancelled)
                dates = {
                    dimension.id
                    for dimension in self.validator.catalog.dimensions
                    if dimension.kind == "date"
                }
                rows = self._rows(names, records[: query.validated_plan.plan.limit], dates)
                return ExecutionResult(
                    rows=rows,
                    truncated=len(records) > query.validated_plan.plan.limit,
                    duration_ms=(time.perf_counter() - started) * 1000,
                )
        except oracledb.Error as error:
            self._check_deadline(deadline, cancelled)
            code = str(getattr(error.args[0], "full_code", "")) if error.args else ""
            if code in {"DPY-4024", "DPI-1067", "DPI-1080"}:
                raise Failure("QUERY_TIMEOUT", "The query timed out.", 504) from error
            raise Failure("ORACLE_UNAVAILABLE", "Oracle execution failed.", 503) from error
        finally:
            finished.set()
            watcher.join(timeout=0.2)
            self._release(connection, watcher.is_alive() or cancel_failed.is_set())

    @staticmethod
    def _check_deadline(deadline: float, cancellation: Event) -> None:
        if cancellation.is_set():
            raise Failure("QUERY_CANCELLED", "The query was cancelled.", 409)
        if time.time() >= deadline:
            raise Failure("QUERY_TIMEOUT", "The query timed out.", 504)

    def _rows(
        self,
        names: tuple[str, ...],
        records: list[tuple[object, ...]],
        dates: set[str] | None = None,
    ) -> tuple[Row, ...]:
        rows: list[Row] = []
        size = 0
        for record in records:
            row: Row = {}
            for key, value in zip(names, record, strict=True):
                scalar: Scalar
                if isinstance(value, Decimal):
                    if not value.is_finite():
                        raise Failure("RESULT_TYPE", "Non-finite Oracle number.", 503)
                    scalar = int(value) if value == value.to_integral_value() else str(value)
                elif isinstance(value, datetime) and key in (dates or set()):
                    if value.time().isoformat() != "00:00:00":
                        raise Failure(
                            "RESULT_TYPE", "A business DATE contained a time component.", 503
                        )
                    scalar = value.date().isoformat()
                elif isinstance(value, (date, datetime)):
                    scalar = value.isoformat()
                elif isinstance(value, (str, int, type(None))):
                    scalar = value
                else:
                    raise Failure("RESULT_TYPE", "Unsupported Oracle output type.", 503)
                row[key] = scalar
            size += len(json.dumps(row).encode())
            if size > self.config.max_result_bytes:
                raise Failure("RESULT_LIMIT", "Please narrow the result set.", 413)
            rows.append(row)
        return tuple(rows)

    def _release(self, connection: OracleConnection, unsafe: bool) -> None:
        clean = False
        try:
            try:
                connection.rollback()
            finally:
                self.policy.reset(connection)
            clean = True
        finally:
            if unsafe or not clean:
                try:
                    self.pool.drop(connection)
                finally:
                    raise Failure(
                        "ORACLE_CLEANUP",
                        "Oracle session cleanup failed; the connection was discarded.",
                        503,
                    ) from None
        try:
            self.pool.release(connection)
        except oracledb.Error as error:
            raise Failure("ORACLE_UNAVAILABLE", "Oracle release failed.", 503) from error

    def close(self) -> None:
        """Release the approved connection pool."""
        self.pool.close()

    def ready(self) -> None:
        """Only an explicitly approved query account may perform this liveness read."""
        connection: OracleConnection | None = None
        try:
            connection = self.pool.acquire()
            connection.call_timeout = self.config.timeout_ms
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchmany(1)
        except oracledb.Error as error:
            raise Failure("ORACLE_UNAVAILABLE", "Oracle readiness failed.", 503) from error
        finally:
            if connection is not None:
                self._release(connection, False)

    def resolve_entity(
        self,
        entity: EntityMapping,
        phrase: str,
        principal: Principal,
        deadline: float | None = None,
    ) -> str:
        """Certified exact lookup uses the same read-only principal context and cleanup."""
        sql, parameters = entity_query(self.validator.catalog, entity, phrase, principal, "oracle")
        end = min(
            deadline or time.time() + self.config.timeout_ms / 1000,
            time.time() + self.config.timeout_ms / 1000,
        )
        try:
            connection = self.pool.acquire()
        except oracledb.Error as error:
            raise Failure(
                "ORACLE_UNAVAILABLE", "Oracle entity lookup is unavailable.", 503
            ) from error
        try:
            self._check_deadline(end, Event())
            connection.call_timeout = max(1, int((end - time.time()) * 1000))
            connection.rollback()
            self.policy.apply(connection, principal)
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute(sql, parameters, fetch_decimals=True, fetch_lobs=False)
                matches = cursor.fetchmany(2)
                self._check_deadline(end, Event())
                return exact_entity(matches)
        except oracledb.Error as error:
            raise Failure(
                "ORACLE_UNAVAILABLE", "Oracle entity lookup is unavailable.", 503
            ) from error
        finally:
            self._release(connection, False)
