"""Spawned workers load the same explicit settings through an importable factory."""

import pytest
from nl2sql.bootstrap import factory
from nl2sql.cli import main as cli


def test_cli_launches_shared_redis_factory(settings, monkeypatch):
    monkeypatch.setenv("NL2SQL_API_WORKERS", "1")
    monkeypatch.setenv("NL2SQL_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("NL2SQL_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("NL2SQL_HTTP_CONCURRENCY_LIMIT", "20")
    monkeypatch.setenv("EWS_NL2SQL_SETTINGS_FILE", "previous-synthetic-path")
    monkeypatch.setenv("EWS_NL2SQL_ENV_FILE", "previous-synthetic-path")
    monkeypatch.setattr(
        "sys.argv",
        [
            "nl2sql",
            "serve",
            "--settings",
            str(settings.data_dir / "settings.json"),
            "--workers",
            "2",
        ],
    )
    calls = []
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    cli.main()
    args, kwargs = calls[0]
    assert args == ("nl2sql.bootstrap.factory:create_configured_app",)
    assert kwargs == {
        "factory": True,
        "workers": 2,
        "limit_concurrency": 20,
        "host": "127.0.0.1",
        "port": 8000,
    }
    assert cli.os.environ["EWS_NL2SQL_SETTINGS_FILE"] == str(
        (settings.data_dir / "settings.json").resolve()
    )
    assert "EWS_NL2SQL_ENV_FILE" not in cli.os.environ


def test_cli_rejects_multi_worker_memory_mode(settings, monkeypatch, capsys):
    monkeypatch.setenv("NL2SQL_API_WORKERS", "1")
    monkeypatch.setenv("NL2SQL_RATE_LIMIT_BACKEND", "memory")
    monkeypatch.setattr(
        "sys.argv",
        [
            "nl2sql",
            "serve",
            "--settings",
            str(settings.data_dir / "settings.json"),
            "--workers",
            "2",
        ],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "Configuration is invalid" in capsys.readouterr().err


def test_worker_factory_preserves_configuration_precedence(settings, tmp_path, monkeypatch):
    env_file = tmp_path / "selected.env"
    env_file.write_text("NL2SQL_MAX_ROWS=9\n", encoding="utf-8")
    monkeypatch.setenv("EWS_NL2SQL_SETTINGS_FILE", str(settings.data_dir / "settings.json"))
    monkeypatch.setenv("EWS_NL2SQL_ENV_FILE", str(env_file))
    monkeypatch.setenv("NL2SQL_MAX_ROWS", "7")
    result = object()
    observed = []

    def capture(configuration):
        observed.append(configuration)
        return result

    monkeypatch.setattr(factory, "create_app", capture)
    assert factory.create_configured_app() is result
    assert observed[0].max_rows == 7


def test_worker_error_omits_configuration_values(tmp_path, monkeypatch):
    path = tmp_path / "invalid.json"
    path.write_text('{"unknown":"synthetic-private-sentinel"}', encoding="utf-8")
    monkeypatch.setenv("EWS_NL2SQL_SETTINGS_FILE", str(path))
    monkeypatch.delenv("EWS_NL2SQL_ENV_FILE", raising=False)
    with pytest.raises(ValueError) as error:
        factory.create_configured_app()
    assert "sentinel" not in str(error.value)


@pytest.mark.parametrize("available", [False, True])
def test_check_redis_checks_permissions_closes_and_sanitizes(
    settings, monkeypatch, capsys, available
):
    from nl2sql.domain.models import Failure

    closed = []

    class Admission:
        def ready(self):
            if not available:
                raise Failure("RATE_LIMIT_UNAVAILABLE", "synthetic credential sentinel", 503)

        def close(self):
            closed.append(True)

    monkeypatch.setenv("NL2SQL_RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("NL2SQL_REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setattr(cli, "build_rate_limiter", lambda _: Admission())
    monkeypatch.setattr(
        "sys.argv",
        ["nl2sql", "check-redis", "--settings", str(settings.data_dir / "settings.json")],
    )
    if available:
        cli.main()
    else:
        with pytest.raises(SystemExit) as failure:
            cli.main()
        assert failure.value.code == 1
    captured = capsys.readouterr()
    assert "sentinel" not in captured.out + captured.err
    assert closed == [True]
