"""Small execution port used by the existing application service."""

from typing import Literal, Protocol

from nl2sql.auth import Authenticator
from nl2sql.domain import Answer, Capability, EntityMapping, ExecutionResult, Principal
from nl2sql.security import SQLValidator
from nl2sql.sessions import SessionStore


class QueryExecutor(Protocol):
    """Oracle and SQLite accept only approved query capabilities."""

    validator: SQLValidator

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
    def auth(self) -> Authenticator:
        """Current server-owned identity adapter."""
        ...

    @property
    def sessions(self) -> SessionStore:
        """Shared owner-scoped conversation store."""
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
