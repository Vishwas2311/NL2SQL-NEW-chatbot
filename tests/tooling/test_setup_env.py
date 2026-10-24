"""Verify setup paths, repeat runs and failures without installing packages in tests."""

import os
import subprocess
from pathlib import Path

import pytest

import setup_env


@pytest.mark.parametrize("existing_settings", [None, "NL2SQL_MODEL_MODE=private_http\n"])
@pytest.mark.parametrize("office", [False, True])
def test_setup_from_another_directory_preserves_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_settings: str | None, office: bool
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
    setup_env.main(office=office)
    setup_env.main(office=office)
    assert created == [root / ".venv"]
    assert (root / ".env").read_text(encoding="utf-8") == (existing_settings or template)
    installs = [
        [
            str(python),
            "-m",
            "pip",
            "install",
            *[
                item
                for name in (
                    ("requirements-oracle.lock", "requirements-redis.lock")
                    if office
                    else ("requirements-core.lock",)
                )
                for item in ("-r", str(root / name))
            ],
        ],
        [str(python), "-m", "pip", "install", "--no-deps", "-e", str(root)],
    ]
    diagnostic = str(root / "backend/nl2sql/bootstrap/sqlite_runtime.py")
    assert calls == (
        (
            [[setup_env.sys.executable, "-I", diagnostic], [str(python), "-I", diagnostic]]
            if office
            else []
        )
        + installs
        + ([[str(python), "-I", diagnostic]] if office else [])
        + installs
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


@pytest.mark.parametrize("existing_venv", [False, True])
def test_office_runtime_failure_precedes_every_mutation(tmp_path, monkeypatch, existing_venv):
    monkeypatch.setattr(setup_env, "__file__", str(tmp_path / "setup_env.py"))
    monkeypatch.setattr(setup_env.sys, "version_info", (3, 13, 17))
    python = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if existing_venv:
        python.parent.mkdir(parents=True)
        python.write_bytes(b"existing runtime")
    settings = tmp_path / ".env"
    settings.write_bytes(b"preserve settings")
    data = tmp_path / "data.db"
    data.write_bytes(b"preserve data")
    calls = []

    def reject(command, *, check):
        assert check and "pip" not in command and "-e" not in command
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Runtime must pass before creating a virtual environment")

    monkeypatch.setattr(setup_env.subprocess, "run", reject)
    monkeypatch.setattr(setup_env.venv, "EnvBuilder", unexpected)
    with pytest.raises(subprocess.CalledProcessError):
        setup_env.main(office=True)
    assert len(calls) == 1
    assert calls[0][0] == (str(python) if existing_venv else setup_env.sys.executable)
    assert settings.read_bytes() == b"preserve settings"
    assert data.read_bytes() == b"preserve data"
    assert python.read_bytes() == b"existing runtime" if existing_venv else not python.exists()
