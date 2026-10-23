"""Ordered local schema upgrades; unknown future stores are never modified."""

import sqlite3
from collections.abc import Callable
from functools import wraps

from nl2sql.domain.models import Failure


def schema_version(connection: sqlite3.Connection, supported: int = 3) -> int:
    """Read-only inspection also supports legacy, unnumbered databases."""
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if not 0 <= version <= supported:
        raise Failure(
            "STORAGE_VERSION", "This storage version requires a compatible release.", "unavailable"
        )
    return version


def migrate(
    connection: sqlite3.Connection,
    baseline: str,
    columns: tuple[tuple[str, str], ...],
    context_columns: tuple[tuple[str, str], ...] = (),
) -> None:
    """Adopt v0 tables, then add record-format tags in one writer transaction."""
    schema_version(connection)
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        version = schema_version(connection)
        if version < 1:
            for statement in baseline.split(";"):
                if statement.strip():
                    connection.execute(statement)
            connection.execute("PRAGMA user_version=1")
        if version < 2:
            for table, field in columns:
                existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                if field not in existing:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN {field} INTEGER NOT NULL DEFAULT 1"
                    )
            connection.execute("PRAGMA user_version=2")
        if version < 3:
            for table, field in context_columns:
                existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
                if field not in existing:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {field} TEXT")
            connection.execute("PRAGMA user_version=3")


def require_format(version: int, supported: tuple[int, ...] = (1,)) -> None:
    """Reject future serialized records rather than coercing them into older contracts."""
    if version not in supported:
        raise Failure(
            "STORAGE_VERSION", "This record format requires a compatible release.", "unavailable"
        )


def storage_errors[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    """Translate driver failures where storage is owned, without exposing provider details."""

    @wraps(function)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except sqlite3.Error:
            raise Failure(
                "STORAGE_UNAVAILABLE", "Local storage is temporarily unavailable.", "unavailable"
            ) from None

    return invoke
