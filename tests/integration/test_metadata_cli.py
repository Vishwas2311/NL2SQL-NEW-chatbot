"""Real CLI subprocesses and managed API use the same private synthetic source."""

import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from nl2sql.bootstrap.factory import create_app
from nl2sql.cli.metadata import MetadataOptions, run_metadata
from nl2sql.infrastructure.metadata.config import load_profile
from nl2sql.infrastructure.metadata.discovery import SyntheticDiscovery
from nl2sql.settings import Settings


def command(root, *arguments, environment=None, success=True):
    environment = dict(os.environ if environment is None else environment)
    result = subprocess.run(
        [sys.executable, "-m", "nl2sql", "metadata", *arguments, "--root", str(root)],
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if success:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    return result


@pytest.mark.parametrize("inline", [False, True])
def test_cli_bootstrap_publish_serve_refresh_schedule_and_recover(
    tmp_path, monkeypatch, capsys, inline
):
    if inline:
        from nl2sql.cli.main import main

        def cli(root, *arguments, environment=None):
            with monkeypatch.context() as context:
                if environment:
                    for key, value in environment.items():
                        context.setenv(key, value)
                context.setattr(
                    sys, "argv", ["nl2sql", "metadata", *arguments, "--root", str(root)]
                )
                main()
                return json.loads(capsys.readouterr().out)
    else:
        cli = command
    root = tmp_path / "private-store"
    preview = cli(root, "bootstrap", "--source", "synthetic", "--dry-run")
    assert preview["state"] == "pending_approval" and not root.exists()
    staged = cli(root, "bootstrap", "--source", "synthetic")
    version = staged["candidate_id"]
    assert cli(root, "status")["control"]["active"] is None
    trust = cli(root, "demo-trust")
    values = json.loads(open(trust["private_credentials"], encoding="utf-8").read())
    environment = dict(os.environ, **values)
    cli(root, "inspect", "--candidate-id", version, environment=environment)
    signatures = cli(root, "sign-demo", "--candidate-id", version, environment=environment)
    cli(
        root,
        "approve",
        "--candidate-id",
        version,
        "--approval-file",
        signatures["private_output"],
        environment=environment,
    )
    cli(root, "publish", "--candidate-id", version, environment=environment)
    assert cli(root, "sync", "--dry-run", environment=environment)["no_change"]
    assert cli(root, "monitor", "--once", environment=environment) == {
        "ran": False,
        "attempts": 0,
        "outcome": None,
        "error_code": None,
    }
    cli(root, "schedule", "--enable", "--interval", "5", "--dry-run", environment=environment)
    tick = cli(root, "monitor", "--once", environment=environment)
    assert tick["ran"] and tick["outcome"]["no_change"]
    cli(root, "schedule", "--disable", environment=environment)
    cli(root, "rollback", "--version", version, environment=environment)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    settings = Settings.model_validate_json((root / "data/settings.json").read_text()).model_copy(
        update={"metadata_root": root}
    )
    credentials = json.loads((settings.data_dir / "demo-credentials.json").read_text())
    headers = {"Authorization": "Bearer " + credentials["analyst"]}
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/health/ready").status_code == 200
        response = client.post(
            "/ews-chatbot/chat",
            headers=headers,
            json={"message": "Show total loan exposure by region"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["loan_exposure"] == "175000.50"
        session = response.json()["session_id"]
        other = {"Authorization": "Bearer " + credentials["north_analyst"]}
        assert client.get("/ews-chatbot/load_session/" + session, headers=other).status_code == 404
        assert (
            client.post(
                "/ews-chatbot/chat",
                headers=headers,
                json={"message": "Show total loan exposure", "user_id": "north_analyst"},
            ).status_code
            == 403
        )
        assert (
            client.get("/ews-chatbot/load_session/" + session, headers=headers).status_code == 200
        )


def test_oracle_cli_guard_no_profile_no_network_no_secret_output(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith("NL2SQL_DISCOVERY_"):
            monkeypatch.delenv(name)
    root = tmp_path / "office"
    result = command(root, "bootstrap", "--source", "oracle", "--dry-run", success=False)
    assert "ORACLE_NOT_APPROVED" in result.stderr
    assert not root.exists()


def test_physical_only_source_can_attach_settings_later_and_status_needs_no_settings(
    settings, tmp_path
):
    root = tmp_path / "physical-first"
    file = tmp_path / "inventory.json"
    file.write_text(
        SyntheticDiscovery(settings.data_dir / "banking.db").discover().model_dump_json()
    )
    first = run_metadata(MetadataOptions(action="bootstrap", root=root, source="file", file=file))
    assert first["state"] == "pending_verification"
    assert load_profile(root).settings_path is None
    settings_path = settings.data_dir / "settings.json"
    run_metadata(MetadataOptions(action="sync", root=root, settings=settings_path, dry_run=True))
    assert load_profile(root).settings_path is None
    run_metadata(MetadataOptions(action="sync", root=root, settings=settings_path))
    assert load_profile(root).settings_path == settings_path.resolve()
    settings_path.unlink()
    assert run_metadata(MetadataOptions(action="status", root=root))["control"] is not None


@pytest.mark.parametrize("action", ["approve", "publish", "rollback"])
def test_missing_cli_identifiers_are_rejected(tmp_path, action):
    command(tmp_path / "none", action, success=False)
