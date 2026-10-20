"""Atomic request quotas and active-chat leases, shared across Redis API workers."""

import hashlib
import json
import logging
import time
from collections import deque
from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Lock
from typing import Protocol, cast
from uuid import uuid4

from nl2sql.application.ports import RateLimiter
from nl2sql.domain.models import Failure, Principal
from nl2sql.settings import Settings

LOGGER = logging.getLogger("nl2sql")

ROLLING_WINDOW = """
local stamp = redis.call('TIME')
local now = tonumber(stamp[1]) * 1000 + math.floor(tonumber(stamp[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000)
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then
    return 0
end
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('PEXPIRE', KEYS[1], 60000)
return 1
"""

ACQUIRE_CHAT = """
local stamp = redis.call('TIME')
local now = tonumber(stamp[1]) * 1000 + math.floor(tonumber(stamp[2]) / 1000)
for i = 1, 2 do
    redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now)
end
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[1]) then return 0 end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[2]) then return -1 end
for i = 1, 2 do
    redis.call('ZADD', KEYS[i], now + tonumber(ARGV[3]), ARGV[4])
    redis.call('PEXPIRE', KEYS[i], ARGV[3])
end
return 1
"""

RELEASE_CHAT = """
local stamp = redis.call('TIME')
local now = tonumber(stamp[1]) * 1000 + math.floor(tonumber(stamp[2]) / 1000)
local valid = 1
for i = 1, 2 do
    local expires = redis.call('ZSCORE', KEYS[i], ARGV[1])
    if not expires or tonumber(expires) <= now then valid = 0 end
    redis.call('ZREM', KEYS[i], ARGV[1])
end
return valid
"""

PROBE = """
redis.call('TIME')
-- Verify expiry and cleanup permissions before creating a probe key.
redis.call('PEXPIRE', KEYS[1], 1000)
redis.call('ZREM', KEYS[1], 'probe')
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', 0)
redis.call('ZADD', KEYS[1], 1, 'probe')
redis.call('PEXPIRE', KEYS[1], 1000)
local valid = redis.call('ZCARD', KEYS[1]) == 1
    and tonumber(redis.call('ZSCORE', KEYS[1], 'probe')) == 1
redis.call('ZREM', KEYS[1], 'probe')
if valid then return 1 end
return 0
"""


def chat_denied(result: int) -> None:
    """Expose a stable admission error without identity or server details."""
    if result == 0:
        raise Failure("CHAT_CAPACITY", "Chat capacity is busy; please retry shortly.", 429)
    if result == -1:
        raise Failure("CHAT_IN_PROGRESS", "A chat request is already running for this user.", 429)


def principal_key(principal: Principal) -> str:
    """Hash stable tenant/subject identity; grant changes must not reset its quota."""
    identity = json.dumps((principal.tenant, principal.id), separators=(",", ":"))
    return hashlib.sha256(identity.encode()).hexdigest()


class MemoryRateLimiter:
    """Single-process development quota; multi-worker configuration rejects this adapter."""

    backend = "memory"

    def __init__(
        self,
        limit: int,
        clock: Callable[[], float] = time.monotonic,
        max_chats: int = 8,
        per_principal: int = 1,
    ) -> None:
        self.limit = limit
        self.clock = clock
        self._lock = Lock()
        self._windows: dict[str, deque[float]] = {}
        self.max_chats = max_chats
        self.per_principal = per_principal
        self._active: dict[str, int] = {}

    def check(self, principal: Principal) -> None:
        """Consume an exact rolling-minute quota under one process lock."""
        with self._lock:
            window = self._windows.setdefault(principal_key(principal), deque())
            now = self.clock()
            while window and window[0] <= now - 60:
                window.popleft()
            if len(window) >= self.limit:
                raise Failure("RATE_LIMIT", "Too many requests; please try again shortly.", 429)
            window.append(now)

    @contextmanager
    def chat(self, principal: Principal) -> Generator[None]:
        """Hold a local slot through failures; a crashed process loses its local state."""
        key = principal_key(principal)
        with self._lock:
            chat_denied(0 if sum(self._active.values()) >= self.max_chats else 1)
            chat_denied(-1 if self._active.get(key, 0) >= self.per_principal else 1)
            self._active[key] = self._active.get(key, 0) + 1
        try:
            yield
        finally:
            with self._lock:
                self._active[key] -= 1
                if self._active[key] == 0:
                    del self._active[key]

    def ready(self) -> None:
        """No external resources are required."""

    def close(self) -> None:
        """Discard development counters at shutdown."""
        with self._lock:
            self._windows.clear()


class RedisCommands(Protocol):
    """Small synchronous boundary around redis-py's broad command return annotations."""

    def eval(self, script: str, numkeys: int, *keys_and_args: str | int) -> object:
        """Run one atomic script without command retries."""
        ...

    def ping(self) -> object:
        """Check the configured store."""
        ...

    def close(self) -> None:
        """Close the process-owned client and pool."""
        ...


class RedisFactory(Protocol):
    """Typed constructor boundary for redis-py's open-ended connection options."""

    def from_url(self, url: str, **options: object) -> RedisCommands:
        """Build a process-owned synchronous client."""
        ...


class RedisRateLimiter:
    """One server-clock Lua decision prevents check-then-increment races across workers."""

    backend = "redis"

    def __init__(self, settings: Settings, client: RedisCommands | None = None) -> None:
        # Redis is optional for development, never silently substituted in VM mode.
        from redis import Redis  # pylint: disable=import-outside-toplevel
        from redis.backoff import NoBackoff  # pylint: disable=import-outside-toplevel
        from redis.exceptions import RedisError  # pylint: disable=import-outside-toplevel
        from redis.retry import Retry  # pylint: disable=import-outside-toplevel

        if settings.redis_url is None:
            raise ValueError("Redis configuration is required")
        self._redis_error = RedisError
        self.limit = settings.requests_per_minute
        self.prefix = settings.redis_key_prefix
        self.max_chats = settings.max_concurrent_chats
        self.per_principal = settings.max_concurrent_chats_per_principal
        self.lease_ms = settings.admission_lease_seconds * 1000
        tls_options: dict[str, object] = {}
        if settings.redis_url.get_secret_value().startswith("rediss://"):
            tls_options.update(ssl_cert_reqs="required", ssl_check_hostname=True)
        if settings.redis_ca_bundle is not None:
            if not settings.redis_ca_bundle.is_file():
                raise ValueError("Redis CA bundle is unavailable")
            tls_options["ssl_ca_certs"] = str(settings.redis_ca_bundle)
        self.client = client or cast(RedisFactory, Redis).from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=settings.redis_timeout_seconds,
            socket_timeout=settings.redis_timeout_seconds,
            max_connections=settings.redis_max_connections,
            retry=Retry(NoBackoff(), 0),
            client_name="ews-nl2sql-rate-limit",
            decode_responses=False,
            **tls_options,
        )

    def _eval(self, script: str, keys: tuple[str, ...], *arguments: str | int) -> int:
        """No command replay: a timeout can occur after Redis applied the mutation."""
        try:
            result = self.client.eval(script, len(keys), *keys, *arguments)
        except self._redis_error:
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            ) from None
        if isinstance(result, bool) or not isinstance(result, int) or result not in (-1, 0, 1):
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            )
        return result

    def check(self, principal: Principal) -> None:
        """Count one accepted request; Redis failure never falls back to local counters."""
        key = f"{self.prefix}:rate:{principal_key(principal)}"
        result = self._eval(ROLLING_WINDOW, (key,), self.limit, uuid4().hex)
        if result == -1:
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            )
        if result == 0:
            raise Failure("RATE_LIMIT", "Too many requests; please try again shortly.", 429)

    @contextmanager
    def chat(self, principal: Principal) -> Generator[None]:
        """Expire crashed leases; never return a successful result after losing admission."""
        keys = (f"{self.prefix}:chat:global", f"{self.prefix}:chat:{principal_key(principal)}")
        token = uuid4().hex
        chat_denied(
            self._eval(ACQUIRE_CHAT, keys, self.max_chats, self.per_principal, self.lease_ms, token)
        )
        completed = False
        try:
            yield
            completed = True
        finally:
            try:
                released = self._eval(RELEASE_CHAT, keys, token)
                if completed and released != 1:
                    raise Failure("ADMISSION_EXPIRED", "Chat admission expired; please retry.", 503)
            except Failure:
                # Preserve an original use-case failure; uncertain leases expire by themselves.
                if completed:
                    raise
                LOGGER.warning('{"event":"chat_lease_release_failed"}')

    def ready(self) -> None:
        """Startup and readiness fail closed without disclosing credentials or endpoints."""
        try:
            result = self.client.ping()
        except self._redis_error:
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            ) from None
        if result is not True:
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            )
        if self._eval(PROBE, (f"{self.prefix}:probe:{uuid4().hex}",)) != 1:
            raise Failure(
                "RATE_LIMIT_UNAVAILABLE", "Request admission is temporarily unavailable.", 503
            )

    def close(self) -> None:
        """Release only this worker's Redis client."""
        self.client.close()


def build_rate_limiter(settings: Settings) -> RateLimiter:
    """Select the explicitly configured adapter; no inference or metadata is cached."""
    if settings.rate_limit_backend == "redis":
        return RedisRateLimiter(settings)
    return MemoryRateLimiter(
        settings.requests_per_minute,
        max_chats=settings.max_concurrent_chats,
        per_principal=settings.max_concurrent_chats_per_principal,
    )
