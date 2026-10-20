"""Verify setup paths, repeat runs and failures without installing packages in tests."""

import os
import subprocess
from pathlib import Path

import pytest

import setup_env


@pytest.mark.parametrize("existing_settings", [None, "NL2SQL_MODEL_MODE=private_http\n"])
def test_setup_from_another_directory_preserves_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_settings: str | None
) -> None:
    root = tmp_path / "project with spaces"
    root.mkdir()
    template = "# MODEL\nNL2SQL_MODEL_MODE=disabled\n"
    (root / ".env.example").write_text(template, encoding="utf-8")
    monkeypatch.setattr(setup_env, "__file__", str(root / "setup_env.py"))
    monkeypatch.setattr(setup_env.sys, "version_info", (3, 13, 16))
    monkeypatch.chdir(tmp_path)
    created: list[Path] = []
    calls: list[list[str]] = []
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    class FakeEnvironment:
        def __init__(self, *, with_pip: bool) -> None:
            assert with_pip

        def create(self, directory: Path) -> None:
            created.append(directory)
            python.parent.mkdir(parents=True)
            python.touch()

    def run(command: list[str], *, check: bool) -> None:
        assert check
        calls.append(command)

    monkeypatch.setattr(setup_env.venv, "EnvBuilder", FakeEnvironment)
    monkeypatch.setattr(setup_env.subprocess, "run", run)
    if existing_settings is not None:
        (root / ".env").write_text(existing_settings, encoding="utf-8")
    setup_env.main()
    setup_env.main()
    assert created == [root / ".venv"]
    assert (root / ".env").read_text(encoding="utf-8") == (existing_settings or template)
    assert (
        calls
        == [
            [str(python), "-m", "pip", "install", "-r", str(root / "requirements-core.lock")],
            [str(python), "-m", "pip", "install", "--no-deps", "-e", str(root)],
        ]
        * 2
    )


def test_install_failure_does_not_report_success_or_create_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(setup_env, "__file__", str(tmp_path / "setup_env.py"))
    monkeypatch.setattr(setup_env.sys, "version_info", (3, 13, 16))
    python = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()

    def fail(command: list[str], *, check: bool) -> None:
        assert check
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(setup_env.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup_env.main()
    assert not (tmp_path / ".env").exists()
    assert "Setup complete" not in capsys.readouterr().out


def test_setup_rejects_unsupported_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_env, "__file__", str(tmp_path / "setup_env.py"))
    monkeypatch.setattr(setup_env.sys, "version_info", (3, 12, 0))
    with pytest.raises(SystemExit, match="Use Python 3.13"):
        setup_env.main()
    assert not (tmp_path / ".venv").exists()
