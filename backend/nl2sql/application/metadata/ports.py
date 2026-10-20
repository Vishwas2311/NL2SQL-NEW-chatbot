"""Typed boundaries used by metadata lifecycle use cases."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Literal, Protocol

from nl2sql.domain.governance import AdminActor, ApprovalEvidence
from nl2sql.domain.metadata import BundleArtifacts, BundleSpec, MetadataControl, MetadataRecord
from nl2sql.domain.models import Catalog, Principal
from nl2sql.domain.physical import PhysicalInventory


class MetadataDiscoveryProvider(Protocol):
    """Oracle and offline providers return the same physical evidence contract."""

    def discover(self) -> PhysicalInventory:
        """Read allowlisted metadata under provider resource limits."""
        ...


class MetadataRepository(Protocol):
    """Publication and lease operations that must be transactional across workers."""

    def control(self) -> MetadataControl:
        """This small local read never polls Oracle on a chat request."""
        ...

    def get(self, version: str) -> MetadataRecord:
        """Recompute the immutable payload identity before any approval or recovery."""
        ...

    def latest(self) -> MetadataRecord | None:
        """Bound history is separate from candidate payloads and private metadata text."""
        ...

    def policy_version_conflict(
        self, version: str, fingerprint: str, active_revision: str | None = None
    ) -> bool:
        """A human revision label must never identify two different history-access policies."""
        ...

    def stage(self, spec: BundleSpec) -> MetadataRecord:
        """Commit a complete immutable candidate; active state is untouched."""
        ...

    def quarantine(self, views: tuple[str, ...]) -> None:
        """Known broken physical mappings block affected old bundles, including in-flight caps."""
        ...

    def set_approvals(
        self, version: str, approvals: tuple[str, ...], actor: str, complete: bool
    ) -> MetadataRecord:
        """Caller verifies identities; readers independently verify signatures again."""
        ...

    def activate(
        self, version: str, expected: MetadataControl, actor: str, rollback: bool = False
    ) -> MetadataControl:
        """One durable transaction is the publication linearization point."""
        ...

    def record_failure(self, code: str) -> None:
        """Never persist provider exception text or credentials."""
        ...

    def refresh_lease(
        self, seconds: int = 300, name: Literal["refresh", "schedule"] = "refresh"
    ) -> AbstractContextManager[None]:
        """A bounded cross-process lease prevents duplicate discovery loops and refresh jobs."""
        ...

    def claim_schedule(self, now: float) -> bool | None:
        """One atomic due-time claim prevents duplicate poll loops across local processes."""
        ...

    def configure_schedule(self, enabled: bool, interval: int, dry_run: bool, actor: str) -> None:
        """Persist an explicitly authorized external schedule."""
        ...

    def retire(self, version: str, actor: str, rejected: bool = False) -> None:
        """Retire or reject an inactive version under administrative authority."""
        ...


class ApprovalVerifier(Protocol):
    """Verify reviewer and administrator evidence without exposing signing keys."""

    def authenticate(self, token: str | None, action: str) -> AdminActor:
        """Verify configured authority independently of metadata content."""
        ...

    def verify(
        self,
        tokens: tuple[str, ...],
        candidate_id: str,
        source_id: str,
        synthetic: bool,
        published: bool = False,
    ) -> tuple[ApprovalEvidence, ...]:
        """Verify configured authority independently of metadata content."""
        ...

    def require_complete(
        self,
        tokens: tuple[str, ...],
        candidate_id: str,
        source_id: str,
        synthetic: bool,
        published: bool = False,
    ) -> tuple[ApprovalEvidence, ...]:
        """Verify configured authority independently of metadata content."""
        ...


class BundleBuilder(Protocol):
    """Build compatible runtime artifacts before a publication can activate."""

    @property
    def encoder_version(self) -> str | None:
        """Encoder identity included in artifact fingerprints."""
        ...

    def search_fingerprint(self, catalog: Catalog, principals: tuple[Principal, ...]) -> str:
        """Fingerprint approved search content and configuration."""
        ...

    def build(
        self,
        catalog: Catalog,
        inventory: PhysicalInventory,
        principals: tuple[Principal, ...],
        previous: BundleArtifacts | None = None,
    ) -> BundleArtifacts:
        """Build or reuse compatible artifacts, or reject the candidate."""
        ...
