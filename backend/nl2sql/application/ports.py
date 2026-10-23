"""Small execution port used by the existing application service."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from threading import Event
from typing import Literal, Protocol

from nl2sql.domain.models import (
    Answer,
    Capability,
    EntityMapping,
    ExecutionResult,
    Principal,
    QueryPlan,
)
from nl2sql.domain.planning import ClarificationRequest, PendingQuestion
from nl2sql.domain.search import SearchRecord
from nl2sql.domain.sessions import Message, SessionState, SessionSummary


class QueryExecutor(Protocol):
    """Oracle and SQLite accept only approved query capabilities."""

    @property
    def dialect(self) -> Literal["sqlite", "oracle"]:
        """Compiler target of this configured, approved executor."""
        ...

    def execute(self, capability: Capability, principal: Principal) -> ExecutionResult:
        """Execute bounded read-only data retrieval."""
        ...

    def resolve_entity(
        self,
        entity: EntityMapping,
        phrase: str,
        principal: Principal,
        deadline: float | None = None,
    ) -> str:
        """Exact lookup through separately certified entity scope mappings."""
        ...

    def close(self) -> None:
        """Release owned pools after in-flight users have drained."""
        ...

    def ready(self) -> None:
        """Read-only liveness through the selected backend."""
        ...


class ChatHandler(Protocol):
    """The unchanged transport depends on a use case, not a particular runtime lifecycle."""

    def chat(
        self,
        question: str,
        session_id: str | None,
        principal: Principal,
        claimed_user_id: str | None,
        spans: dict[str, float],
    ) -> Answer:
        """Return the stable typed answer contract."""
        ...


class Readiness(Protocol):
    """The public route cannot assume a SQLite connection API."""

    def ready(self) -> None:
        """Check the selected data adapter."""
        ...


class ApplicationResources(Protocol):
    """Structural properties preserve the original resource factory's test seam."""

    @property
    def auth(self) -> IdentityProvider:
        """Current server-owned identity adapter."""
        ...

    @property
    def sessions(self) -> SessionRepository:
        """Shared owner-scoped conversation store."""
        ...

    @property
    def conversations(self) -> SessionAccess:
        """Session use cases recheck current identity around protected responses."""
        ...

    @property
    def database(self) -> Readiness:
        """Backend-independent readiness."""
        ...

    @property
    def service(self) -> ChatHandler:
        """Request use case."""
        ...

    def close(self) -> None:
        """Drain resources on lifespan exit."""
        ...

    def components(self) -> dict[str, str]:
        """Sanitized local readiness signals; never credentials or schema text."""
        ...


@dataclass(frozen=True)
class ModelResult:
    """Provider-measured usage; unavailable token counts remain unknown."""

    plan: QueryPlan | ClarificationRequest
    calls: int
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None


class ModelProvider(Protocol):
    """Models never receive a database tool or execution capability."""

    def plan(
        self, question: str, context: str, deadline: float, cancelled: Event | None = None
    ) -> ModelResult:
        """Return a strict typed plan or a safe provider failure."""
        ...

    def close(self) -> None:
        """Release inference connections."""
        ...


class EmbeddingProvider(Protocol):
    """Optional local encoder; implementations require separate benchmark promotion."""

    def encode(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Encode metadata only, never customer rows."""
        ...


@dataclass(frozen=True)
class Candidate:
    """Ranking evidence is not a probability of SQL correctness."""

    metric_id: str
    method: str
    rank_score: float


class IdentityProvider(Protocol):
    """Resolve current identity from credentials at the transport boundary."""

    def authenticate(self, authorization: str | None) -> Principal:
        """Never accept identity or grants from request bodies."""
        ...

    def assert_current(self, principal: Principal) -> None:
        """Reject a principal whose server-owned permissions have changed or been revoked."""
        ...


class SchemaRetriever(Protocol):
    """Find authorized semantic evidence without giving it execution authority."""

    def retrieve(
        self, text: str, principal: Principal, domain: str | None = None
    ) -> tuple[Candidate, ...]:
        """Return bounded authorized metric candidates."""
        ...

    def ambiguous_alias(self, text: str, principal: Principal) -> bool:
        """Report ambiguity among authorized aliases."""
        ...

    def authorized_schema(self, principal: Principal) -> tuple[SearchRecord, ...]:
        """Return only the caller's certified evidence."""
        ...


class SessionRepository(Protocol):
    """Transactional conversation access independent of the storage adapter."""

    def create(self, owner: str, title: str) -> SessionState:
        """Create an owned conversation."""
        ...

    def state(self, key: str, owner: str) -> SessionState:
        """Read owned, unexpired context."""
        ...

    def list_owned(self, owner: str) -> tuple[SessionSummary, ...]:
        """List only the authenticated owner's conversations."""
        ...

    def messages(
        self, key: str, owner: str, scope_digest: str | None = None
    ) -> tuple[Message, ...]:
        """Read owned history under current scope."""
        ...

    def append(
        self,
        state: SessionState,
        owner: str,
        question: str,
        answer: Answer,
        plan: QueryPlan | None,
        scope_digest: str = "",
        pending: PendingQuestion | None = None,
    ) -> None:
        """Atomically commit messages and context if the version is current."""
        ...

    def delete(self, key: str, owner: str) -> None:
        """Delete only an owned conversation."""
        ...

    def close(self) -> None:
        """Release adapter resources."""
        ...


class SessionAccess(Protocol):
    """Owned conversation use cases, independent of HTTP and persistence drivers."""

    def list_owned(self, principal: Principal) -> tuple[SessionSummary, ...]:
        """List currently authorized conversation summaries."""
        ...

    def messages(self, key: str, principal: Principal) -> tuple[Message, ...]:
        """Load history after checking current permissions."""
        ...

    def delete(self, key: str, principal: Principal) -> None:
        """Delete an owned conversation, including expired records."""
        ...


class RateLimiter(Protocol):
    """Shared rate and active-chat admission never confer business permissions."""

    @property
    def backend(self) -> str:
        """Sanitized backend name for readiness diagnostics."""
        ...

    def check(self, principal: Principal) -> None:
        """Consume one request or raise a safe denial/unavailability error."""
        ...

    def chat(self, principal: Principal) -> AbstractContextManager[None]:
        """Hold one active-chat slot until work finishes, including exceptional exits."""
        ...

    def ready(self) -> None:
        """Fail readiness when the configured quota store is unavailable."""
        ...

    def close(self) -> None:
        """Release connections at process shutdown."""
        ...
