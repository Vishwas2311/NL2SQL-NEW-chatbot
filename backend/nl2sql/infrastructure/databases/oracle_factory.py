"""Approved query-account configuration is separate from metadata-discovery credentials."""

import json

import oracledb
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from nl2sql.application.query.security import SQLValidator
from nl2sql.domain.models import Failure, Principal
from nl2sql.infrastructure.databases.oracle import OracleAdapter, OracleConfig, OracleConnection

PROCEDURE = r"^[A-Za-z][A-Za-z0-9_$#]*(?:\.[A-Za-z][A-Za-z0-9_$#]*){1,2}$"


class OracleExecutionSettings(BaseSettings):
    """Secrets are supplied through the approved environment/secret manager, never CLI args."""

    model_config = SettingsConfigDict(env_prefix="NL2SQL_QUERY_", env_file=None, extra="forbid")
    approved_environment: bool = False
    owner_authorized: bool = False
    network_authorized: bool = False
    readonly_grants_verified: bool = False
    context_procedures_verified: bool = False
    dsn: SecretStr | None = None
    user: SecretStr | None = None
    password: SecretStr | None = None
    apply_procedure: str | None = Field(default=None, pattern=PROCEDURE)
    reset_procedure: str | None = Field(default=None, pattern=PROCEDURE)
    pool_max: int = Field(default=4, ge=1, le=16)
    timeout_ms: int = Field(default=3000, ge=1, le=30_000)
    max_result_bytes: int = Field(default=1_000_000, ge=1000, le=10_000_000)


class DBAContextPolicy:
    """DBA owns grants, VPD and these procedures; Python supplies signed server identity."""

    def __init__(self, apply_procedure: str, reset_procedure: str) -> None:
        # Validate even when constructed outside BaseSettings.
        checked = OracleExecutionSettings(
            apply_procedure=apply_procedure, reset_procedure=reset_procedure
        )
        self.apply_procedure = checked.apply_procedure
        self.reset_procedure = checked.reset_procedure

    def apply(self, connection: OracleConnection, principal: Principal) -> None:
        """Bind trusted identity into the DBA-approved application context."""
        assert self.apply_procedure is not None
        with connection.cursor() as cursor:
            cursor.callproc(
                self.apply_procedure,
                [
                    principal.id,
                    principal.tenant,
                    json.dumps(
                        {
                            "regions": principal.regions,
                            "scopes": principal.scopes,
                            "policy_version": principal.policy_version,
                        }
                    ),
                ],
            )

    def reset(self, connection: OracleConnection) -> None:
        """Clear pooled identity before releasing this session."""
        assert self.reset_procedure is not None
        with connection.cursor() as cursor:
            cursor.callproc(self.reset_procedure)


def oracle_executor(
    validator: SQLValidator, settings: OracleExecutionSettings | None = None
) -> OracleAdapter:
    """Flags record outside approvals; no connection can precede their explicit configuration."""
    settings = settings or OracleExecutionSettings()
    if not all(
        (
            settings.approved_environment,
            settings.owner_authorized,
            settings.network_authorized,
            settings.readonly_grants_verified,
            settings.context_procedures_verified,
        )
    ):
        raise Failure(
            "ORACLE_QUERY_NOT_APPROVED",
            "Oracle query access and DBA context/grants require approval.",
            403,
        )
    if any(
        value is None
        for value in (
            settings.dsn,
            settings.user,
            settings.password,
            settings.apply_procedure,
            settings.reset_procedure,
        )
    ):
        raise Failure(
            "ORACLE_CONFIGURATION", "Approved Oracle query configuration is incomplete.", 503
        )
    assert settings.dsn is not None and settings.user is not None and settings.password is not None
    assert settings.apply_procedure is not None and settings.reset_procedure is not None
    config = OracleConfig(
        dsn=settings.dsn.get_secret_value(),
        user=settings.user.get_secret_value(),
        password=settings.password.get_secret_value(),
        approved_test_environment=True,
        pool_max=settings.pool_max,
        timeout_ms=settings.timeout_ms,
        max_result_bytes=settings.max_result_bytes,
    )
    try:
        return OracleAdapter(
            config, validator, DBAContextPolicy(settings.apply_procedure, settings.reset_procedure)
        )
    except oracledb.Error as error:
        raise Failure(
            "ORACLE_UNAVAILABLE", "The approved query pool is unavailable.", 503
        ) from error
