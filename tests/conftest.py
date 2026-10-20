"""Isolated synthetic databases and independently hand-calculated expected results."""

import json
import os
from pathlib import Path

import pytest
from nl2sql.bootstrap.resources import build_resources
from nl2sql.evaluation.synthetic import initialize
from nl2sql.infrastructure.inference.model import MockModel
from nl2sql.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    initialize(tmp_path / "data", tmp_path / "catalog.json")
    return Settings.model_validate_json((tmp_path / "data/settings.json").read_text())


@pytest.fixture
def credentials(settings: Settings) -> dict[str, str]:
    return json.loads((settings.data_dir / "demo-credentials.json").read_text())


@pytest.fixture
def resources(settings: Settings):
    active = build_resources(settings, MockModel({}))
    yield active
    active.close()


@pytest.fixture(autouse=True)
def synthetic_environment(monkeypatch: pytest.MonkeyPatch):
    """Tests never inherit office credentials/providers; Redis tests require their own URL."""
    for name in tuple(os.environ):
        if (name.startswith("NL2SQL_") and name != "NL2SQL_TEST_REDIS_URL") or name in {
            "EWS_NL2SQL_SETTINGS_FILE",
            "EWS_NL2SQL_ENV_FILE",
        }:
            monkeypatch.delenv(name)
