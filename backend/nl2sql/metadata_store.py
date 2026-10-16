"""Private, transactional metadata lifecycle and a durable atomic active-version pointer."""

import json
import sqlite3
import time
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from pydantic import Field

from nl2sql.catalog import digest
from nl2sql.domain import Catalog, Failure, FrozenModel, Principal
from nl2sql.drift import ChangeImpact
from nl2sql.physical import PhysicalInventory

Lifecycle = Literal[
    "discovered",
    "pending_verification",
    "verified_physical",
    "pending_approval",
    "certified",
    "published",
    "superseded",
    "retired",
    "rejected",
]


class BundleArtifacts(FrozenModel):
    """Derived structures are reproducible from the signed catalog and current implementation."""

    catalog_digest: str
    physical_digest: str
    graph_digest: str
    search_digest: str
    policy_digest: str
    compiler_digest: str
    encoder_version: str | None = None
    vector_digest: str | None = None
    build_ms: float = 0
    rebuilt: tuple[str, ...] = ()


class BundleSpec(FrozenModel):
    """Immutable candidate content; lifecycle status and review tokens are separate records."""

    inventory: PhysicalInventory
    base_version: str | None = None
    catalog: Catalog | None
    principals: tuple[Principal, ...] = Field(default=(), max_length=128)
    artifacts: BundleArtifacts | None = None
    impact: ChangeImpact
    issues: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def id(self) -> str:
        """Approvals bind every source, mapping, permission and derived-artifact reference."""
        return digest(self.model_dump_json())


class MetadataRecord(FrozenModel):
    """An arbitrary status/file can never stand in for signature verification."""

    spec: BundleSpec
    state: Lifecycle
    approvals: tuple[str, ...] = ()


class MetadataControl(FrozenModel):
    """Revision provides compare-and-swap coordination across processes sharing this store."""

    active: str | None
    revision: int
    blocked_views: tuple[str, ...]


class MetadataRepository:
    """Use an approved restricted local volume; the exporter respects its private marker."""

    def __init__(self, root: Path, read_only: bool = False) -> None:
        self.root = root.resolve()
        if not read_only:
            self.root.mkdir(parents=True, exist_ok=True)
            (self.root / ".metadata-private").touch(exist_ok=True)
        self.read_only = read_only
        self._lease_owner: ContextVar[str | None] = ContextVar("metadata_lease_owner", default=None)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            (self.root / "metadata.db").as_uri() + "?mode=ro"
            if read_only
            else self.root / "metadata.db",
            uri=read_only,
            check_same_thread=False,
            timeout=5,
        )
        if read_only:
            return
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,payload TEXT NOT NULL,
                state TEXT NOT NULL,approvals TEXT NOT NULL DEFAULT '[]');
            CREATE TABLE IF NOT EXISTS control(id INTEGER PRIMARY KEY CHECK(id=1),
                active TEXT,revision INTEGER NOT NULL,blocked TEXT NOT NULL);
            INSERT OR IGNORE INTO control VALUES(1,NULL,0,'[]');
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT NOT NULL,
                event TEXT NOT NULL,version TEXT,actor TEXT,code TEXT);
            CREATE TABLE IF NOT EXISTS leases(name TEXT PRIMARY KEY,owner TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS schedule(id INTEGER PRIMARY KEY CHECK(id=1),enabled INTEGER NOT NULL,
                interval_seconds INTEGER NOT NULL,next_at REAL NOT NULL,dry_run INTEGER NOT NULL);
            INSERT OR IGNORE INTO schedule VALUES(1,0,900,0,1);
        """)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection]:
        """BEGIN before reading state, so multiple CLI processes cannot lose updates."""
        if self.read_only:
            raise Failure("DRY_RUN_WRITE", "A dry run cannot change metadata state.", 403)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            yield self._connection

    def control(self) -> MetadataControl:
        """This small local read never polls Oracle on a chat request."""
        with self._lock:
            row = self._connection.execute(
                "SELECT active,revision,blocked FROM control WHERE id=1"
            ).fetchone()
        assert row is not None
        return MetadataControl(
            active=row[0], revision=int(row[1]), blocked_views=tuple(json.loads(row[2]))
        )

    def get(self, version: str) -> MetadataRecord:
        """Recompute the immutable payload identity before any approval or recovery."""
        with self._lock:
            row = self._connection.execute(
                "SELECT payload,state,approvals FROM versions WHERE id=?", (version,)
            ).fetchone()
        if row is None:
            raise Failure("VERSION_NOT_FOUND", "The metadata version was not found.", 404)
        record = MetadataRecord(
            spec=BundleSpec.model_validate_json(row[0]),
            state=row[1],
            approvals=tuple(json.loads(row[2])),
        )
        if record.spec.id != version:
            raise Failure(
                "METADATA_INTEGRITY", "Metadata content failed integrity validation.", 503
            )
        return record

    def latest(self) -> MetadataRecord | None:
        """Bound history is separate from candidate payloads and private metadata text."""
        with self._lock:
            row = self._connection.execute(
                "SELECT id FROM versions ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
        return self.get(row[0]) if row else None

    def policy_version_conflict(
        self, version: str, fingerprint: str, active_revision: str | None = None
    ) -> bool:
        """A human revision label must never identify two different history-access policies."""
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM versions WHERE json_extract(payload,'$.catalog.policy_version')=? "
                "AND (json_extract(payload,'$.artifacts.policy_digest')<>? "
                "OR (? IS NOT NULL AND ?<>? AND EXISTS "
                "(SELECT 1 FROM events WHERE events.version=versions.id "
                "AND event IN ('published','rollback')))) LIMIT 1",
                (version, fingerprint, active_revision, active_revision, version),
            ).fetchone()
        return row is not None

    def stage(self, spec: BundleSpec) -> MetadataRecord:
        """Commit a complete immutable candidate; active state is untouched."""
        state: Lifecycle = "pending_verification" if spec.issues else "pending_approval"
        with self.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO versions(id,payload,state) VALUES(?,?,?)",
                (spec.id, spec.model_dump_json(), state),
            )
            self._event(connection, "candidate_staged", spec.id, None, None)
        return self.get(spec.id)

    def quarantine(self, views: tuple[str, ...]) -> None:
        """Known broken physical mappings block affected old bundles, including in-flight caps."""
        if not views:
            return
        with self.transaction() as connection:
            row = connection.execute("SELECT blocked FROM control WHERE id=1").fetchone()
            blocked = tuple(sorted(set(json.loads(row[0])) | set(views)))
            connection.execute(
                "UPDATE control SET blocked=?,revision=revision+1 WHERE id=1",
                (json.dumps(blocked),),
            )
            self._event(connection, "physical_quarantine", None, None, "SCHEMA_DRIFT")

    def set_approvals(
        self, version: str, approvals: tuple[str, ...], actor: str, complete: bool
    ) -> MetadataRecord:
        """Caller verifies identities; readers independently verify signatures again."""
        with self.transaction() as connection:
            changed = connection.execute(
                "UPDATE versions SET approvals=?,state=? WHERE id=? "
                "AND state IN ('pending_approval','certified')",
                (json.dumps(approvals), "certified" if complete else "pending_approval", version),
            ).rowcount
            if changed != 1:
                raise Failure(
                    "LIFECYCLE_DENIED",
                    "The metadata version cannot be approved in this state.",
                    409,
                )
            self._event(connection, "approval_recorded", version, actor, None)
        return self.get(version)

    def activate(
        self, version: str, expected: MetadataControl, actor: str, rollback: bool = False
    ) -> MetadataControl:
        """One durable transaction is the publication linearization point."""
        with self.transaction() as connection:
            lease = connection.execute(
                "SELECT owner,expires FROM leases WHERE name='refresh'"
            ).fetchone()
            if (
                lease is None
                or lease[0] != self._lease_owner.get()
                or float(lease[1]) <= time.time()
            ):
                raise Failure(
                    "REFRESH_LEASE_EXPIRED", "The refresh lease expired; retry publication.", 409
                )
            row = connection.execute("SELECT state FROM versions WHERE id=?", (version,)).fetchone()
            allowed = {"published", "superseded", "certified"} if rollback else {"certified"}
            if row is None or row[0] not in allowed:
                raise Failure("LIFECYCLE_DENIED", "A certified metadata version is required.", 409)
            changed = connection.execute(
                "UPDATE control SET active=?,revision=revision+1,blocked='[]' "
                "WHERE id=1 AND revision=? AND active IS ?",
                (version, expected.revision, expected.active),
            ).rowcount
            if changed != 1:
                raise Failure(
                    "PUBLICATION_CONFLICT",
                    "Another metadata operation changed the active state.",
                    409,
                )
            if expected.active is not None and expected.active != version:
                connection.execute(
                    "UPDATE versions SET state='superseded' WHERE id=?", (expected.active,)
                )
            connection.execute("UPDATE versions SET state='published' WHERE id=?", (version,))
            self._event(connection, "rollback" if rollback else "published", version, actor, None)
        return self.control()

    def retire(self, version: str, actor: str, rejected: bool = False) -> None:
        """Never retire the active version behind in-flight requests."""
        with self.transaction() as connection:
            row = connection.execute("SELECT active FROM control WHERE id=1").fetchone()
            if row[0] == version:
                raise Failure("LIFECYCLE_DENIED", "Publish a replacement before retirement.", 409)
            changed = connection.execute(
                "UPDATE versions SET state=? WHERE id=?",
                ("rejected" if rejected else "retired", version),
            ).rowcount
            if changed != 1:
                raise Failure("VERSION_NOT_FOUND", "The metadata version was not found.", 404)
            self._event(connection, "retired", version, actor, None)

    def history(self) -> tuple[dict[str, object], ...]:
        """Routine status contains opaque IDs and safe error codes, not schema descriptions."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT at,event,version,actor,code FROM events ORDER BY id DESC LIMIT 100"
            ).fetchall()
        return tuple(
            dict(zip(("at", "event", "version", "actor", "code"), row, strict=True)) for row in rows
        )

    def record_failure(self, code: str) -> None:
        """Never persist provider exception text or credentials."""
        with self.transaction() as connection:
            self._event(connection, "refresh_failed", None, None, code)

    @staticmethod
    def _event(
        connection: sqlite3.Connection,
        event: str,
        version: str | None,
        actor: str | None,
        code: str | None,
    ) -> None:
        connection.execute(
            "INSERT INTO events(at,event,version,actor,code) VALUES(?,?,?,?,?)",
            (datetime.now(UTC).isoformat(), event, version, actor, code),
        )

    @contextmanager
    def refresh_lease(
        self, seconds: int = 300, name: Literal["refresh", "schedule"] = "refresh"
    ) -> Generator[None]:
        """A bounded cross-process lease prevents duplicate discovery loops and refresh jobs."""
        if not 1 <= seconds <= 300:
            raise ValueError("Refresh lease must be between 1 and 300 seconds")
        identity = str(uuid4())
        with self.transaction() as connection:
            row = connection.execute("SELECT expires FROM leases WHERE name=?", (name,)).fetchone()
            if row is not None and float(row[0]) > time.time():
                raise Failure("REFRESH_BUSY", "Another metadata refresh is already running.", 409)
            connection.execute(
                "INSERT OR REPLACE INTO leases VALUES(?,?,?)",
                (name, identity, time.time() + seconds),
            )
        token = self._lease_owner.set(identity)
        try:
            yield
        finally:
            self._lease_owner.reset(token)
            with self.transaction() as connection:
                connection.execute("DELETE FROM leases WHERE name=? AND owner=?", (name, identity))

    def candidates(self) -> tuple[dict[str, object], ...]:
        """Opaque status listing; detailed payload review is a privileged CLI operation."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT id,state FROM versions ORDER BY rowid DESC LIMIT 100"
            ).fetchall()
        return tuple({"candidate_id": row[0], "state": row[1]} for row in rows)

    def configure_schedule(self, enabled: bool, interval: int, dry_run: bool, actor: str) -> None:
        """A separate approved scheduler owns polling; API workers never enable it."""
        if not 5 <= interval <= 86_400:
            raise ValueError("Refresh interval must be between 5 and 86400 seconds")
        with self.transaction() as connection:
            connection.execute(
                "UPDATE schedule SET enabled=?,interval_seconds=?,next_at=0,dry_run=? WHERE id=1",
                (int(enabled), interval, int(dry_run)),
            )
            self._event(connection, "schedule_configured", None, actor, None)

    def claim_schedule(self, now: float) -> bool | None:
        """One atomic due-time claim prevents duplicate poll loops across local processes."""
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT enabled,interval_seconds,next_at,dry_run FROM schedule WHERE id=1"
            ).fetchone()
            if not row[0] or float(row[2]) > now:
                return None
            connection.execute("UPDATE schedule SET next_at=? WHERE id=1", (now + int(row[1]),))
            return bool(row[3])

    def close(self) -> None:
        """Close after refresh and request users have drained."""
        self._connection.close()
