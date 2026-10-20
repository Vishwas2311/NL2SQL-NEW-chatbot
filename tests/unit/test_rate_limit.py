"""Quota concurrency, expiry, isolation and fail-closed transport contracts."""

from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest
from fastapi.testclient import TestClient
from nl2sql.bootstrap.factory import create_app
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.rate_limit import (
    ACQUIRE_CHAT,
    PROBE,
    RELEASE_CHAT,
    ROLLING_WINDOW,
    MemoryRateLimiter,
    RedisRateLimiter,
    principal_key,
)
from nl2sql.settings import Settings
from pydantic import SecretStr, ValidationError
from redis.exceptions import ConnectionError as RedisConnectionError


class SharedRedisContract:
    """Contract fake only; actual Lua behavior is checked by the real Redis suite."""

    def __init__(self):
        self.lock = Lock()
        self.counts = {}
        self.members = set()
        self.available = True
        self.closed = False
        self.reply = None

    def eval(self, script, numkeys, key, *arguments):
        if not self.available:
            raise RedisConnectionError("synthetic private credential sentinel")
        if self.reply is not None:
            return self.reply
        if script == PROBE:
            assert numkeys == 1
            return 1
        assert script == ROLLING_WINDOW and numkeys == 1
        limit, member = arguments
        with self.lock:
            assert member not in self.members
            self.members.add(member)
            if self.counts.get(key, 0) >= limit:
                return 0
            self.counts[key] = self.counts.get(key, 0) + 1
            return 1

    def ping(self):
        if not self.available:
            raise RedisConnectionError("synthetic private credential sentinel")
        return True

    def close(self):
        self.closed = True


def configured(settings, **updates):
    return Settings.model_validate(
        {
            **settings.model_dump(),
            "rate_limit_backend": "redis",
            "redis_url": SecretStr("redis://127.0.0.1:6379/0"),
            **updates,
        }
    )


def outcome(limiter, user):
    try:
        limiter.check(user)
        return 200
    except Failure as error:
        return error.status


def test_rolling_memory_quota_expires_and_isolates_tenants(settings):
    now = [100.0]
    limiter = MemoryRateLimiter(1, lambda: now[0])
    user = settings.principals[0]
    limiter.check(user)
    assert outcome(limiter, user) == 429
    limiter.check(user.model_copy(update={"tenant": "another-synthetic-tenant"}))
    now[0] = 160.0
    limiter.check(user)
    limiter.ready()
    limiter.close()


def test_independent_redis_clients_share_one_atomic_quota(settings):
    store = SharedRedisContract()
    configuration = configured(settings, requests_per_minute=7)
    workers = [RedisRateLimiter(configuration, store) for _ in range(2)]
    user = settings.principals[0]
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda i: outcome(workers[i % 2], user), range(100)))
    assert results.count(200) == 7
    assert results.count(429) == 93
    assert user.id not in next(iter(store.counts))
    assert principal_key(user) == principal_key(user.model_copy(update={"metrics": ()}))


@pytest.mark.parametrize("reply", [True, "1", -1, 2])
def test_malformed_redis_decision_fails_closed(settings, reply):
    store = SharedRedisContract()
    store.reply = reply
    assert outcome(RedisRateLimiter(configured(settings), store), settings.principals[0]) == 503


def test_redis_failure_blocks_startup_and_closes_client(settings):
    store = SharedRedisContract()
    store.available = False
    limiter = RedisRateLimiter(configured(settings), store)

    def unexpected_resources(*_):
        raise AssertionError("Redis readiness must precede database allocation")

    with pytest.raises(Failure) as error:
        with TestClient(
            create_app(
                settings,
                resources_factory=unexpected_resources,
                rate_limiter_factory=lambda _: limiter,
            )
        ):
            pass
    assert error.value.code == "RATE_LIMIT_UNAVAILABLE"
    assert "sentinel" not in str(error.value)
    assert store.closed


def test_api_quota_and_outage_use_safe_errors_without_local_fallback(settings, credentials):
    store = SharedRedisContract()
    configuration = configured(settings, requests_per_minute=1)
    limiter = RedisRateLimiter(configuration, store)
    headers = {"Authorization": "Bearer " + credentials[settings.principals[0].id]}
    with TestClient(create_app(configuration, rate_limiter_factory=lambda _: limiter)) as client:
        first = client.get("/ews-chatbot/get_all_sessions", headers=headers)
        assert first.status_code == 200
        denied = client.get("/ews-chatbot/get_all_sessions", headers=headers)
        assert denied.status_code == 429
        store.available = False
        blocked = client.get("/ews-chatbot/get_all_sessions", headers=headers)
        assert blocked.status_code == 503
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_UNAVAILABLE"
        assert "sentinel" not in blocked.text
        assert client.get("/api/v1/health/ready").status_code == 503
        assert client.get("/health").status_code == 200
    assert store.closed


@pytest.mark.parametrize(
    "values",
    [
        {"api_workers": 2},
        {"rate_limit_backend": "redis"},
        {"redis_url": "http://127.0.0.1:6379"},
        {"redis_url": "redis://192.0.2.1:6379"},
        {"redis_url": "rediss://redis.example.invalid:6379?ssl_cert_reqs=none"},
        {"redis_url": "redis://127.0.0.1:99999"},
        {"redis_url": "redis://127.0.0.1/not-a-database"},
        {"redis_key_prefix": "unsafe prefix"},
    ],
)
def test_unsafe_or_partially_configured_vm_settings_reject(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_vm_settings_allow_shared_loopback_or_tls_store(settings):
    assert configured(settings, api_workers=4).api_workers == 4
    checked = configured(settings, redis_url=SecretStr("rediss://redis.example.invalid:6379/0"))
    assert "example.invalid" not in repr(checked)


def test_memory_chat_limits_and_exception_cleanup(settings):
    user, other = settings.principals
    limiter = MemoryRateLimiter(60, max_chats=2)
    with pytest.raises(RuntimeError):
        with limiter.chat(user):
            with pytest.raises(Failure) as denied:
                with limiter.chat(user):
                    pytest.fail("A user must not take a second active slot")
            assert denied.value.code == "CHAT_IN_PROGRESS"
            with limiter.chat(other):
                with pytest.raises(Failure) as full:
                    with limiter.chat(other.model_copy(update={"id": "third"})):
                        pytest.fail("Global active slots must be bounded")
                assert full.value.code == "CHAT_CAPACITY"
            raise RuntimeError("synthetic use-case failure")
    with limiter.chat(user):
        pass
    assert limiter._active == {}


@pytest.mark.parametrize("work_fails", [False, True])
def test_redis_release_outage_blocks_success_and_preserves_original_failure(settings, work_fails):
    class LeaseCommands(SharedRedisContract):
        def eval(self, script, numkeys, *args):
            assert numkeys == 2
            if script == ACQUIRE_CHAT:
                return 1
            assert script == RELEASE_CHAT
            raise RedisConnectionError("synthetic private credential sentinel")

    limiter = RedisRateLimiter(configured(settings), LeaseCommands())
    with pytest.raises(Failure) as error:
        with limiter.chat(settings.principals[0]):
            if work_fails:
                raise Failure("SYNTHETIC_FAILURE", "Original error.", 400)
    assert error.value.code == ("SYNTHETIC_FAILURE" if work_fails else "RATE_LIMIT_UNAVAILABLE")
    assert "sentinel" not in str(error.value)


@pytest.mark.parametrize(
    "updates",
    [
        {"max_concurrent_chats": 1, "max_concurrent_chats_per_principal": 2},
        {"admission_lease_seconds": 10, "request_timeout_seconds": 15},
        {"redis_url": "redis://127.0.0.1:6379/0", "redis_ca_bundle": "synthetic-ca.pem"},
    ],
)
def test_admission_budget_and_tls_mismatches_reject(updates):
    with pytest.raises(ValidationError):
        Settings(**updates)
