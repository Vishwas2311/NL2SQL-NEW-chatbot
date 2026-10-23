"""Administrative and reviewer authority comes from configured keys, never a candidate file."""

import time
from typing import Literal

import jwt
from pydantic import SecretStr

from nl2sql.domain.governance import AdminActor, ApprovalEvidence, Reviewer
from nl2sql.domain.models import Failure

ReviewRole = Literal["physical", "business", "security"]
ROLES: frozenset[str] = frozenset({"physical", "business", "security"})


class ApprovalAuthority:
    """HS256 is the local protected-secret adapter; corporate key/SSO qualification is separate."""

    def __init__(self, admin_key: SecretStr, reviewers: tuple[Reviewer, ...]) -> None:
        if len(admin_key.get_secret_value()) < 32 or any(
            len(item.secret.get_secret_value()) < 32 for item in reviewers
        ):
            raise ValueError("Administrative trust keys must contain at least 32 characters")
        if len({item.id for item in reviewers}) != len(reviewers):
            raise ValueError("Duplicate reviewer trust identities")
        self.admin_key = admin_key
        self.reviewers = {item.id: item for item in reviewers}

    def authenticate(self, token: str | None, action: str) -> AdminActor:
        """Every privileged command verifies issuer, audience, expiry and authorized action."""
        if not token or len(token) > 8192:
            raise Failure("ADMIN_DENIED", "A valid administrative identity is required.", "denied")
        try:
            claims = jwt.decode(
                token,
                self.admin_key.get_secret_value(),
                algorithms=["HS256"],
                audience="nl2sql-metadata-admin",
                issuer="nl2sql-metadata-admin",
                options={"require": ["sub", "iat", "exp", "iss", "aud", "actions"]},
            )
            actor = AdminActor(id=claims["sub"], actions=claims["actions"])
        except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as error:
            raise Failure(
                "ADMIN_DENIED", "Administrative authorization failed.", "denied"
            ) from error
        if action not in actor.actions:
            raise Failure("ADMIN_DENIED", "This administrative action is not authorized.", "denied")
        return actor

    def verify(
        self,
        tokens: tuple[str, ...],
        candidate_id: str,
        source_id: str,
        synthetic: bool,
        published: bool = False,
    ) -> tuple[ApprovalEvidence, ...]:
        """Published review evidence remains auditable; revoked trust keys still fail closed."""
        evidence: list[ApprovalEvidence] = []
        if len(tokens) > 16:
            raise Failure("APPROVAL_DENIED", "Too many approval records.", "denied")
        for token in tokens:
            try:
                if len(token) > 8192:
                    raise ValueError("Approval token budget")
                header = jwt.get_unverified_header(token)
                reviewer = self.reviewers.get(str(header.get("kid", "")))
                if reviewer is None:
                    raise ValueError("Untrusted reviewer")
                claims = jwt.decode(
                    token,
                    reviewer.secret.get_secret_value(),
                    algorithms=["HS256"],
                    audience="metadata:" + source_id,
                    issuer="nl2sql-metadata-review",
                    options={
                        "require": [
                            "sub",
                            "iat",
                            "exp",
                            "iss",
                            "aud",
                            "candidate_id",
                            "roles",
                            "reference",
                            "synthetic",
                        ],
                        "verify_exp": not published,
                    },
                )
                item = ApprovalEvidence.model_validate(
                    {
                        "reviewer": claims["sub"],
                        "roles": claims["roles"],
                        "candidate_id": claims["candidate_id"],
                        "reference": claims["reference"],
                        "synthetic": claims["synthetic"],
                    }
                )
                if (
                    item.reviewer != reviewer.id
                    or item.candidate_id != candidate_id
                    or not set(item.roles) <= set(reviewer.roles)
                    or item.synthetic != synthetic
                ):
                    raise ValueError("Approval scope mismatch")
                evidence.append(item)
            except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as error:
                raise Failure(
                    "APPROVAL_DENIED", "Approval evidence failed verification.", "denied"
                ) from error
        return tuple(evidence)

    def require_complete(
        self,
        tokens: tuple[str, ...],
        candidate_id: str,
        source_id: str,
        synthetic: bool,
        published: bool = False,
    ) -> tuple[ApprovalEvidence, ...]:
        """No physical discovery or model can stand in for three owner responsibilities."""
        evidence = self.verify(tokens, candidate_id, source_id, synthetic, published)
        if not ROLES <= {role for item in evidence for role in item.roles}:
            raise Failure(
                "APPROVAL_MISSING",
                "Physical, business and security approvals are required.",
                "conflict",
            )
        return evidence

    def sign_synthetic(self, reviewer_id: str, candidate_id: str, source_id: str) -> str:
        """Explicit local demo helper; production signing belongs to authorized reviewers."""
        reviewer = self.reviewers[reviewer_id]
        return jwt.encode(
            {
                "sub": reviewer.id,
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "iss": "nl2sql-metadata-review",
                "aud": "metadata:" + source_id,
                "candidate_id": candidate_id,
                "roles": reviewer.roles,
                "reference": "Explicit fictional local demonstration",
                "synthetic": True,
            },
            reviewer.secret.get_secret_value(),
            algorithm="HS256",
            headers={"kid": reviewer.id},
        )
