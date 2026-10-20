"""One governed bootstrap/sync/publish/rollback use case for all metadata providers."""

import time
from collections.abc import Callable

from nl2sql.application.metadata.certification import reconcile
from nl2sql.application.metadata.drift import (
    analyze_impact,
    policy_digest,
    schema_changes,
    semantic_changes,
)
from nl2sql.application.metadata.ports import (
    ApprovalVerifier,
    BundleBuilder,
    MetadataDiscoveryProvider,
    MetadataRepository,
)
from nl2sql.domain.fingerprints import catalog_hash, grant_digest
from nl2sql.domain.metadata import BundleSpec, MetadataRecord
from nl2sql.domain.models import Catalog, Failure, FrozenModel, Principal
from nl2sql.domain.physical import inventory_digest


class StageOutcome(FrozenModel):
    """Opaque candidate references are safe to print; detailed inventories remain private."""

    candidate_id: str | None
    state: str
    dry_run: bool
    no_change: bool
    object_count: int
    change_count: int
    affected_views: tuple[str, ...]
    issues: tuple[str, ...]
    build_ms: float


class MetadataWorkflow:
    """Publication never trusts a catalog's imported approved boolean as authority."""

    def __init__(
        self,
        repository: MetadataRepository,
        provider: MetadataDiscoveryProvider,
        authority: ApprovalVerifier | None = None,
        *,
        builder: BundleBuilder,
        runtime_check: Callable[[BundleSpec], None] | None = None,
    ) -> None:
        self.repository = repository
        self.provider = provider
        self.authority = authority
        self.builder = builder
        self.runtime_check = runtime_check

    def stage(
        self,
        catalog: Catalog | None = None,
        principals: tuple[Principal, ...] | None = None,
        dry_run: bool = False,
    ) -> StageOutcome:
        """One operation: discover, compare, impact, reconcile, build and stage; never approve."""
        if dry_run:
            return self._stage(catalog, principals, True)
        with self.repository.refresh_lease():
            return self._stage(catalog, principals, dry_run)

    def _stage(
        self, catalog: Catalog | None, principals: tuple[Principal, ...] | None, dry_run: bool
    ) -> StageOutcome:
        started = time.perf_counter()
        try:
            inventory = self.provider.discover()
            control = self.repository.control()
            active = self.repository.get(control.active) if control.active else None
            previous = active or self.repository.latest()
            if previous is not None and previous.spec.inventory.source_id != inventory.source_id:
                raise Failure(
                    "SOURCE_MISMATCH",
                    "A metadata store cannot silently switch database identity.",
                    409,
                )
            if catalog is None and previous is not None:
                catalog = previous.spec.catalog
            if principals is None:
                principals = previous.spec.principals if previous else ()
            latest = self.repository.latest()
            reusable = next(
                (
                    item
                    for item in (previous, latest)
                    if item is not None
                    and item.state not in {"rejected", "retired"}
                    and control.active in {item.spec.id, item.spec.base_version}
                    and (not control.blocked_views or item.spec.id != control.active)
                    and _unchanged(
                        item.spec,
                        inventory_digest(inventory),
                        catalog,
                        principals,
                        self.builder.encoder_version,
                    )
                    and (
                        item.spec.artifacts is None
                        or catalog is None
                        or item.spec.artifacts.search_digest
                        == self.builder.search_fingerprint(catalog, principals)
                    )
                    and (not item.spec.issues or item.spec.catalog is None)
                ),
                None,
            )
            if reusable is not None:
                return StageOutcome(
                    candidate_id=reusable.spec.id,
                    state=reusable.state,
                    dry_run=dry_run,
                    no_change=True,
                    object_count=len(inventory.objects),
                    change_count=0,
                    affected_views=(),
                    issues=reusable.spec.issues,
                    build_ms=(time.perf_counter() - started) * 1000,
                )
            changes = (
                *schema_changes(previous.spec.inventory if previous else None, inventory),
                *semantic_changes(
                    previous.spec.catalog if previous else None,
                    catalog,
                    previous.spec.principals if previous else (),
                    principals,
                ),
            )
            impact = analyze_impact(
                changes,
                previous.spec.catalog if previous else catalog,
                previous.spec.inventory if previous else inventory,
            )
            if active is not None and not dry_run:
                # Observed physical failures quarantine active mappings.
                physical = analyze_impact(
                    schema_changes(active.spec.inventory, inventory),
                    active.spec.catalog,
                    active.spec.inventory,
                )
                self.repository.quarantine(physical.blocked_views)
            issues = (
                list(reconcile(catalog, inventory).issues)
                if catalog is not None
                else ["business_semantics_required", "security_mapping_required"]
            )
            artifacts = None
            if catalog is not None and self.repository.policy_version_conflict(
                catalog.policy_version,
                policy_digest(catalog),
                active.spec.catalog.policy_version
                if active is not None and active.spec.catalog is not None
                else None,
            ):
                issues.append("policy_version_change_required")
            if catalog is not None and not issues:
                try:
                    artifacts = self.builder.build(
                        catalog,
                        inventory,
                        principals,
                        previous.spec.artifacts if previous else None,
                    )
                except (Failure, ValueError) as error:
                    issues.append(
                        "bundle_build_failed:"
                        + (error.code if isinstance(error, Failure) else type(error).__name__)
                    )
            spec = BundleSpec(
                inventory=inventory,
                base_version=control.active,
                catalog=catalog,
                principals=principals,
                artifacts=artifacts,
                impact=impact,
                issues=tuple(issues),
            )
            state = "pending_verification" if spec.issues else "pending_approval"
            if not dry_run:
                state = self.repository.stage(spec).state
            return StageOutcome(
                candidate_id=spec.id,
                state=state,
                dry_run=dry_run,
                no_change=False,
                object_count=len(inventory.objects),
                change_count=len(changes),
                affected_views=impact.views,
                issues=spec.issues,
                build_ms=(time.perf_counter() - started) * 1000,
            )
        except (Failure, ValueError, OSError) as error:
            if not dry_run:
                self.repository.record_failure(
                    error.code if isinstance(error, Failure) else type(error).__name__
                )
            raise

    def approve(
        self, candidate: str, tokens: tuple[str, ...], admin_token: str | None
    ) -> MetadataRecord:
        """Both administrator and reviewer authority are required."""
        authority = self._authority()
        actor = authority.authenticate(admin_token, "approve")
        record = self.repository.get(candidate)
        if record.spec.issues or record.spec.catalog is None or record.spec.artifacts is None:
            raise Failure(
                "CANDIDATE_INVALID", "Resolve the candidate validation issues before approval.", 409
            )
        evidence = authority.verify(
            tokens,
            candidate,
            record.spec.inventory.source_id,
            record.spec.inventory.classification == "synthetic",
        )
        roles = {role for item in evidence for role in item.roles}
        return self.repository.set_approvals(
            candidate, tokens, actor.id, {"physical", "business", "security"} <= roles
        )

    def publish(self, candidate: str, admin_token: str | None) -> str:
        """Prepare complete resources off the active path, then CAS one durable pointer."""
        authority = self._authority()
        actor = authority.authenticate(admin_token, "publish")
        with self.repository.refresh_lease():
            expected = self.repository.control()
            record = self.repository.get(candidate)
            if record.spec.base_version != expected.active:
                raise Failure(
                    "CANDIDATE_STALE",
                    "Restage and review this candidate against the current publication.",
                    409,
                )
            self.verify_record(record, published=False)
            current = self.provider.discover()
            if inventory_digest(current) != inventory_digest(record.spec.inventory):
                raise Failure(
                    "SOURCE_CHANGED", "Rediscover and review the changed physical inventory.", 409
                )
            if self.runtime_check is None:
                raise Failure(
                    "RUNTIME_CHECK_REQUIRED",
                    "A complete runtime validation is required before publication.",
                    409,
                )
            self.runtime_check(record.spec)
            if inventory_digest(self.provider.discover()) != inventory_digest(current):
                raise Failure(
                    "SOURCE_CHANGED", "The physical schema changed during publication.", 409
                )
            self.repository.activate(candidate, expected, actor.id)
        return candidate

    def rollback(self, target: str, admin_token: str | None) -> str:
        """An old catalog may return; an older grant or policy snapshot may not."""
        authority = self._authority()
        actor = authority.authenticate(admin_token, "rollback")
        with self.repository.refresh_lease():
            expected = self.repository.control()
            if expected.active is None:
                raise Failure("NO_ACTIVE_METADATA", "There is no active metadata version.", 409)
            current = self.repository.get(expected.active)
            old = self.repository.get(target)
            if old.state not in {"published", "superseded"}:
                raise Failure(
                    "ROLLBACK_DENIED", "Only previously published metadata can be restored.", 409
                )
            self.verify_record(old, published=True)
            assert old.spec.catalog is not None and current.spec.catalog is not None
            if policy_digest(old.spec.catalog) != policy_digest(
                current.spec.catalog
            ) or grant_digest(old.spec.principals) != grant_digest(current.spec.principals):
                raise Failure(
                    "ROLLBACK_SECURITY",
                    "Rollback cannot restore older policies or grants; stage a reviewed revision.",
                    403,
                )
            live = self.provider.discover()
            if reconcile(old.spec.catalog, live).issues:
                raise Failure(
                    "ROLLBACK_INCOMPATIBLE",
                    "The rollback target is incompatible with the current physical schema.",
                    409,
                )
            if self.runtime_check is None:
                raise Failure(
                    "RUNTIME_CHECK_REQUIRED", "Runtime validation is required before rollback.", 409
                )
            self.runtime_check(old.spec)
            if inventory_digest(self.provider.discover()) != inventory_digest(live):
                raise Failure("SOURCE_CHANGED", "The physical schema changed during rollback.", 409)
            self.repository.activate(target, expected, actor.id, rollback=True)
        return target

    def verify_record(self, record: MetadataRecord, published: bool = True) -> None:
        """Recovery verifies signatures, source compatibility and all artifact fingerprints."""
        spec = record.spec
        if spec.catalog is None or spec.artifacts is None or spec.issues:
            raise Failure(
                "METADATA_INCOMPLETE", "A complete certified metadata bundle is required.", 503
            )
        self._authority().require_complete(
            record.approvals,
            spec.id,
            spec.inventory.source_id,
            spec.inventory.classification == "synthetic",
            published,
        )
        if reconcile(spec.catalog, spec.inventory).issues:
            raise Failure("METADATA_INTEGRITY", "Published metadata compatibility failed.", 503)
        artifacts = self.builder.build(
            spec.catalog, spec.inventory, spec.principals, spec.artifacts
        )
        expected = spec.artifacts
        if any(
            getattr(artifacts, key) != getattr(expected, key)
            for key in (
                "catalog_digest",
                "physical_digest",
                "graph_digest",
                "search_digest",
                "policy_digest",
                "compiler_digest",
                "encoder_version",
                "vector_digest",
            )
        ):
            raise Failure("METADATA_INTEGRITY", "Metadata artifact versions do not match.", 503)

    def _authority(self) -> ApprovalVerifier:
        if self.authority is None:
            raise Failure(
                "ADMIN_CONFIGURATION", "Administrative trust anchors have not been configured.", 403
            )
        return self.authority


def _unchanged(
    spec: BundleSpec,
    physical_digest: str,
    catalog: Catalog | None,
    principals: tuple[Principal, ...],
    encoder_version: str | None,
) -> bool:
    return (
        inventory_digest(spec.inventory) == physical_digest
        and (
            (spec.catalog is None and catalog is None)
            or (
                spec.catalog is not None
                and catalog is not None
                and catalog_hash(spec.catalog) == catalog_hash(catalog)
            )
        )
        and grant_digest(spec.principals) == grant_digest(principals)
        and (spec.artifacts is None or spec.artifacts.encoder_version == encoder_version)
    )
