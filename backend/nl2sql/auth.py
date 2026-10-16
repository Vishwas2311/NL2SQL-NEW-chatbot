"""Validated bearer authentication with server-side, revocable entitlements."""

import hmac
from collections.abc import Callable
from threading import RLock

import jwt

from nl2sql.catalog import digest
from nl2sql.config import Settings
from nl2sql.domain import Failure, Principal


class Authenticator:
    """Opaque local tokens or issuer/audience/expiry-verified HS256 JWTs."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.principals = {principal.id: principal for principal in settings.principals}
        self.refresh_hook: Callable[[], None] | None = None
        self._lock = RLock()

    def replace_principals(self, principals: tuple[Principal, ...]) -> None:
        """Only verified runtime publication supplies this server-owned grant set."""
        with self._lock:
            self.principals = {principal.id: principal for principal in principals}

    def authenticate(self, authorization: str | None) -> Principal:
        """Never accept a principal, tenant or grant from the browser body."""
        if self.refresh_hook is not None:
            self.refresh_hook()
        if authorization is None or not authorization.startswith("Bearer "):
            raise Failure("UNAUTHENTICATED", "Valid authentication is required.", 401)
        token = authorization[7:]
        if not token or len(token) > 8192:
            raise Failure("UNAUTHENTICATED", "Valid authentication is required.", 401)
        token_hash = digest(token)
        principal_id: str | None = None
        for grant in self.settings.tokens:
            if hmac.compare_digest(grant.sha256, token_hash):
                principal_id = grant.principal_id
        if principal_id is None and self.settings.jwt_secret is not None:
            try:
                claims = jwt.decode(
                    token,
                    self.settings.jwt_secret.get_secret_value(),
                    algorithms=["HS256"],
                    issuer=self.settings.jwt_issuer,
                    audience=self.settings.jwt_audience,
                    options={"require": ["exp", "iat", "sub", "iss", "aud"]},
                )
                subject: object = claims.get("sub")
                if isinstance(subject, str):
                    principal_id = subject
            except jwt.InvalidTokenError as error:
                raise Failure(
                    "UNAUTHENTICATED", "Valid authentication is required.", 401
                ) from error
        principal = self.principals.get(principal_id or "")
        if principal is None:
            raise Failure("UNAUTHENTICATED", "Valid authentication is required.", 401)
        return principal
