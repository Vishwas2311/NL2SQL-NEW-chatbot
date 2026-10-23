"""A publication waiter and nested chat cannot reset the inherited application deadline."""

import time

import pytest
from nl2sql.domain.models import Failure
from nl2sql.telemetry import stage_metrics

from tests.integration.test_metadata_lifecycle import MetadataKit


def test_reload_wait_uses_request_deadline(settings, tmp_path):
    kit = MetadataKit(settings, tmp_path / "metadata")
    try:
        kit.publish()
        kit.start()
        kit.manager._reload_lock.acquire()
        started = time.monotonic()
        try:
            with stage_metrics({}, time.time() + 0.02), pytest.raises(Failure) as error:
                kit.manager.reload()
            assert error.value.code == "RUNTIME_BUSY"
            assert time.monotonic() - started < 1
        finally:
            kit.manager._reload_lock.release()
    finally:
        kit.close()


def test_direct_chat_keeps_expired_outer_deadline(resources):
    user = resources.auth.principals["analyst"]
    with stage_metrics({}, time.time() - 1), pytest.raises(Failure) as error:
        resources.service.chat("Show total loan exposure by region", None, user, None, {})
    assert error.value.code == "REQUEST_TIMEOUT" and resources.database.execute_count == 0


def test_runtime_factory_captures_oracle_configuration_once(settings, resources, monkeypatch):
    from nl2sql.bootstrap.runtime import RuntimeFactory

    captured = []

    def executor(_validator, configuration, **_kwargs):
        captured.append(configuration.pool_max)
        return object()

    monkeypatch.setattr("nl2sql.infrastructure.databases.oracle_factory.oracle_executor", executor)
    monkeypatch.setenv("NL2SQL_QUERY_POOL_MAX", "2")
    factory = RuntimeFactory(
        settings.model_copy(update={"query_backend": "oracle"}),
        resources.sessions,
        resources.model,
        inference_admission=resources.service.model.admission,
    )
    monkeypatch.setenv("NL2SQL_QUERY_POOL_MAX", "7")
    factory.executor_factory(resources.database.validator)
    assert captured == [2]
