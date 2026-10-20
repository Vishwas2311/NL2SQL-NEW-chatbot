"""Session ownership and response-time authorization are application use cases."""

from nl2sql.application.ports import IdentityProvider, SessionRepository
from nl2sql.application.query.planning import principal_hash
from nl2sql.domain.models import Principal
from nl2sql.domain.sessions import Message, SessionSummary


class SessionService:
    """Persistence cannot decide whether a previously authenticated identity is still current."""

    def __init__(self, repository: SessionRepository, identity: IdentityProvider) -> None:
        self.repository = repository
        self.identity = identity

    def list_owned(self, principal: Principal) -> tuple[SessionSummary, ...]:
        """Never expose old question text through sidebar titles after grants change."""
        self.identity.assert_current(principal)
        summaries = tuple(
            item.model_copy(update={"title": "Conversation"})
            for item in self.repository.list_owned(principal.id)
        )
        self.identity.assert_current(principal)
        return summaries

    def messages(self, key: str, principal: Principal) -> tuple[Message, ...]:
        """A revocation during the read blocks the protected response."""
        self.identity.assert_current(principal)
        messages = self.repository.messages(key, principal.id, principal_hash(principal))
        self.identity.assert_current(principal)
        return messages

    def delete(self, key: str, principal: Principal) -> None:
        """Owner-bound deletion is allowed even after a conversation expires."""
        self.identity.assert_current(principal)
        self.repository.delete(key, principal.id)
        self.identity.assert_current(principal)
