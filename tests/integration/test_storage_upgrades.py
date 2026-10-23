"""Previous storage formats survive upgrades without rewriting signed evidence."""

import sqlite3
from contextlib import closing

import pytest
from nl2sql.domain.fingerprints import digest
from nl2sql.domain.metadata import BundleSpec, ChangeImpact
from nl2sql.domain.models import Failure
from nl2sql.domain.physical import PhysicalInventory
from nl2sql.infrastructure.metadata.store import MetadataRepository
from nl2sql.infrastructure.sessions import SessionStore


def candidate():
    return BundleSpec(
        inventory=PhysicalInventory(
            source_id="upgrade-fixture",
            source_kind="synthetic",
            classification="synthetic",
            owners=("TEST",),
            objects=(),
        ),
        catalog=None,
        impact=ChangeImpact(changes=()),
    )


def test_legacy_metadata_payload_and_identity_survive_upgrade(tmp_path):
    original = candidate()
    legacy_payload = original.model_dump_json()
    legacy_id = digest(legacy_payload)
    with closing(sqlite3.connect(tmp_path / "metadata.db")) as connection, connection:
        connection.execute(
            "CREATE TABLE versions(id TEXT PRIMARY KEY,payload TEXT NOT NULL,"
            "state TEXT NOT NULL,approvals TEXT NOT NULL DEFAULT '[]')"
        )
        connection.execute(
            "INSERT INTO versions(id,payload,state) VALUES(?,?,?)",
            (legacy_id, legacy_payload, "pending_approval"),
        )
        connection.execute("PRAGMA user_version=0")
        before = connection.execute("SELECT id,payload FROM versions").fetchone()
    legacy_reader = MetadataRepository(tmp_path, read_only=True)
    try:
        assert legacy_reader.get(legacy_id).spec.id == legacy_id
    finally:
        legacy_reader.close()
    upgraded = MetadataRepository(tmp_path)
    try:
        assert upgraded.get(legacy_id).spec.id == legacy_id
        with closing(sqlite3.connect(tmp_path / "metadata.db")) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
            assert connection.execute("SELECT id,payload FROM versions").fetchone() == before
    finally:
        upgraded.close()


def test_future_storage_version_fails_without_modifying_data(tmp_path):
    path = tmp_path / "sessions.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA user_version=999")
    with pytest.raises(Failure) as error:
        SessionStore(path)
    assert error.value.code == "STORAGE_VERSION"
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 999
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []


def test_versioned_bundle_reader_preserves_identity_and_detects_changes():
    original = candidate()
    restored = BundleSpec.read_payload(original.payload_json(), 2)
    assert restored.id == original.id
    assert restored.created_at == original.created_at
    assert restored.inventory.discovered_at == original.inventory.discovered_at

    class FutureBundle(BundleSpec):
        harmless_future_default: str = ""

    assert FutureBundle.read_payload(original.payload_json(), 2).id == original.id
    assert restored.model_copy(update={"issues": ("changed",)}).id != original.id
    with pytest.raises(ValueError, match="format"):
        BundleSpec.read_payload(original.model_dump_json(), 999)


def test_session_schema_upgrades_and_rejects_unknown_message_format(tmp_path):
    path = tmp_path / "sessions.db"
    sessions = SessionStore(path)
    state = sessions.create("owner", "legacy")
    sessions.close()
    with closing(sqlite3.connect(path)) as connection, connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        connection.execute(
            "INSERT INTO messages(session_id,body,format_version) VALUES(?,?,?)",
            (state.session_id, "{}", 999),
        )
    reopened = SessionStore(path)
    try:
        with pytest.raises(Failure) as error:
            reopened.messages(state.session_id, "owner")
        assert error.value.code == "STORAGE_VERSION"
    finally:
        reopened.close()


def test_real_v0_history_survives_upgrade_and_sqlite_backup_restore(tmp_path):
    path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(path)) as source, source:
        source.executescript("""
            CREATE TABLE sessions(id TEXT PRIMARY KEY,owner TEXT NOT NULL,title TEXT NOT NULL,
                updated_at TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 0,plan TEXT);
            CREATE TABLE messages(id INTEGER PRIMARY KEY,session_id TEXT NOT NULL,body TEXT NOT NULL);
            INSERT INTO sessions VALUES('old-session','owner','legacy','2099-01-01T00:00:00+00:00',0,NULL);
            INSERT INTO messages(session_id,body) VALUES('old-session',
                '{"role":"user","content":"fictional legacy question","timestamp":"2026-01-01"}');
        """)
        with closing(sqlite3.connect(tmp_path / "backup.db")) as backup:
            source.backup(backup)
    for target in (path, tmp_path / "backup.db"):
        upgraded = SessionStore(target)
        try:
            assert (
                upgraded.messages("old-session", "owner")[0].content == "fictional legacy question"
            )
            assert upgraded.state("old-session", "owner").pending is None
        finally:
            upgraded.close()
