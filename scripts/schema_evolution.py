"""Measure the real local synthetic lifecycle; never claims Oracle/model qualification."""

import json
import os
import sqlite3
import statistics
import tempfile
import time
import tracemalloc
from contextlib import closing
from pathlib import Path

from nl2sql.config import Settings
from nl2sql.managed_resources import build_managed_resources
from nl2sql.metadata_cli import MetadataOptions, run_metadata
from nl2sql.metadata_store import MetadataControl
from pydantic import TypeAdapter


def exercise(root: Path) -> dict[str, object]:
    """Use the same CLI workflows, signed artifacts and managed service as an operator."""
    started = time.perf_counter()
    candidate = run_metadata(MetadataOptions(action="bootstrap", root=root, source="synthetic"))
    version = candidate["candidate_id"]
    assert isinstance(version, str)
    run_metadata(MetadataOptions(action="demo-trust", root=root))
    values = TypeAdapter(dict[str, str]).validate_json((root / "demo-credentials.json").read_text())
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        signed = run_metadata(MetadataOptions(action="sign-demo", root=root, candidate_id=version))
        path = signed["private_output"]
        assert isinstance(path, str)
        run_metadata(
            MetadataOptions(
                action="approve", root=root, candidate_id=version, approval_file=Path(path)
            )
        )
        run_metadata(MetadataOptions(action="publish", root=root, candidate_id=version))
        settings = Settings.model_validate_json(
            (root / "data/settings.json").read_text()
        ).model_copy(update={"metadata_root": root})
        bootstrap_ms = (time.perf_counter() - started) * 1000
        with closing(build_managed_resources(settings)) as resources:
            principal = settings.principals[0]
            timings: list[float] = []
            correct = 0
            for _ in range(30):
                began = time.perf_counter()
                answer = resources.service.chat(
                    "Show total loan exposure by region", None, principal, None, {}
                )
                timings.append((time.perf_counter() - began) * 1000)
                correct += answer.rows == (
                    {"region": "Demo North", "loan_exposure": "175000.50"},
                    {"region": "Demo South", "loan_exposure": "75000.00"},
                )
                assert answer.provenance is not None and answer.provenance.bundle_version == version
            unchanged = run_metadata(MetadataOptions(action="sync", root=root))
            with (
                closing(sqlite3.connect(settings.data_dir / "banking.db")) as connection,
                connection,
            ):
                connection.execute(
                    "UPDATE loans SET amount_minor=amount_minor+100 WHERE loan_id='L1'"
                )
            rows_only = run_metadata(MetadataOptions(action="sync", root=root))
            updated = resources.service.chat(
                "Show total loan exposure by region", None, principal, None, {}
            )
            assert updated.rows[0]["loan_exposure"] == "175001.50"
            with (
                closing(sqlite3.connect(settings.data_dir / "banking.db")) as connection,
                connection,
            ):
                connection.execute("ALTER TABLE loans ADD COLUMN unreviewed_note TEXT")
            added = run_metadata(MetadataOptions(action="sync", root=root))
            with resources.manager.pin() as bundle:
                assert not any(
                    column.name == "unreviewed_note"
                    for table in bundle.catalog.tables
                    for column in table.columns
                )
            status = run_metadata(MetadataOptions(action="status", root=root))
            assert correct == 30 and unchanged["no_change"] and rows_only["no_change"]
            return {
                "source": "fictional synthetic SQLite; no corporate connection",
                "bootstrap_approve_publish_ms": bootstrap_ms,
                "initial_bundle_build_ms": candidate["build_ms"],
                "questions": 30,
                "correct_results": correct,
                "query_p50_ms": statistics.median(timings),
                "query_p95_ms": sorted(timings)[28],
                "unchanged_refresh_ms": unchanged["build_ms"],
                "row_change_triggers_rebuild": not rows_only["no_change"],
                "row_change_result": updated.rows,
                "new_column_state": added["state"],
                "new_column_gains_permission": False,
                "active_unchanged": MetadataControl.model_validate(status["control"]).active
                == version,
                "model_calls": 0,
                "inference_tokens": None,
                "actual_oracle": "not run",
                "actual_gemma": "not run",
                "actual_faiss": "not installed or run",
            }
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> None:
    """Export aggregate nonconfidential measurements only."""
    tracemalloc.start()
    with tempfile.TemporaryDirectory(prefix="nl2sql-schema-evolution-") as directory:
        report = exercise(Path(directory))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report["peak_python_traced_bytes"] = peak
    Path("reports").mkdir(exist_ok=True)
    Path("reports/schema-evolution.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
