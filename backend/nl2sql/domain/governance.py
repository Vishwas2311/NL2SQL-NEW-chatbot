"""Immutable reviewer and administrator identity contracts."""

from typing import Literal

from pydantic import Field, SecretStr

from nl2sql.domain.models import FrozenModel

ReviewRole = Literal["physical", "business", "security"]


class Reviewer(FrozenModel):
    """Configured trust anchors must be protected by the company secrets mechanism."""

    id: str
    roles: tuple[ReviewRole, ...]
    secret: SecretStr


class AdminActor(FrozenModel):
    """Host/SSO-issued identity, not the browser's analyst user_id."""

    id: str
    actions: tuple[str, ...]


class ApprovalEvidence(FrozenModel):
    """Roles are constrained by the configured reviewer, not self-granted JWT claims."""

    reviewer: str
    roles: tuple[ReviewRole, ...]
    candidate_id: str
    reference: str = Field(min_length=1, max_length=300)
    synthetic: bool
