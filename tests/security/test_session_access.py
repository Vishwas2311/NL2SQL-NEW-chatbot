"""Protected session responses reauthorize, redact titles and bound durable history."""

import json
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from nl2sql.bootstrap.factory import create_app
from nl2sql.cli import main as cli
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.sessions import SessionStore
from nl2sql.telemetry import stage_metrics


@pytest.mark.parametrize("operation", ["list_owned", "messages"])
def test_revocation_during_session_read_blocks_response(
    settings, resources, credentials, monkeypatch, operation
):
    principal = settings.principals[0]
    answer = resources.service.chat("Show total loan exposure by region", None, principal, None, {})
    original = getattr(resources.sessions, operation)

    def read_then_revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        resources.auth.replace_principals(
            tuple(user for user in settings.principals if user.id != principal.id)
        )
        return result

    monkeypatch.setattr(resources.sessions, operation, read_then_revoke)
    with TestClient(create_app(settings, resources_factory=lambda *_: resources)) as client:
        path = (
            "/ews-chatbot/get_all_sessions"
            if operation == "list_owned"
            else f"/ews-chatbot/load_session/{answer.session_id}"
        )
        response = client.get(
            path, headers={"Authorization": "Bearer " + credentials[principal.id]}
        )
        assert response.status_code == 403
        assert "175000.50" not in response.text


def test_session_sidebar_never_returns_legacy_question_titles(settings, resources, credentials):
    resources.sessions.create("analyst", "Private fictional customer and financial threshold")
    principals = tuple(user.model_copy(update={"metrics": ()}) for user in settings.principals)
    resources.auth.replace_principals(principals)
    with TestClient(create_app(settings, resources_factory=lambda *_: resources)) as client:
        response = client.get(
            "/ews-chatbot/get_all_sessions",
            headers={"Authorization": "Bearer " + credentials["analyst"]},
        )
        assert response.status_code == 200
        assert response.json()["sessions"][0]["title"] == "Conversation"
        assert "Private fictional" not in response.text


def test_expired_sessions_remain_owner_deletable_and_purge_is_bounded(
    settings, resources, monkeypatch, capsys
):
    principal = settings.principals[0]
    answer = resources.service.chat("Show total loan exposure", None, principal, None, {})
    expired = resources.sessions.create(principal.id, "expired")
    fresh = resources.sessions.create(principal.id, "fresh")
    old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    path = settings.data_dir / "sessions.db"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "UPDATE sessions SET updated_at=? WHERE id IN (?,?)",
            (old, answer.session_id, expired.session_id),
        )
        connection.commit()
    with pytest.raises(Failure):
        resources.sessions.state(answer.session_id, principal.id)
    with pytest.raises(Failure):
        resources.sessions.delete(answer.session_id, settings.principals[1].id)
    resources.sessions.delete(answer.session_id, principal.id)
    with closing(sqlite3.connect(path)) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM messages WHERE session_id=?", (answer.session_id,)
            ).fetchone()[0]
            == 0
        )
    monkeypatch.setattr(
        "sys.argv",
        [
            "nl2sql",
            "purge-sessions",
            "--settings",
            str(settings.data_dir / "settings.json"),
            "--limit",
            "1",
        ],
    )
    cli.main()
    assert json.loads(capsys.readouterr().out) == {"deleted_sessions": 1}
    assert resources.sessions.state(fresh.session_id, principal.id)
    assert resources.sessions.purge_expired(1) == 0
    with pytest.raises(ValueError):
        resources.sessions.purge_expired(0)


def test_history_byte_budget_blocks_appends_atomically_and_legacy_reads(settings, resources):
    principal = settings.principals[0]
    answer = resources.service.chat("Show total loan exposure", None, principal, None, {})
    store = SessionStore(settings.data_dir / "sessions.db", max_bytes=1000)
    try:
        state = store.state(answer.session_id, principal.id)
        with pytest.raises(Failure) as full:
            store.append(state, principal.id, "fictional" * 1000, answer, state.last_plan)
        assert full.value.code == "SESSION_FULL"
        assert store.state(answer.session_id, principal.id).version == state.version
        with closing(sqlite3.connect(settings.data_dir / "sessions.db")) as connection:
            connection.execute(
                "UPDATE messages SET body=? WHERE session_id=?",
                ('{"oversized":"' + "x" * 2000 + '"}', answer.session_id),
            )
            connection.commit()
        with pytest.raises(Failure) as oversized:
            store.messages(answer.session_id, principal.id)
        assert oversized.value.code == "SESSION_FULL"
        store.delete(answer.session_id, principal.id)
    finally:
        store.close()


def test_expired_request_cannot_write_a_session(resources):
    before = resources.sessions.list_owned("analyst")
    with stage_metrics({}, time.time() - 1), pytest.raises(Failure) as expired:
        resources.sessions.create("analyst", "expired fictional request")
    assert expired.value.code == "REQUEST_TIMEOUT"
    assert resources.sessions.list_owned("analyst") == before


def test_history_lookup_uses_a_session_index_instead_of_scanning_all_conversations(
    settings, resources
):
    state = resources.sessions.create("analyst", "fictional indexed conversation")
    with closing(sqlite3.connect(settings.data_dir / "sessions.db")) as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT body FROM messages WHERE session_id=? ORDER BY id LIMIT 200",
            (state.session_id,),
        ).fetchall()
    details = " ".join(str(row[3]) for row in plan)
    assert "SEARCH messages" in details
    assert "SCAN messages" not in details
    assert "TEMP B-TREE" not in details


def test_database_writer_wait_is_bounded_by_remaining_request_budget(settings, resources):
    with closing(sqlite3.connect(settings.data_dir / "sessions.db")) as competing:
        competing.execute("BEGIN IMMEDIATE")
        try:
            began = time.monotonic()
            with stage_metrics({}, time.time() + 0.05), pytest.raises(Failure) as error:
                resources.sessions.create("analyst", "blocked fictional request")
            assert error.value.code == "STORAGE_UNAVAILABLE"
            assert time.monotonic() - began < 1.0
        finally:
            competing.rollback()
