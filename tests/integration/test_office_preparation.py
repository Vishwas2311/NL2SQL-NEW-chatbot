"""The office preparation workflow runs with real local graph/vector resources and synthetic data."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from nl2sql.bootstrap.managed import build_managed_resources
from nl2sql.cli.metadata import MetadataOptions, run_metadata
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.metadata.store import MetadataRepository
from nl2sql.infrastructure.retrieval.vector_index import LadybugVectorIndex
from nl2sql.settings import load_settings


def test_prepare_generates_resources_after_signed_review_and_monitor_stages_updates(
    tmp_path, monkeypatch
):
    root = tmp_path / "private"
    env = tmp_path / "synthetic.env"
    env.write_text(
        "NL2SQL_DATA_CLASSIFICATION=synthetic\nNL2SQL_EMBEDDING_MODE=fake\n"
        "NL2SQL_EMBEDDING_MODEL=synthetic\nNL2SQL_EMBEDDING_VERSION=1\n"
        "NL2SQL_EMBEDDING_DIMENSION=2\n",
        encoding="utf-8",
    )

    def run(action, **options):
        return run_metadata(MetadataOptions(action=action, root=root, env_file=env, **options))

    pending = run("prepare", source="synthetic")
    assert pending["state"] == "pending_approval" and pending["next_step"] == "review_metadata"
    with closing(MetadataRepository(root)) as repository:
        assert repository.control().active is None
    trust = run("demo-trust")
    for key, value in json.loads(Path(trust["private_credentials"]).read_text()).items():
        monkeypatch.setenv(key, value)
    signatures = run("sign-demo", candidate_id=pending["candidate_id"])
    ready = run("prepare", approval_file=Path(signatures["private_output"]))
    assert ready["state"] == "ready" and ready["next_step"] == "serve"
    assert list((root / "data/graphs").glob("*.lbdb"))
    assert run("prepare")["state"] == "ready"
    settings = load_settings(root / "data/settings.json", env).model_copy(
        update={"metadata_root": root}
    )
    resources = build_managed_resources(settings)
    try:
        with resources.manager.pin() as bundle:
            assert all(
                isinstance(index, LadybugVectorIndex)
                for index in bundle.retriever._native_indexes.values()
            )
        answer = resources.service.chat(
            "Show total loan exposure by region",
            None,
            resources.auth.principals["analyst"],
            None,
            {},
        )
        assert answer.rows[0]["loan_exposure"] == "175000.50"
        run("schedule", enable=True, interval=5)
        with closing(sqlite3.connect(root / "data/banking.db")) as connection, connection:
            connection.execute("ALTER TABLE loans ADD COLUMN unapproved_note TEXT")
        detected = run("monitor", once=True)
        assert detected["ran"] and detected["outcome"]["change_count"] > 0
        with closing(MetadataRepository(root)) as repository:
            assert repository.control().active == ready["candidate_id"]
    finally:
        resources.close()


def test_prepare_dry_run_does_not_create_target_and_invalid_signature_cannot_publish(tmp_path):
    root = tmp_path / "private"
    preview = run_metadata(
        MetadataOptions(action="prepare", source="synthetic", root=root, dry_run=True)
    )
    assert preview["state"] == "pending_approval" and not root.exists()
    pending = run_metadata(MetadataOptions(action="prepare", source="synthetic", root=root))
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"approvals":["not-signed"]}', encoding="utf-8")
    with pytest.raises(Failure):
        run_metadata(MetadataOptions(action="prepare", root=root, approval_file=invalid))
    with closing(MetadataRepository(root)) as repository:
        assert (
            repository.control().active is None
            and repository.get(pending["candidate_id"]).state == "pending_approval"
        )
