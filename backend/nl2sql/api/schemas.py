"""Stable EWS and versioned API request/response contracts."""

from pydantic import Field

from nl2sql.domain.models import FrozenModel, Row
from nl2sql.domain.sessions import SessionSummary


class ChatRequest(FrozenModel):
    """Existing EWS body; user_id is only a consistency assertion."""

    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=100)
    user_id: str | None = Field(default=None, max_length=100)


class EWSResponse(FrozenModel):
    """Stable keys consumed by the immutable JavaScript reference."""

    session_id: str
    response: str
    results: tuple[Row, ...]
    status: str
    metadata: dict[str, object] | None = None


class SessionList(FrozenModel):
    """Bounded legacy-compatible session list."""

    sessions: tuple[SessionSummary, ...]


class DisplayMessage(FrozenModel):
    """Public history contains safe rows without internal policy details."""

    role: str
    content: str
    timestamp: str
    results: tuple[Row, ...]


class SessionHistory(FrozenModel):
    """Owned message collection consumed by the existing UI."""

    messages: tuple[DisplayMessage, ...]
