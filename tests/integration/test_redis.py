"""Actual Lua behavior and independent clients against an explicit local test Redis."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from nl2sql.api.compatibility import failure_status
from nl2sql.bootstrap.factory import create_app
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.inference.model import MockModel
from nl2sql.infrastructure.rate_limit import (
    RedisRateLimiter,
    build_inference_admission,
    principal_key,
)
from nl2sql.settings import Settings

from tests.unit.test_rate_limit import outcome


def test_real_inference_leases_are_shared_and_separate_from_chat(redis_configuration):
    configuration, client = redis_configuration
    first, second = (build_inference_admission(configuration) for _ in range(2))
    outer = RedisRateLimiter(configuration)
    user, other = configuration.principals
    prefix = configuration.redis_key_prefix
    try:
        with outer.chat(user), first.chat(user):
            assert client.zcard(f"{prefix}:chat:global") == 1
            assert client.zcard(f"{prefix}:inference:chat:global") == 1
            with outer.chat(other):
                with pytest.raises(Failure) as busy:
                    with second.chat(other):
                        pytest.fail("Independent workers must share inference capacity")
                assert busy.value.code == "CHAT_CAPACITY"
        with second.chat(other):
            assert client.zcard(f"{prefix}:inference:chat:global") == 1
        assert client.zcard(f"{prefix}:inference:chat:global") == 0
    finally:
        first.close()
        second.close()
        outer.close()


def test_real_lua_is_atomic_has_ttl_and_prunes_old_entries(redis_configuration):
    configuration, client = redis_configuration
    user = configuration.principals[0]
    key = f"{configuration.redis_key_prefix}:rate:{principal_key(user)}"
    seconds, microseconds = client.time()
    now = seconds * 1000 + microseconds // 1000
    client.zadd(key, {"expired-synthetic-request": now - 61_000})
    workers = [RedisRateLimiter(configuration) for _ in range(2)]
    try:
        for worker in workers:
            worker.ready()
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda i: outcome(workers[i % 2], user), range(100)))
        assert results.count(200) == 7
        assert results.count(429) == 93
        assert client.zcard(key) == 7
        assert 0 < client.pttl(key) <= 60_000
        assert client.zscore(key, "expired-synthetic-request") is None
    finally:
        for worker in workers:
            worker.close()


def test_real_client_pool_pressure_fails_closed_and_recovers(redis_configuration):
    configuration, _ = redis_configuration
    configuration = Settings.model_validate(
        {**configuration.model_dump(), "redis_max_connections": 1}
    )
    worker = RedisRateLimiter(configuration)
    try:
        worker.ready()
        pool = worker.client.connection_pool
        held = pool.get_connection()
        try:
            with pytest.raises(Failure) as exhausted:
                worker.check(configuration.principals[0])
            assert exhausted.value.code == "RATE_LIMIT_UNAVAILABLE"
            assert failure_status(exhausted.value) == 503
        finally:
            pool.release(held)
        worker.check(configuration.principals[0])
        worker.ready()
    finally:
        worker.close()


def test_real_chat_leases_share_global_and_principal_limits(redis_configuration):
    configuration, client = redis_configuration
    user, other = configuration.principals
    first, second = (RedisRateLimiter(configuration) for _ in range(2))
    global_key = f"{configuration.redis_key_prefix}:chat:global"
    try:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            with first.chat(user):
                assert client.zcard(global_key) == 1
                with pytest.raises(Failure) as denied:
                    with second.chat(user.model_copy(update={"metrics": ()})):
                        pytest.fail("Grant changes must not bypass the user's active slot")
                assert denied.value.code == "CHAT_IN_PROGRESS"
                with second.chat(other):
                    assert client.zcard(global_key) == 2
                raise RuntimeError("synthetic failure")
        assert client.zcard(global_key) == 0
        with second.chat(user):
            assert client.zcard(global_key) == 1
    finally:
        first.close()
        second.close()


def test_global_admission_is_atomic_under_real_contention(redis_configuration):
    configuration, client = redis_configuration
    configuration = Settings.model_validate(
        {**configuration.model_dump(), "max_concurrent_chats": 3}
    )
    user = configuration.principals[0]
    workers = [RedisRateLimiter(configuration) for _ in range(2)]
    held = []
    keys = []

    def enter(index):
        principal = user.model_copy(update={"id": f"synthetic-{index}"})
        key = f"{configuration.redis_key_prefix}:chat:{principal_key(principal)}"
        lease = workers[index % 2].chat(principal)
        try:
            lease.__enter__()
            return lease, key
        except Failure as error:
            assert error.code == "CHAT_CAPACITY"
            return None, key

    try:
        with ThreadPoolExecutor(max_workers=16) as pool:
            for lease, key in pool.map(enter, range(100)):
                keys.append(key)
                if lease is not None:
                    held.append(lease)
        assert len(held) == 3
        assert client.zcard(f"{configuration.redis_key_prefix}:chat:global") == 3
    finally:
        for lease in held:
            lease.__exit__(None, None, None)
        client.delete(*keys)
        for worker in workers:
            worker.close()


def test_expired_lease_cannot_release_a_new_request(redis_configuration):
    configuration, client = redis_configuration
    user = configuration.principals[0]
    worker = RedisRateLimiter(configuration)
    global_key = f"{configuration.redis_key_prefix}:chat:global"
    principal_key_name = f"{configuration.redis_key_prefix}:chat:{principal_key(user)}"
    old = worker.chat(user)
    try:
        old.__enter__()
        token = client.zrange(global_key, 0, -1)[0]
        assert 0 < client.pttl(global_key) <= configuration.admission_lease_seconds * 1000
        seconds, microseconds = client.time()
        expired = seconds * 1000 + microseconds // 1000 - 1
        for key in (global_key, principal_key_name):
            client.zadd(key, {token: expired})
        with worker.chat(user):
            with pytest.raises(Failure) as failure:
                old.__exit__(None, None, None)
            assert failure.value.code == "ADMISSION_EXPIRED"
            assert client.zcard(global_key) == 1
        assert client.zcard(global_key) == 0
    finally:
        old.__exit__(None, None, None)
        worker.close()


def test_real_api_chat_history_and_cross_worker_admission(redis_configuration, credentials):
    configuration, client = redis_configuration
    user = configuration.principals[0]
    headers = {"Authorization": "Bearer " + credentials[user.id]}
    entered, release = Event(), Event()

    class BlockingModel(MockModel):
        def plan(self, *args, **kwargs):
            entered.set()
            assert release.wait(timeout=10)
            return super().plan(*args, **kwargs)

    # An unrecognized question reaches the injected model, holding the first API's lease.
    with (
        TestClient(create_app(configuration, model=BlockingModel({}))) as first,
        TestClient(create_app(configuration)) as second,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        pending = pool.submit(
            first.post,
            "/ews-chatbot/chat",
            headers=headers,
            json={"message": "Please show loan exposure by region as of 2026-09-30"},
        )
        try:
            assert entered.wait(timeout=5)
            denied = second.post(
                "/api/v1/chat",
                headers=headers,
                json={"message": "Show total loan exposure by region"},
            )
            assert denied.status_code == 429
            assert denied.json()["error"]["code"] == "CHAT_IN_PROGRESS"
        finally:
            release.set()
        pending.result(timeout=10)
        response = second.post(
            "/ews-chatbot/chat",
            headers=headers,
            json={"message": "Show total loan exposure by region"},
        )
        assert response.status_code == 200
        assert response.json()["results"] == [
            {"region": "Demo North", "loan_exposure": "175000.50"},
            {"region": "Demo South", "loan_exposure": "75000.00"},
        ]
        session = response.json()["session_id"]
        history = first.get(f"/ews-chatbot/load_session/{session}", headers=headers)
        assert history.status_code == 200
        assert history.json()["messages"][-1]["results"] == response.json()["results"]
        assert client.zcard(f"{configuration.redis_key_prefix}:chat:global") == 0


def test_independent_api_instances_share_quota(redis_configuration, credentials):
    configuration, client = redis_configuration
    user = configuration.principals[0]
    headers = {"Authorization": "Bearer " + credentials[user.id]}
    with (
        TestClient(create_app(configuration)) as first,
        TestClient(create_app(configuration)) as second,
    ):
        for i in range(7):
            worker = first if i % 2 else second
            response = worker.get("/ews-chatbot/get_all_sessions", headers=headers)
            assert response.status_code == 200
            assert response.json() == {"sessions": []}
        assert first.get("/ews-chatbot/get_all_sessions", headers=headers).status_code == 429
        assert second.get("/ews-chatbot/get_all_sessions", headers=headers).status_code == 429
        assert first.get("/api/v1/health/ready").status_code == 200
        key = f"{configuration.redis_key_prefix}:rate:{principal_key(user)}"
        assert client.zcard(key) == 7
