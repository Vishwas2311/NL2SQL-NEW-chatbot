"""Validated configuration; no default passwords or browser demo-token trust."""

import json
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from nl2sql.domain import FrozenModel, Principal


class TokenGrant(FrozenModel):
    """Only token hashes are stored; grants are resolved on every request."""

    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    principal_id: str


class RetrievalOptions(FrozenModel):
    """Bounded runtime retrieval budgets shared with signed bundle construction."""

    top_k: int = Field(default=10, ge=1, le=50)
    max_candidates: int = Field(default=20, ge=1, le=100)
    rrf_constant: int = Field(default=60, ge=1, le=1000)


class Settings(BaseSettings):
    """Local budgets are provisional; enterprise policy must approve production values."""

    model_config = SettingsConfigDict(env_prefix="NL2SQL_", env_file=None, extra="forbid")
    data_dir: Path = Path(".local")
    catalog_path: Path = Path("metadata/synthetic/catalog.json")
    catalog_digest: str = ""
    metadata_root: Path | None = None
    query_backend: Literal["sqlite", "oracle"] = "sqlite"
    principals: tuple[Principal, ...] = ()
    tokens: tuple[TokenGrant, ...] = ()
    jwt_secret: SecretStr | None = None
    jwt_issuer: str = "ews-local"
    jwt_audience: str = "ews-backend"
    max_rows: int = Field(default=1000, ge=1, le=1000)
    max_metrics: int = Field(default=5, ge=1, le=5)
    max_dimensions: int = Field(default=5, ge=1, le=5)
    max_join_edges: int = Field(default=6, ge=0, le=6)
    max_result_bytes: int = Field(default=1_000_000, ge=1000, le=10_000_000)
    query_timeout_seconds: float = Field(default=3, gt=0, le=30)
    request_timeout_seconds: float = Field(default=15, gt=0, le=120)
    pool_size: int = Field(default=4, ge=1, le=16)
    model_mode: str = "disabled"
    model_endpoint: str | None = None
    approved_model_hosts: tuple[str, ...] = ()
    model_name: str = "gemma-4-12b"
    model_key: SecretStr | None = None
    model_timeout_seconds: float = Field(default=8, gt=0, le=60)
    model_retries: int = Field(default=0, ge=0, le=1)
    model_max_tokens: int = Field(default=1200, ge=100, le=4000)
    model_output_mode: Literal["json_schema", "json_object", "text_json"] = "json_schema"
    model_context_bytes: int = Field(default=64_000, ge=16_000, le=256_000)
    model_ca_bundle: Path | None = None
    public_model_authorized: bool = False
    data_classification: Literal["synthetic", "restricted"] = "restricted"
    scripted_plans: dict[str, str] = Field(default_factory=dict)
    embedding_mode: Literal["disabled", "fake", "local", "private_http"] = "disabled"
    embedding_model: str = "disabled"
    embedding_version: str = "disabled"
    embedding_dimension: int = Field(default=32, ge=1, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    embedding_timeout_seconds: float = Field(default=5, gt=0, le=60)
    embedding_normalization: Literal["l2", "none"] = "l2"
    embedding_cache_entries: int = Field(default=2048, ge=0, le=100_000)
    embedding_endpoint: str | None = None
    approved_embedding_hosts: tuple[str, ...] = ()
    embedding_key: SecretStr | None = None
    embedding_local_path: Path | None = None
    index_storage_path: Path | None = None
    retrieval_top_k: int = Field(default=10, ge=1, le=50)
    retrieval_max_candidates: int = Field(default=20, ge=1, le=100)
    retrieval_rrf_constant: int = Field(default=60, ge=1, le=1000)
    metadata_startup_reconcile: bool = False
    requests_per_minute: int = Field(default=60, ge=1, le=600)
    session_retention_days: int = Field(default=30, ge=1, le=365)

    @property
    def retrieval_options(self) -> RetrievalOptions:
        """Flattened environment keys retain one typed set of search budgets."""
        return RetrievalOptions(
            top_k=self.retrieval_top_k,
            max_candidates=self.retrieval_max_candidates,
            rrf_constant=self.retrieval_rrf_constant,
        )

    @model_validator(mode="after")
    def check_configuration(self) -> "Settings":
        """Prevent accidental insecure or partially configured startup modes."""
        ids = [principal.id for principal in self.principals]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate principal ID")
        if any(grant.principal_id not in ids for grant in self.tokens):
            raise ValueError("Token references an unknown principal")
        if len({grant.sha256 for grant in self.tokens}) != len(self.tokens):
            raise ValueError("Duplicate bearer token")
        if self.jwt_secret is not None and len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("JWT signing secret must contain at least 32 characters")
        if self.model_mode == "hosted_http" and (
            not self.public_model_authorized or self.data_classification != "synthetic"
        ):
            raise ValueError(
                "Hosted inference requires explicit synthetic data egress authorization"
            )
        if self.retrieval_top_k > self.retrieval_max_candidates:
            raise ValueError("Retrieval top K exceeds its candidate budget")
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Explicit process environment wins; no implicit dotenv or secret directory search."""
        return env_settings, dotenv_settings, init_settings, file_secret_settings


def load_settings(path: Path | None = None, env_file: Path | None = None) -> Settings:
    """Environment > explicitly selected dotenv > JSON > validated defaults."""
    values: object = json.loads(path.read_text(encoding="utf-8-sig")) if path else {}
    if not isinstance(values, dict):
        raise ValueError("Settings must be a JSON object")
    return Settings.model_validate(
        {
            **values,
            **DotEnvSettingsSource(Settings, env_file=env_file)(),
            **EnvSettingsSource(Settings)(),
        }
    )
