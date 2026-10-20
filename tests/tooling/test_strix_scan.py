"""Optional security tooling must never scan host secrets or report a truncated run as clean."""

import json
from subprocess import CompletedProcess

import pytest

from scripts import strix_scan
from scripts.strix_scan import prepare_source, scan_complete


def test_snapshot_preserves_source_and_excludes_private_runtime_files(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    files = {
        "backend/app.py": b"print('synthetic')\r\n",
        "docs/ARCHITECTURE.md": b"Synthetic-only backend\n",
        ".env": b"LLM_API_KEY=PRIVATE_SENTINEL",
        "full_project_export.txt": b"PRIVATE_SENTINEL",
        ".local/settings.json": b'{"token":"PRIVATE_SENTINEL"}',
        "private/.metadata-private": b"",
        "private/inventory.json": b'{"source_kind":"oracle","objects":[]}',
        "copied-inventory.json": b'{"source_kind":"oracle","objects":[]}',
        "copied-approval.json": b'{"approvals":["PRIVATE_SENTINEL"]}',
        "banking.db": b"PRIVATE_SENTINEL",
    }
    for name, payload in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    destination = root / ".local/strix/run/source"
    assert prepare_source(root, destination) == 2
    assert (destination / "backend/app.py").read_bytes() == files["backend/app.py"]
    assert {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    } == {
        "backend/app.py",
        "docs/ARCHITECTURE.md",
    }
    with pytest.raises(FileExistsError):
        prepare_source(root, destination)


@pytest.mark.parametrize("status", ["stopped", "running", "completed", "broken_json", "missing"])
def test_scan_requires_a_single_completed_run_record(tmp_path, status):
    path = tmp_path / "strix_runs/run/run.json"
    if status != "missing":
        path.parent.mkdir(parents=True)
        path.write_text(
            "{" if status == "broken_json" else json.dumps({"status": status}), encoding="utf-8"
        )
    assert scan_complete(tmp_path) == (status == "completed")
    if status == "completed":
        second = tmp_path / "strix_runs/another/run.json"
        second.parent.mkdir()
        second.write_text('{"status":"completed"}', encoding="utf-8")
        assert not scan_complete(tmp_path)


@pytest.mark.parametrize(
    "exit_code,completed,expected", [(0, True, 0), (0, False, 1), (2, True, 2)]
)
def test_hook_scans_only_disposable_source_and_propagates_findings(
    tmp_path, monkeypatch, exit_code, completed, expected
):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("# synthetic\n", encoding="utf-8")
    tool = tmp_path / "strix.exe"
    tool.touch()
    monkeypatch.setattr(strix_scan, "ROOT", root)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["strix_scan", "--strix", tool.name])
    calls = []

    def run(command, *, cwd, env, check):
        calls.append(command)
        assert command[0] == str(tool)
        assert env["STRIX_TELEMETRY"] == "0" and check is False
        assert command[command.index("--scope-mode") + 1] == "full"
        assert float(command[command.index("--max-budget") + 1]) == 10
        assert command[command.index("-t") + 1] == str(cwd / "source")
        assert cwd.is_relative_to(root / ".local/strix")
        assert str(root) not in command
        if completed:
            path = cwd / "strix_runs/test/run.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"status":"completed"}', encoding="utf-8")
        return CompletedProcess(command, exit_code)

    monkeypatch.setattr(strix_scan.subprocess, "run", run)
    assert strix_scan.main() == expected
    assert len(calls) == 1 and (root / "app.py").read_text(encoding="utf-8") == "# synthetic\n"
