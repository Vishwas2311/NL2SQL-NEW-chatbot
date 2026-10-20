"""Immutable conversation contracts independent of persistence."""

from nl2sql.domain.models import FrozenModel, QueryPlan, Row


class Message(FrozenModel):
    """Saved rows are display history and never an execution authority."""

    role: str
    content: str
    timestamp: str
    results: tuple[Row, ...] = ()
    query_reference: str | None = None
    scope_digest: str = ""


class SessionSummary(FrozenModel):
    """Legacy-compatible owned conversation summary."""

    session_id: str
    title: str
    updated_at: str
    user_id: str


class SessionState(FrozenModel):
    """Minimal approved context; never raw prior messages in model prompts."""

    session_id: str
    version: int
    last_plan: QueryPlan | None
