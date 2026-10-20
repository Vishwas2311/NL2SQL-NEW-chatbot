"""Exporter regression tests run the same standalone entry point as the user."""

import shutil
import subprocess
import sys
from pathlib import Path


def test_export_includes_project_and_excludes_private_runtime_data(tmp_path: Path) -> None:
    script = tmp_path / "export_project_to_txt.py"
    shutil.copyfile(Path(__file__).resolve().parents[2] / script.name, script)
    fixtures = {
        "backend/app.py": "print('fictional application')\n",
        "docs/design.md": "Synthetic design\n",
        "frontend-reference/index.html": "<h1>Original UI reference</h1>\n",
        ".gitignore": ".local/\n",
        ".local/demo-credentials.json": '"PRIVATE_RUNTIME_TOKEN"',
        ".env": "PRIVATE_ENV_TOKEN=secret",
        ".venv/installed.py": "PRIVATE_DEPENDENCY_CONTENT",
        ".git/config": "PRIVATE_GIT_SETTINGS",
        "settings.json": '"PRIVATE_SETTINGS"',
        "secrets.json": '"PRIVATE_SECRET"',
        "office-cache/.metadata-private": "",
        "office-cache/review.txt": "PRIVATE_MARKED_INVENTORY",
        "copy.json": '{"classification":"restricted","objects":["PRIVATE_COLUMN"]}',
        "review.txt": '{"classification":"restricted","objects":["PRIVATE_SCHEMA_TEXT"]}',
        "approval-copy.json": '{"approvals":["PRIVATE_REVIEW_TOKEN"]}',
        "nested-copy.json": '{"spec":{"inventory":{"source_kind":"oracle","objects":["PRIVATE_SCHEMA"]}}}',
    }
    for filename, content in fixtures.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "binary.py").write_bytes(b"\xff\xfe\x00")
    elsewhere = tmp_path / "another_directory"
    elsewhere.mkdir()
    for _ in range(2):
        subprocess.run(
            [sys.executable, str(script)], cwd=elsewhere, check=True, capture_output=True
        )
        exported = (tmp_path / "full_project_export.txt").read_text(encoding="utf-8")
        assert "FILE: backend/app.py" in exported
        assert "FILE: docs/design.md" in exported
        assert "FILE: frontend-reference/index.html" in exported
        assert "FILE: .gitignore" in exported
        assert "PRIVATE_" not in exported
        assert exported.count("NL2SQL PROJECT TEXT EXPORT") == 2  # Header and exporter source.
        assert "FILE: full_project_export.txt" not in exported
        assert "Skipped binary/non-UTF-8 files:" in exported
        assert "\nbinary.py\n" in exported
    assert (tmp_path / "backend/app.py").read_text() == fixtures["backend/app.py"]


def test_export_preserves_unrelated_existing_destination(tmp_path: Path) -> None:
    script = tmp_path / "export_project_to_txt.py"
    shutil.copyfile(Path(__file__).resolve().parents[2] / script.name, script)
    output = tmp_path / "full_project_export.txt"
    output.write_text("Existing user notes", encoding="utf-8")
    result = subprocess.run([sys.executable, str(script)], capture_output=True)
    assert result.returncode != 0
    assert output.read_text() == "Existing user notes"
    assert not list(tmp_path.glob(".project-export-*.tmp"))
