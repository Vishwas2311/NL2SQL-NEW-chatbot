"""Inference uses separate atomic counters and shares them across catalog planners."""

import time

import pytest
from nl2sql.application.inference import InferencePlanner
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.rate_limit import build_inference_admission


def test_expired_request_cannot_enter_provider(settings):
    class Provider:
        def plan(self, *_args):
            pytest.fail("Expired inference must not enter the provider")

    limiter = build_inference_admission(settings)
    try:
        with pytest.raises(Failure) as error:
            InferencePlanner(Provider(), limiter).plan(
                "q", "c", time.time() - 1, settings.principals[0]
            )
        assert error.value.code == "REQUEST_TIMEOUT"
        assert limiter._active == {}
    finally:
        limiter.close()


def test_inference_namespace_limits_and_failed_startup_cleanup(settings, monkeypatch):
    captured = []

    class Limiter:
        def __init__(self):
            self.closed = False

        def ready(self):
            raise Failure("RATE_LIMIT_UNAVAILABLE", "Synthetic unavailable.", "unavailable")

        def close(self):
            self.closed = True

    limiter = Limiter()

    def build(configuration):
        captured.append(configuration)
        return limiter

    monkeypatch.setattr("nl2sql.infrastructure.rate_limit.build_rate_limiter", build)
    with pytest.raises(Failure):
        build_inference_admission(settings)
    assert limiter.closed
    assert captured[0].redis_key_prefix == settings.redis_key_prefix + ":inference"
    assert captured[0].max_concurrent_chats == settings.max_concurrent_inferences
    assert captured[0].rate_limit_backend == settings.rate_limit_backend


def test_catalog_planners_share_one_inference_limit(settings):
    limiter = build_inference_admission(settings)
    user, other = settings.principals

    class Provider:
        def plan(self, *_args):
            pytest.fail("Saturated capacity must not enter a second catalog's provider")

    old, new = InferencePlanner(Provider(), limiter), InferencePlanner(Provider(), limiter)
    try:
        with old.admission.chat(user):
            with pytest.raises(Failure) as error:
                new.plan("q", "c", time.time() + 5, other)
        assert error.value.code == "INFERENCE_CAPACITY"
    finally:
        limiter.close()
