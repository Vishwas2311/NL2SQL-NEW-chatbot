"""Immutable metadata lifecycle and change-impact contracts."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from nl2sql.domain.fingerprints import digest
from nl2sql.domain.models import Catalog, FrozenModel, Principal
from nl2sql.domain.physical import PhysicalInventory

Lifecycle = Literal[
    "discovered",
    "pending_verification",
    "verified_physical",
    "pending_approval",
    "certified",
    "published",
    "superseded",
    "retired",
    "rejected",
]

ChangeClass = Literal[
    "compatible_physical_addition",
    "metadata_only",
    "approval_required_addition",
    "breaking_physical",
    "breaking_semantic",
    "security_sensitive",
    "unknown",
]


class SchemaChange(FrozenModel):
    """Only IDs and change kinds need to appear in routine telemetry."""

    kind: str
    classification: ChangeClass
    object_id: str | None = None
    column: str | None = None
    semantic_id: str | None = None


class ChangeImpact(FrozenModel):
    """Affected mappings and review gates, not an automatic business-definition generator."""

    changes: tuple[SchemaChange, ...]
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    views: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    retrieval: tuple[str, ...] = ()
    compiler: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    saved_plans: tuple[str, ...] = ()
    blocked_views: tuple[str, ...] = ()
    revalidation: tuple[str, ...] = ()
    approval_required: bool = False


class BundleArtifacts(FrozenModel):
    """Derived structures are reproducible from the signed catalog and current implementation."""

    catalog_digest: str
    physical_digest: str
    graph_digest: str
    search_digest: str
    policy_digest: str
    compiler_digest: str
    encoder_version: str | None = None
    vector_digest: str | None = None
    build_ms: float = 0
    rebuilt: tuple[str, ...] = ()


class BundleSpec(FrozenModel):
    """Immutable candidate content; lifecycle status and review tokens are separate records."""

    inventory: PhysicalInventory
    base_version: str | None = None
    catalog: Catalog | None
    principals: tuple[Principal, ...] = Field(default=(), max_length=128)
    artifacts: BundleArtifacts | None = None
    impact: ChangeImpact
    issues: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def id(self) -> str:
        """Approvals bind every source, mapping, permission and derived-artifact reference."""
        return digest(self.model_dump_json())


class MetadataRecord(FrozenModel):
    """An arbitrary status/file can never stand in for signature verification."""

    spec: BundleSpec
    state: Lifecycle
    approvals: tuple[str, ...] = ()


class MetadataControl(FrozenModel):
    """Revision provides compare-and-swap coordination across processes sharing this store."""

    active: str | None
    revision: int
    blocked_views: tuple[str, ...]
