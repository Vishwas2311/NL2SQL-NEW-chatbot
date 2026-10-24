"""Small typed boundary for the pinned, process-local SurrealDB engine."""

from typing import cast

from surrealdb import Surreal
from surrealdb.connections.blocking_embedded import BlockingEmbeddedSurrealConnection
from surrealdb.types import Value


def open_projection() -> BlockingEmbeddedSurrealConnection:
    """Every projection owns an independent memory store; no remote endpoint is accepted."""
    connection = cast(BlockingEmbeddedSurrealConnection, Surreal("mem://"))
    try:
        connection.connect()
        connection.use("nl2sql", "projection")
        return connection
    except BaseException:
        connection.close()
        raise


def records(
    connection: BlockingEmbeddedSurrealConnection,
    query: str,
    values: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    """Only application-owned, single-statement queries cross this boundary."""
    result = cast(object, connection.query(query, cast(dict[str, Value] | None, values)))
    if not isinstance(result, list):
        raise ValueError("Invalid embedded projection response")
    if any(not isinstance(row, dict) for row in cast(list[object], result)):
        raise ValueError("Invalid embedded projection response")
    return cast(list[dict[str, object]], result)
