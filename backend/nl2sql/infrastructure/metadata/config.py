"""Restricted source profiles and environment-supplied administrative trust anchors."""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, TypeAdapter

from nl2sql.application.metadata.ports import MetadataDiscoveryProvider
from nl2sql.domain.governance import Reviewer
from nl2sql.domain.models import Failure, FrozenModel
from nl2sql.infrastructure.metadata.discovery import FileDiscovery, SyntheticDiscovery
from nl2sql.infrastructure.metadata.governance import ApprovalAuthority


class ReviewerReference(FrozenModel):
    """Only configured environment references nominate trust anchors."""

    id: str
    roles: tuple[Literal["physical", "business", "security"], ...]
    key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,100}$")


class SourceProfile(FrozenModel):
    """No connection password or model credential is stored in a metadata profile."""

    source: Literal["synthetic", "file", "oracle"]
    source_id: str
    database_path: Path | None = None
    inventory_path: Path | None = None
    settings_path: Path | None = None

    def provider(self) -> MetadataDiscoveryProvider:
        """Oracle is primary in office; offline adapters retain the same evidence contract."""
        if self.source == "oracle":
            from nl2sql.infrastructure.metadata.oracle_discovery import (  # pylint: disable=import-outside-toplevel
                OracleDiscovery,
                OracleDiscoverySettings,
            )

            return OracleDiscovery(OracleDiscoverySettings(source_id=self.source_id))
        if self.source == "file" and self.inventory_path is not None:
            return FileDiscovery(self.inventory_path)
        if self.source == "synthetic" and self.database_path is not None:
            return SyntheticDiscovery(self.database_path, self.source_id)
        raise Failure(
            "SOURCE_CONFIGURATION", "The metadata source profile is incomplete.", "unavailable"
        )


def load_profile(root: Path) -> SourceProfile:
    """Profiles live under the private repository, never in the portable source catalog."""
    path = root / "source-profile.json"
    if path.stat().st_size > 64_000:
        raise ValueError("Metadata source profile exceeds its budget")
    return SourceProfile.model_validate_json(path.read_text(encoding="utf-8"))


def authority_from_environment() -> ApprovalAuthority | None:
    """File holders cannot nominate their own reviewer or key through an approval manifest."""
    key = os.environ.get("NL2SQL_METADATA_ADMIN_KEY")
    if not key:
        return None
    references = TypeAdapter(tuple[ReviewerReference, ...]).validate_json(
        os.environ.get("NL2SQL_METADATA_REVIEWERS", "[]")
    )
    reviewers: list[Reviewer] = []
    for item in references:
        secret = os.environ.get(item.key_env)
        if secret is None:
            raise Failure(
                "ADMIN_CONFIGURATION", "A configured reviewer secret is unavailable.", "denied"
            )
        reviewers.append(Reviewer(id=item.id, roles=item.roles, secret=SecretStr(secret)))
    return ApprovalAuthority(SecretStr(key), tuple(reviewers))
