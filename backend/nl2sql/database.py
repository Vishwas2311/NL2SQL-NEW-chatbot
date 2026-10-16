"""Read-only SQLite execution, bounded pooling, preflight and secure entity lookup."""

import json
import sqlite3
import time
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from pathlib import Path
from queue import Empty, Queue
from typing import Literal, cast

from nl2sql.config import Settings
from nl2sql.domain import (
    Bind,
    Capability,
    EntityMapping,
    ExecutionResult,
    Failure,
    Principal,
    Row,
    Scalar,
)
from nl2sql.entity_lookup import entity_query, exact_entity
from nl2sql.security import SQLValidator
from nl2sql.telemetry import STAGE_SPANS


def _check_integer_binds(values: Iterable[Bind]) -> None:
    """Reject integers outside SQLite's native range before acquiring a query handle."""
    if any(isinstance(value, int) and not -(2**63) <= value < 2**63 for value in values):
        raise Failure("NUMERIC_RANGE", "This value is outside the configured numeric range.")


class SQLiteDatabase:
    """Preopened read-only connections, distinct from session-write storage."""

    dialect: Literal["sqlite"] = "sqlite"

    def __init__(self, path: Path, validator: SQLValidator, settings: Settings) -> None:
        self.validator = validator
        self.settings = settings
        self._pool: Queue[sqlite3.Connection] = Queue(settings.pool_size)
        self.execute_count = 0
        for _ in range(settings.pool_size):
            connection = sqlite3.connect(
                path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False, timeout=1
            )
            connection.execute("PRAGMA query_only=ON")
            connection.row_factory = sqlite3.Row
            self._pool.put(connection)

    @contextmanager
    def connection(self, timeout: float = 1) -> Generator[sqlite3.Connection]:
        """Bound pool waits and always reset per-request SQLite callbacks."""
        started = time.perf_counter()
        try:
            connection = self._pool.get(timeout=max(0.001, timeout))
        except Empty as error:
            raise Failure("POOL_EXHAUSTED", "The query service is busy.", 503) from error
        spans = STAGE_SPANS.get()
        if spans is not None:
            spans["pool_queue_ms"] = (
                spans.get("pool_queue_ms", 0) + (time.perf_counter() - started) * 1000
            )
        try:
            yield connection
        finally:
            connection.set_progress_handler(None, 0)
            connection.set_authorizer(None)
            self._pool.put(connection)

    def execute(self, capability: Capability, principal: Principal) -> ExecutionResult:
        """The only business-query execution interface accepts signed authority."""
        query = self.validator.verify(capability, principal)
        if query.dialect != "sqlite":
            raise Failure("DIALECT_ERROR", "The database dialect is unsupported.")
        parameters = dict(query.binds)
        _check_integer_binds(parameters.values())
        end = min(capability.expires_at, time.time() + self.settings.query_timeout_seconds)
        if len(query.validated_plan.proof.relationships) > 5:
            raise Failure("PREFLIGHT_REJECTED", "The query exceeds the resource budget.")
        start = time.perf_counter()
        tables = set(query.validated_plan.proof.tables)

        def authorizer(
            action: int,
            first: str | None,
            second: str | None,
            _database: str | None,
            _source: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if first in tables else sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION:
                return (
                    sqlite3.SQLITE_OK
                    if second
                    in {"sum", "count", "min", "max", "avg", "row_number", "dense_rank", "coalesce"}
                    else sqlite3.SQLITE_DENY
                )
            return sqlite3.SQLITE_OK if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_DENY

        try:
            with self.connection(end - time.time()) as connection:
                self.validator.verify(capability, principal)
                connection.set_authorizer(authorizer)
                connection.set_progress_handler(lambda: int(time.time() >= end), 100)
                if time.time() >= end:
                    raise Failure("QUERY_TIMEOUT", "The query timed out.", 504)
                self.execute_count += 1
                cursor = connection.execute(query.sql, parameters)
                rows = cursor.fetchmany(query.validated_plan.plan.limit + 1)
                output: list[Row] = []
                byte_count = 0
                for row in rows[: query.validated_plan.plan.limit]:
                    values: Row = {}
                    for key in row.keys():
                        value: object = row[key]
                        if not isinstance(value, (str, int, type(None))):
                            raise Failure(
                                "RESULT_TYPE", "The database returned an unsupported value.", 503
                            )
                        values[key] = cast(Scalar, value)
                    byte_count += len(json.dumps(values).encode())
                    if byte_count > self.settings.max_result_bytes:
                        raise Failure("RESULT_LIMIT", "Please narrow the result set.", 413)
                    output.append(values)
        except sqlite3.Error as error:
            if time.time() >= end:
                raise Failure("QUERY_TIMEOUT", "The query timed out.", 504) from error
            raise Failure(
                "DB_UNAVAILABLE", "The database is temporarily unavailable.", 503
            ) from error
        return ExecutionResult(
            rows=tuple(output),
            truncated=len(rows) > query.validated_plan.plan.limit,
            duration_ms=(time.perf_counter() - start) * 1000,
        )

    def resolve_customer(self, phrase: str, principal: Principal) -> str:
        """Compatibility helper; physical names belong to the catalog entity mapping."""
        entity = next(
            (item for item in self.validator.catalog.entities if item.id == "customer"), None
        )
        if entity is None:
            raise Failure("ENTITY_NOT_FOUND", "No certified entity mapping is available.")
        return self.resolve_entity(entity, phrase, principal)

    def resolve_entity(
        self,
        entity: EntityMapping,
        phrase: str,
        principal: Principal,
        deadline: float | None = None,
    ) -> str:
        """Bounded exact lookup under certified tenant/scope constraints."""
        sql, parameters = entity_query(self.validator.catalog, entity, phrase, principal, "sqlite")
        _check_integer_binds(parameters.values())
        end = min(
            deadline or time.time() + self.settings.query_timeout_seconds,
            time.time() + self.settings.query_timeout_seconds,
        )
        try:
            with self.connection(end - time.time()) as connection:
                connection.set_progress_handler(lambda: int(time.time() >= end), 100)
                matches = [tuple(row) for row in connection.execute(sql, parameters).fetchmany(2)]
        except sqlite3.Error as error:
            raise Failure(
                "DB_UNAVAILABLE", "Entity lookup is temporarily unavailable.", 503
            ) from error
        return exact_entity(matches)

    def close(self) -> None:
        """Called after active API requests finish during shutdown."""
        while not self._pool.empty():
            self._pool.get_nowait().close()

    def ready(self) -> None:
        """Transport delegates its readiness check to the configured adapter."""
        with self.connection() as connection:
            connection.execute("SELECT 1").fetchone()
