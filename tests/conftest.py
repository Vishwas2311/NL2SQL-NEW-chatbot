"""Isolated synthetic databases and independently hand-calculated expected results."""

import json
from pathlib import Path

import pytest
from nl2sql.api import build_resources
from nl2sql.config import Settings
from nl2sql.model import MockModel
from nl2sql.synthetic import initialize


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
