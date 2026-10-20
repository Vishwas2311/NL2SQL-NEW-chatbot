"""Quality gates accept only an explicitly selected isolated Redis test environment."""

import pytest

from scripts import check


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
