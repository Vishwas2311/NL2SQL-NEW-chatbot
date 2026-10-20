"""An explicit loopback Redis is required for real-server and spawned-worker tests."""

import os
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from nl2sql.infrastructure.rate_limit import principal_key
from nl2sql.settings import Settings
from pydantic import SecretStr


@pytest.fixture
def redis_configuration(settings):
    url = os.environ.get("NL2SQL_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set NL2SQL_TEST_REDIS_URL for the explicit local Redis integration suite")
    assert urlparse(url).hostname in {"127.0.0.1", "localhost", "::1"}
    import redis

    configuration = Settings.model_validate(
        {
            **settings.model_dump(),
            "rate_limit_backend": "redis",
            "redis_url": SecretStr(url),
            "redis_key_prefix": "ews:test:" + uuid4().hex,
            "requests_per_minute": 7,
            "api_workers": 2,
            # Isolate Lua correctness from the production client's bounded-pressure behavior.
            "redis_max_connections": 32,
            "redis_timeout_seconds": 2,
        }
    )
    client = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)
    client.ping()  # A selected but unavailable server fails; it never skips.
    keys = [f"{configuration.redis_key_prefix}:chat:global"]
    for user in configuration.principals:
        keys.extend(
            (
                f"{configuration.redis_key_prefix}:rate:{principal_key(user)}",
                f"{configuration.redis_key_prefix}:chat:{principal_key(user)}",
            )
        )
    try:
        yield configuration, client
    finally:
        client.delete(*keys)  # Only this test's keys; never FLUSHDB.
        client.close()
