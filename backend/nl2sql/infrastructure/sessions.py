"""Transactional, owner-scoped conversation persistence with optimistic concurrency."""

import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import RLock
from uuid import uuid4

from nl2sql.domain.models import Answer, Failure, QueryPlan
from nl2sql.domain.planning import PendingQuestion
from nl2sql.domain.sessions import Message, SessionState, SessionSummary
from nl2sql.infrastructure.storage import migrate, require_format, schema_version, storage_errors
from nl2sql.telemetry import REQUEST_DEADLINE, STAGE_SPANS, measured


class SessionStore:
    """One local write connection with a lock; SQLite CAS protects multiple workers."""

    @storage_errors
    def __init__(self, path: Path, retention_days: int = 30, max_bytes: int = 4_000_000) -> None:
        self.retention_days = retention_days
        self.max_bytes = max_bytes
        self._lock = RLock()
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=3)
        try:
            self._connection.row_factory = sqlite3.Row
            schema_version(self._connection)
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            migrate(
                self._connection,
                """
                CREATE TABLE IF NOT EXISTS sessions(
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
                    updated_at TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0, plan TEXT);
                CREATE INDEX IF NOT EXISTS sessions_owner ON sessions(owner,updated_at);
                CREATE TABLE IF NOT EXISTS messages(
                    id INTEGER PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id)
                    ON DELETE CASCADE, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id,id);
            """,
                (("sessions", "plan_format"), ("messages", "format_version")),
                (("sessions", "pending"), ("sessions", "plan_scope")),
            )
        except BaseException:
            self._connection.close()
            raise

    @contextmanager
    def _locked(self) -> Generator[None]:
        """Bound write-lock queuing within the turn deadline and measure actual contention."""
        began = time.perf_counter()
        deadline = REQUEST_DEADLINE.get()
        remaining = 3.0 if deadline is None else deadline - time.time()
        if remaining <= 0:
            raise Failure("REQUEST_TIMEOUT", "The request deadline expired.", "timeout")
        # RLock's context-manager entry has no timeout parameter.
        acquired = self._lock.acquire(  # pylint: disable=consider-using-with
            timeout=max(0, remaining)
        )
        if not acquired:
            raise Failure(
                "SESSION_BUSY", "Conversation storage is busy; please retry.", "unavailable"
            )
        try:
            remaining = 3.0 if deadline is None else deadline - time.time()
            if remaining <= 0:
                raise Failure("REQUEST_TIMEOUT", "The request deadline expired.", "timeout")
            # PRAGMA cannot bind values; this bounded integer comes only from the deadline.
            milliseconds = max(0, int(min(3.0, remaining) * 1000))
            self._connection.execute(f"PRAGMA busy_timeout={milliseconds}")
            spans = STAGE_SPANS.get()
            if spans is not None:
                spans["session_queue_ms"] = (
                    spans.get("session_queue_ms", 0) + (time.perf_counter() - began) * 1000
                )
            yield
        finally:
            self._lock.release()

    @measured("session_create_ms")
    @storage_errors
    def create(self, owner: str, title: str) -> SessionState:
        """Server generates unguessable identifiers and binds ownership at creation."""
        key = str(uuid4())
        with self._locked(), self._connection:
            self._connection.execute(
                "INSERT INTO sessions(id,owner,title,updated_at) VALUES(?,?,?,?)",
                (key, owner, title[:100], datetime.now(UTC).isoformat()),
            )
        return SessionState(session_id=key, version=0, last_plan=None)

    @measured("session_state_ms")
    @storage_errors
    def state(self, key: str, owner: str) -> SessionState:
        """Recheck owner and expiry on all reads, appends and deletes."""
        with self._locked():
            row = self._connection.execute(
                "SELECT version,plan,updated_at,plan_format,pending,plan_scope "
                "FROM sessions WHERE id=? AND owner=?",
                (key, owner),
            ).fetchone()
        if row is None or datetime.fromisoformat(str(row["updated_at"])) < datetime.now(
            UTC
        ) - timedelta(days=self.retention_days):
            raise Failure("SESSION_NOT_FOUND", "The conversation was not found.", "not_found")
        require_format(int(row["plan_format"]))
        raw: object = row["plan"]
        plan = QueryPlan.model_validate_json(raw) if isinstance(raw, str) else None
        return SessionState(
            session_id=key,
            version=int(row["version"]),
            last_plan=plan,
            pending=PendingQuestion.model_validate_json(row["pending"]) if row["pending"] else None,
            scope_digest=str(row["plan_scope"] or ""),
        )

    @storage_errors
    def list_owned(self, owner: str) -> tuple[SessionSummary, ...]:
        """Bound listing and filter on owner in SQL, never in the browser."""
        cutoff = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()
        with self._locked():
            records = self._connection.execute(
                "SELECT id,title,updated_at FROM sessions WHERE owner=? AND updated_at>=? "
                "ORDER BY updated_at DESC LIMIT 100",
                (owner, cutoff),
            ).fetchall()
        return tuple(
            SessionSummary(
                session_id=str(row[0]), title=str(row[1]), updated_at=str(row[2]), user_id=owner
            )
            for row in records
        )

    @storage_errors
    def messages(
        self, key: str, owner: str, scope_digest: str | None = None
    ) -> tuple[Message, ...]:
        """Authorized history remains available across process restarts."""
        with self._locked():
            self.state(key, owner)
            stored_bytes = self._connection.execute(
                "SELECT COALESCE(SUM(length(CAST(body AS BLOB))),0) "
                "FROM messages WHERE session_id=?",
                (key,),
            ).fetchone()[0]
            if stored_bytes > self.max_bytes:
                raise Failure(
                    "SESSION_FULL", "Conversation history exceeds its storage budget.", "conflict"
                )
            records = self._connection.execute(
                "SELECT body,format_version FROM messages WHERE session_id=? ORDER BY id LIMIT 200",
                (key,),
            ).fetchall()
        for record in records:
            require_format(int(record[1]))
        messages = tuple(Message.model_validate_json(str(row[0])) for row in records)
        if scope_digest is None:
            return messages
        return tuple(
            message
            if message.scope_digest == scope_digest
            else message.model_copy(
                update={
                    "results": (),
                    "content": "Historical content is unavailable after access changed.",
                }
            )
            for message in messages
        )

    @measured("session_append_ms")
    @storage_errors
    def append(
        self,
        state: SessionState,
        owner: str,
        question: str,
        answer: Answer,
        plan: QueryPlan | None,
        scope_digest: str = "",
        pending: PendingQuestion | None = None,
    ) -> None:
        """Commit user/assistant pair and context together; stale tabs cannot overwrite."""
        now = datetime.now(UTC).isoformat()
        reference = answer.provenance.query_reference if answer.provenance else None
        messages = (
            Message(role="user", content=question, timestamp=now, scope_digest=scope_digest),
            Message(
                role="assistant",
                content=answer.message,
                results=answer.rows,
                timestamp=now,
                query_reference=reference,
                scope_digest=scope_digest,
            ),
        )
        payloads = tuple(item.model_dump_json() for item in messages)
        with self._locked(), self._connection:
            self.state(state.session_id, owner)
            count, stored_bytes = self._connection.execute(
                "SELECT count(*),COALESCE(SUM(length(CAST(body AS BLOB))),0) FROM messages "
                "WHERE session_id=?",
                (state.session_id,),
            ).fetchone()
            if (
                count >= 200
                or stored_bytes + sum(len(body.encode("utf-8")) for body in payloads)
                > self.max_bytes
            ):
                raise Failure("SESSION_FULL", "Start a new conversation.", "conflict")
            cursor = self._connection.execute(
                "UPDATE sessions SET version=version+1,updated_at=?,plan=?,pending=?,plan_scope=? "
                "WHERE id=? AND owner=? AND version=?",
                (
                    now,
                    plan.model_dump_json() if plan else None,
                    pending.model_dump_json() if pending else None,
                    scope_digest,
                    state.session_id,
                    owner,
                    state.version,
                ),
            )
            if cursor.rowcount != 1:
                raise Failure(
                    "SESSION_CONFLICT", "The conversation changed; please retry.", "conflict"
                )
            self._connection.executemany(
                "INSERT INTO messages(session_id,body) VALUES(?,?)",
                ((state.session_id, body) for body in payloads),
            )

    @storage_errors
    def delete(self, key: str, owner: str) -> None:
        """Delete only the authenticated owner's conversation and message rows."""
        with self._locked(), self._connection:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE id=? AND owner=?", (key, owner)
            )
            if cursor.rowcount != 1:
                raise Failure("SESSION_NOT_FOUND", "The conversation was not found.", "not_found")

    @storage_errors
    def purge_expired(self, limit: int = 1000) -> int:
        """Bounded maintenance outside API workers; normal reads do not run cleanup jobs."""
        if not 1 <= limit <= 1000:
            raise ValueError("Session purge batch must be between 1 and 1000")
        cutoff = (datetime.now(UTC) - timedelta(days=self.retention_days)).isoformat()
        with self._locked(), self._connection:
            cursor = self._connection.execute(
                "DELETE FROM sessions WHERE id IN (SELECT id FROM sessions WHERE updated_at<? "
                "ORDER BY updated_at LIMIT ?)",
                (cutoff, limit),
            )
        return cursor.rowcount

    @storage_errors
    def close(self) -> None:
        """Release local persistence at application shutdown."""
        self._connection.close()
