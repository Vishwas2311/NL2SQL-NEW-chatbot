"""Portable supervisor cleanup and complete, explicit environment propagation."""

import os

import pytest
from nl2sql.cli import office
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.databases.oracle_factory import OracleExecutionSettings
from nl2sql.infrastructure.metadata.config import authority_from_environment
from nl2sql.infrastructure.metadata.oracle_discovery import OracleDiscoverySettings
from nl2sql.settings import load_settings, selected_environment


def test_selected_env_reaches_oracle_and_trust_without_leaking_process_changes(
    tmp_path, monkeypatch
):
    path = tmp_path / "office.env"
    path.write_text(
        "NL2SQL_QUERY_DSN=synthetic-query\nNL2SQL_DISCOVERY_DSN=synthetic-discovery\n"
        "NL2SQL_MODEL_CONTEXT_TOKENS=4096\nNL2SQL_METADATA_ADMIN_KEY=" + "a" * 48 + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NL2SQL_QUERY_DSN", "process-wins")
    settings = load_settings(env_file=path)
    assert settings.model_context_tokens == 4096
    assert "NL2SQL_DISCOVERY_DSN" not in os.environ
    with selected_environment(path):
        assert OracleExecutionSettings().dsn.get_secret_value() == "process-wins"
        assert OracleDiscoverySettings().dsn.get_secret_value() == "synthetic-discovery"
        assert authority_from_environment() is not None
    assert (
        "NL2SQL_DISCOVERY_DSN" not in os.environ and "NL2SQL_METADATA_ADMIN_KEY" not in os.environ
    )


def test_visible_blank_env_fields_keep_json_values(tmp_path):
    path = tmp_path / "office.env"
    path.write_text("NL2SQL_EMBEDDING_DIMENSION=\nNL2SQL_REDIS_URL=\n", encoding="utf-8")
    settings = tmp_path / "office.json"
    settings.write_text('{"embedding_dimension":2,"redis_url":"redis://127.0.0.1:6380"}')
    loaded = load_settings(settings, env_file=path)
    assert loaded.embedding_dimension == 2
    assert loaded.redis_url is not None
    assert loaded.redis_url.get_secret_value() == "redis://127.0.0.1:6380"


@pytest.mark.parametrize("failure", ["monitor_exit", "second_start", "interrupt"])
def test_supervisor_stops_children_on_all_exit_paths(monkeypatch, failure):
    children = []

    class Child:
        def __init__(self, command, **_options):
            if failure == "second_start" and children:
                raise OSError("synthetic launch failure")
            self.command = command
            self.stopped = False
            children.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            assert self.poll() is not None

        def poll(self):
            return (
                1
                if (failure == "monitor_exit" and self.command == ["monitor"]) or self.stopped
                else None
            )

        def terminate(self):
            self.stopped = True

        def wait(self, timeout):
            assert timeout == 5 and self.stopped

    monkeypatch.setattr(office.subprocess, "Popen", Child)

    def interrupt(_delay):
        raise KeyboardInterrupt

    monkeypatch.setattr(office.time, "sleep", interrupt)
    if failure == "interrupt":
        office.supervise(["api"], ["monitor"])
    else:
        with pytest.raises((Failure, OSError)):
            office.supervise(["api"], ["monitor"])
    assert children and all(child.stopped or child.poll() is not None for child in children)


def test_office_does_not_launch_api_with_uncertified_metadata(settings, tmp_path, monkeypatch):
    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "metadata_root": tmp_path,
            "embedding_mode": "private_http",
        }
    )
    monkeypatch.setattr(office, "load_settings", lambda *_: configuration)
    calls = []

    def run(options):
        calls.append(options.action)
        return {"state": "pending_verification", "issues": ["business_semantics_required"]}

    monkeypatch.setattr(office, "run_metadata", run)
    monkeypatch.setattr(office, "supervise", lambda *_: pytest.fail("Uncertified API launch"))
    with pytest.raises(Failure) as error:
        office.run_office(tmp_path / "office.json", None, None, None, 8000, 900)
    assert error.value.code == "METADATA_REVIEW_REQUIRED" and calls == ["prepare"]


def test_laptop_supervisor_rejects_multiworker_tree_before_preparing(
    settings, tmp_path, monkeypatch
):
    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "metadata_root": tmp_path,
            "embedding_mode": "private_http",
            "api_workers": 2,
        }
    )
    monkeypatch.setattr(office, "load_settings", lambda *_: configuration)
    monkeypatch.setattr(office, "run_metadata", lambda *_: pytest.fail("Unexpected preparation"))
    with pytest.raises(Failure, match="one API worker"):
        office.run_office(tmp_path / "office.json", None, None, None, 8000, 900)


@pytest.mark.parametrize("embedding_mode", ["disabled", "local"])
def test_office_prepares_and_supervises_selected_encoder(
    settings, tmp_path, monkeypatch, embedding_mode
):
    configuration = settings.model_copy(
        update={
            "query_backend": "oracle",
            "metadata_root": tmp_path,
            "embedding_mode": embedding_mode,
        }
    )
    monkeypatch.setattr(office, "load_settings", lambda *_: configuration)
    calls = []
    monkeypatch.setattr(
        office, "run_metadata", lambda options: calls.append(options.action) or {"state": "ready"}
    )
    children = []
    monkeypatch.setattr(office, "supervise", lambda *commands: children.extend(commands))
    office.run_office(tmp_path / "office.json", None, None, None, 8000, 900)
    assert calls == ["prepare", "schedule"]
    assert len(children) == 2 and "serve" in children[0] and "monitor" in children[1]
