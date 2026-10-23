"""Quality gates accept only an explicitly selected isolated Redis test environment."""

from pathlib import Path

import pytest

from scripts import check, hook


@pytest.mark.parametrize(
    "value",
    [
        "NL2SQL_TEST_REDIS_URL=redis://192.0.2.1:6379/0\n",
        "NL2SQL_REDIS_URL=redis://127.0.0.1:6379/0\n",
    ],
)
def test_check_rejects_nonlocal_or_application_redis_env(tmp_path, monkeypatch, value):
    path = tmp_path / "test.env"
    path.write_text(value)
    monkeypatch.setattr("sys.argv", ["check", "--redis-env", str(path)])
    with pytest.raises(SystemExit) as error:
        check.main()
    assert error.value.code == 2


def test_check_runs_every_gate_with_explicit_test_redis(tmp_path, monkeypatch):
    monkeypatch.setenv("NL2SQL_TEST_REDIS_URL", "synthetic-previous-value")
    path = tmp_path / "test.env"
    path.write_text("NL2SQL_TEST_REDIS_URL=redis://127.0.0.1:6380/0\n")
    monkeypatch.setattr("sys.argv", ["check", "--redis-env", str(path)])
    calls = []
    monkeypatch.setattr(check.subprocess, "run", lambda command, **_: calls.append(command))
    check.main()
    assert check.os.environ["NL2SQL_TEST_REDIS_URL"] == "redis://127.0.0.1:6380/0"
    assert [command[2] for command in calls] == [
        "ruff",
        "ruff",
        "pylint",
        "pyright",
        "pytest",
        "pre_commit",
    ]


def test_hook_keeps_venv_interpreter_path_when_it_is_a_symlink(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executable = Path(".venv") / ("Scripts/python.exe" if hook.os.name == "nt" else "bin/python")
    expected = str(executable.absolute())
    # Simulate POSIX venv symlinks on every test platform.
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        if path == executable:
            return tmp_path / "system-python"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(hook.sys, "argv", ["hook", "ruff", "check", "example.py"])
    calls = []
    monkeypatch.setattr(hook.subprocess, "run", lambda command, **_: calls.append(command))
    hook.main()
    assert calls == [[expected, "-m", "ruff", "check", "example.py"]]
