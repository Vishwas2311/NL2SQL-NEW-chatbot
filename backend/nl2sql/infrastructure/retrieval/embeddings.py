"""Configured metadata encoders with bounded batches, validation and single-flight caching."""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from threading import Event, Lock

import httpx
from pydantic import BaseModel, ConfigDict

from nl2sql.application.ports import EmbeddingProvider
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.http_policy import private_client, private_endpoint
from nl2sql.infrastructure.retrieval.embedding_cache import (
    load_vectors,
    restricted_path,
    save_vectors,
)
from nl2sql.infrastructure.retrieval.vector_index import normalized
from nl2sql.settings import Settings
from nl2sql.telemetry import REQUEST_DEADLINE, measured


class FakeEmbedding:
    """Deterministic token hashing for plumbing tests; no semantic accuracy claim."""

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Produce reproducible nonzero vectors without external packages or weights."""
        return tuple(
            tuple(
                (hashlib.sha256(text.encode()).digest()[i % 32] + 1) / 256
                for i in range(self.dimension)
            )
            for text in texts
        )


class _Embedding(BaseModel):
    model_config = ConfigDict(extra="ignore")
    index: int
    embedding: tuple[float, ...]


class _Embeddings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str
    version: str | None = None
    data: tuple[_Embedding, ...]


class PrivateEmbedding:
    """Reuse the private inference host/TLS gate; no public embedding egress mode."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        private_endpoint(settings.embedding_endpoint, settings.approved_embedding_hosts)
        self.client = client or private_client(settings.model_ca_bundle)
        self.settings = settings

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Bound streamed replies before parsing, checking identity and ordered batch indexes."""
        headers: dict[str, str] = {}
        if self.settings.embedding_key is not None:
            headers["Authorization"] = "Bearer " + self.settings.embedding_key.get_secret_value()
        remaining = min(
            self.settings.embedding_timeout_seconds,
            (REQUEST_DEADLINE.get() or float("inf")) - time.time(),
        )
        if remaining <= 0:
            raise Failure("EMBEDDING_TIMEOUT", "Optional encoding timed out.", "timeout")
        deadline = time.monotonic() + remaining
        try:
            with self.client.stream(
                "POST",
                self.settings.embedding_endpoint or "",
                headers=headers,
                json={"model": self.settings.embedding_model, "input": texts},
                timeout=remaining,
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    if len(data) + len(chunk) > 4_000_000 or time.monotonic() >= deadline:
                        raise ValueError("Embedding response exceeded its budget")
                    data.extend(chunk)
            reply = _Embeddings.model_validate_json(bytes(data))
            if (
                reply.model != self.settings.embedding_model
                or reply.version not in (None, self.settings.embedding_version)
                or tuple(item.index for item in reply.data) != tuple(range(len(texts)))
            ):
                raise ValueError("Embedding identity, version or batch shape mismatch")
            return tuple(item.embedding for item in reply.data)
        except httpx.HTTPError as error:
            raise Failure(
                "EMBEDDING_UNAVAILABLE", "Optional encoding is unavailable.", "unavailable"
            ) from error

    def close(self) -> None:
        """Close owned HTTP connections after runtime users drain."""
        self.client.close()


class ManagedEncoder:
    """One bounded lock coalesces duplicate content and limits external calls to one at a time."""

    def __init__(self, settings: Settings, provider: EmbeddingProvider) -> None:
        self.settings = settings
        self.provider = provider
        self.identity = hashlib.sha256(
            json.dumps(
                (
                    settings.embedding_mode,
                    settings.embedding_model,
                    settings.embedding_version,
                    settings.embedding_dimension,
                    settings.embedding_normalization,
                )
            ).encode()
        ).hexdigest()
        self._lock = Lock()
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        if settings.index_storage_path is not None:
            self._cache.update(
                load_vectors(
                    restricted_path(settings.index_storage_path, self.identity),
                    self.identity,
                    settings.embedding_dimension,
                    settings.embedding_normalization,
                )
            )

        while len(self._cache) > settings.embedding_cache_entries:
            self._cache.popitem(last=False)

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """The existing encoder port remains compatible with injected installed providers."""
        return self.encode_bounded(texts)

    @measured("embedding_ms")
    def encode_bounded(
        self,
        texts: tuple[str, ...],
        deadline: float | None = None,
        cancelled: Event | None = None,
    ) -> tuple[tuple[float, ...], ...]:
        """No partial cache publication on failed, cancelled, late or malformed batches."""
        end = min(
            deadline or float("inf"),
            REQUEST_DEADLINE.get() or float("inf"),
            time.time() + self.settings.embedding_timeout_seconds,
        )
        if len(texts) > 10_000 or sum(len(text.encode()) for text in texts) > 10_000_000:
            raise ValueError("Embedding input exceeds its budget")
        # RLock's context-manager entry cannot enforce the request deadline.
        acquired = self._lock.acquire(  # pylint: disable=consider-using-with
            timeout=max(0, end - time.time())
        )
        if not acquired:
            raise Failure("EMBEDDING_TIMEOUT", "Optional encoding is busy.", "timeout")
        try:
            keys = tuple(
                hashlib.sha256((self.identity + text).encode()).hexdigest() for text in texts
            )
            pending = dict(zip(keys, texts, strict=True))
            vectors = {key: self._cache[key] for key in keys if key in self._cache}
            missing = [key for key in pending if key not in vectors]
            size = self.settings.embedding_batch_size
            for offset in range(0, len(missing), size):
                self._check(end, cancelled)
                batch = missing[offset : offset + size]
                encoded = self.provider.encode(tuple(pending[key] for key in batch))
                self._check(end, cancelled)
                if len(encoded) != len(batch):
                    raise ValueError("Embedding batch is incomplete")
                for key, vector in zip(batch, encoded, strict=True):
                    if len(vector) != self.settings.embedding_dimension:
                        raise ValueError("Embedding dimension mismatch")
                    unit = normalized(vector)
                    vectors[key] = unit if self.settings.embedding_normalization == "l2" else vector
            self._check(end, cancelled)
            for key, vector in vectors.items():
                self._cache[key] = vector
                self._cache.move_to_end(key)
            while len(self._cache) > self.settings.embedding_cache_entries:
                self._cache.popitem(last=False)
            return tuple(vectors[key] for key in keys)
        finally:
            self._lock.release()

    def checkpoint(self, metadata_texts: tuple[str, ...]) -> None:
        """Persist a bounded restart cache during preparation, never on query cache misses."""
        root = self.settings.index_storage_path
        if root is None:
            return
        # A finite float uses fewer than 32 JSON bytes; reserve envelope and hash space.
        limit = min(
            self.settings.embedding_cache_entries,
            19_000_000 // (self.settings.embedding_dimension * 32 + 80),
        )
        allowed = {
            hashlib.sha256((self.identity + text).encode()).hexdigest() for text in metadata_texts
        }
        with self._lock:
            keys = tuple(key for key in self._cache if key in allowed)[-limit:] if limit else ()
            entries = {key: self._cache[key] for key in keys}
        try:
            save_vectors(
                restricted_path(root, self.identity),
                self.identity,
                self.settings.embedding_dimension,
                self.settings.embedding_normalization,
                entries,
            )
        except (OSError, ValueError):
            logging.getLogger("nl2sql").warning("embedding_cache_write_failed")

    @staticmethod
    def _check(deadline: float, cancelled: Event | None) -> None:
        if cancelled is not None and cancelled.is_set():
            raise Failure("EMBEDDING_CANCELLED", "Optional encoding was cancelled.", "conflict")
        if time.time() >= deadline:
            raise Failure("EMBEDDING_TIMEOUT", "Optional encoding timed out.", "timeout")

    def close(self) -> None:
        """Close owned HTTP resources; the registrar owns an installed local runtime."""
        if isinstance(self.provider, PrivateEmbedding):
            self.provider.close()


_LOCAL_PROVIDERS: dict[str, Callable[[Path], EmbeddingProvider]] = {}


def register_local_embedding(model: str, factory: Callable[[Path], EmbeddingProvider]) -> None:
    """Trusted integration binds an installed runtime, without automatic downloads."""
    if model in _LOCAL_PROVIDERS:
        raise ValueError("Installed embedding adapter is already registered")
    _LOCAL_PROVIDERS[model] = factory


def build_embedding(settings: Settings) -> ManagedEncoder | None:
    """Same configured identity is used by staging, publication and query-time encoding."""
    if settings.embedding_mode == "disabled":
        return None
    if settings.embedding_model == "disabled" or settings.embedding_version == "disabled":
        raise ValueError("An embedding model ID and version are required")
    if settings.embedding_mode == "private_http":
        provider: EmbeddingProvider = PrivateEmbedding(settings)
    elif settings.embedding_mode == "fake":
        if settings.data_classification != "synthetic":
            raise ValueError("Fake embeddings are only for synthetic development")
        provider = FakeEmbedding(settings.embedding_dimension)
    else:
        path = settings.embedding_local_path
        if path is None or not path.exists() or settings.embedding_model not in _LOCAL_PROVIDERS:
            raise ValueError(
                "An existing local model and installed adapter registration are required"
            )
        provider = _LOCAL_PROVIDERS[settings.embedding_model](path)
    return ManagedEncoder(settings, provider)
