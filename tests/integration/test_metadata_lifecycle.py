"""Real synthetic data through discovery, signatures, atomic bundles and refresh."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import jwt
import pytest
from nl2sql.application.metadata.refresh import MetadataRefreshService
from nl2sql.application.metadata.workflow import MetadataWorkflow
from nl2sql.application.query.planning import principal_hash
from nl2sql.application.sessions import SessionService
from nl2sql.bootstrap.runtime import BundleChatService, RuntimeFactory, RuntimeManager
from nl2sql.domain.governance import Reviewer
from nl2sql.domain.models import Catalog, Failure
from nl2sql.infrastructure.auth import Authenticator
from nl2sql.infrastructure.inference.model import MockModel
from nl2sql.infrastructure.metadata.builder import BundleBuilder
from nl2sql.infrastructure.metadata.discovery import SyntheticDiscovery
from nl2sql.infrastructure.metadata.governance import ApprovalAuthority
from nl2sql.infrastructure.metadata.store import MetadataRepository
from nl2sql.infrastructure.sessions import SessionStore
from pydantic import SecretStr


class MetadataKit:
    def __init__(self, settings, root):
        self.settings = settings
        self.root = root
        self.repository = MetadataRepository(root)
        self.sessions = SessionStore(settings.data_dir / "sessions.db")
        self.model = MockModel({})
        self.factory = RuntimeFactory(settings, self.sessions, self.model)
        self.authority = ApprovalAuthority(
            SecretStr("a" * 48),
            tuple(
                Reviewer(id="test-" + role, roles=(role,), secret=SecretStr(role * 16))
                for role in ("physical", "business", "security")
            ),
        )
        self.admin = jwt.encode(
            {
                "sub": "synthetic-test-admin",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
                "iss": "nl2sql-metadata-admin",
                "aud": "nl2sql-metadata-admin",
                "actions": ["approve", "publish", "rollback", "schedule", "review", "retire"],
            },
            "a" * 48,
            algorithm="HS256",
        )
        self.catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
        self.workflow = MetadataWorkflow(
            self.repository,
            SyntheticDiscovery(settings.data_dir / "banking.db"),
            self.authority,
            builder=BundleBuilder(),
            runtime_check=self.factory.check,
        )
        self.manager = None

    def approvals(self, version):
        return tuple(
            self.authority.sign_synthetic(key, version, "synthetic-banking")
            for key in self.authority.reviewers
        )

    def publish(self, catalog=None, principals=None):
        outcome = self.workflow.stage(
            self.catalog if catalog is None else catalog,
            self.settings.principals if principals is None else principals,
        )
        assert not outcome.issues, outcome.issues
        self.workflow.approve(
            outcome.candidate_id, self.approvals(outcome.candidate_id), self.admin
        )
        self.workflow.publish(outcome.candidate_id, self.admin)
        return outcome.candidate_id

    def start(self):
        self.manager = RuntimeManager(self.workflow, self.factory)
        return BundleChatService(self.manager)

    def query(self, service, principal=None):
        return service.chat(
            "Show total loan exposure by region",
            None,
            principal or self.settings.principals[0],
            None,
            {},
        )

    def close(self):
        if self.manager is not None:
            self.manager.close()
        self.model.close()
        self.sessions.close()
        self.repository.close()


@pytest.fixture
def kit(settings, tmp_path):
    active = MetadataKit(settings, tmp_path / "private-metadata")
    yield active
    active.close()


def test_history_response_rechecks_governed_publication_after_read(kit, monkeypatch):
    kit.publish()
    answer = kit.query(kit.start())
    identity = Authenticator(kit.settings)
    kit.manager.on_activate = identity.replace_principals
    identity.refresh_hook = kit.manager.reload
    service = SessionService(kit.sessions, identity)
    principal = kit.settings.principals[0]
    original = kit.sessions.messages
    observed = []

    def read_then_publish(*args, **kwargs):
        saved = original(*args, **kwargs)
        observed.extend(saved)
        grants = tuple(
            user.model_copy(
                update={"metrics": tuple(key for key in user.metrics if key != "loan_exposure")}
            )
            for user in kit.settings.principals
        )
        kit.publish(principals=grants)
        return saved

    monkeypatch.setattr(kit.sessions, "messages", read_then_publish)
    with pytest.raises(Failure) as denied:
        service.messages(answer.session_id, principal)
    assert any(message.results for message in observed)
    assert denied.value.code == "DENIED"


def test_first_bootstrap_approval_and_actual_query(kit):
    staged = kit.workflow.stage(kit.catalog, kit.settings.principals)
    assert staged.state == "pending_approval" and not staged.issues
    assert kit.repository.control().active is None
    with pytest.raises(Failure, match="approvals"):
        kit.workflow.publish(staged.candidate_id, kit.admin)
    kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), kit.admin)
    kit.workflow.publish(staged.candidate_id, kit.admin)
    answer = kit.query(kit.start())
    assert answer.rows == (
        {"region": "Demo North", "loan_exposure": "175000.50"},
        {"region": "Demo South", "loan_exposure": "75000.00"},
    )
    assert answer.provenance.bundle_version == staged.candidate_id


@pytest.mark.parametrize(
    "change", ["type", "precision", "nullable", "removed_column", "composite_key"]
)
def test_breaking_physical_contracts_quarantine_only_dependent_reports(kit, change):
    active = kit.publish()
    service = kit.start()
    original = kit.workflow.provider.discover()
    loans = next(item for item in original.objects if item.name == "loans")
    if change == "composite_key":
        keys = tuple(
            key.model_copy(update={"columns": key.columns[1:]}) if key.kind == "primary" else key
            for key in loans.keys
        )
        replacement = loans.model_copy(update={"keys": keys})
    else:
        columns = []
        for column in loans.columns:
            if column.name == "amount_minor":
                if change == "removed_column":
                    continue
                column = column.model_copy(
                    update={"data_type": "TEXT"}
                    if change == "type"
                    else {"precision": 12}
                    if change == "precision"
                    else {"nullable": not column.nullable}
                )
            columns.append(column)
        replacement = loans.model_copy(update={"columns": tuple(columns)})
    changed = original.model_copy(
        update={
            "objects": tuple(
                replacement if item.id == loans.id else item for item in original.objects
            )
        }
    )

    class Changed:
        def discover(self):
            return changed

    kit.workflow.provider = Changed()
    outcome = kit.workflow.stage()
    assert outcome.change_count > 0
    assert kit.repository.control().active == active
    assert "loan_snapshot" in kit.repository.control().blocked_views
    assert "account_current" not in kit.repository.control().blocked_views
    with pytest.raises(Failure, match="blocked"):
        kit.query(service)


def test_new_table_and_verified_fk_remain_unmapped_and_ungranted(kit):
    active = kit.publish()
    with closing(sqlite3.connect(kit.settings.data_dir / "banking.db")) as conn, conn:
        conn.execute(
            "CREATE TABLE discovered_only(tenant_id TEXT, id TEXT, customer_id TEXT, PRIMARY KEY(tenant_id,id), FOREIGN KEY(tenant_id,customer_id) REFERENCES customers(tenant_id,customer_id))"
        )
    outcome = kit.workflow.stage()
    record = kit.repository.get(outcome.candidate_id)
    physical = next(
        item for item in record.spec.inventory.objects if item.name == "discovered_only"
    )
    assert any(key.kind == "foreign" for key in physical.keys)
    assert physical.name not in {table.id for table in record.spec.catalog.tables}
    assert record.spec.principals == kit.settings.principals
    assert kit.repository.control().active == active
    assert not record.spec.artifacts.rebuilt
    repeated = kit.workflow.stage()
    assert repeated.no_change and repeated.candidate_id == outcome.candidate_id


def test_synonym_and_semantic_view_changes_require_review_and_rebuild(kit):
    active = kit.publish()
    metrics = tuple(
        metric.model_copy(update={"aliases": (*metric.aliases, "fictional new synonym")})
        if metric.id == "loan_exposure"
        else metric
        for metric in kit.catalog.metrics
    )
    views = tuple(
        view.model_copy(update={"evidence": view.evidence + " Reviewed wording"})
        if view.id == "loan_snapshot"
        else view
        for view in kit.catalog.views
    )
    changed = kit.catalog.model_copy(update={"metrics": metrics, "views": views})
    outcome = kit.workflow.stage(changed)
    assert kit.repository.control().active == active
    assert "loan_snapshot" in outcome.affected_views
    assert "bm25" in kit.repository.get(outcome.candidate_id).spec.artifacts.rebuilt
    with pytest.raises(Failure):
        kit.workflow.publish(outcome.candidate_id, kit.admin)
    kit.workflow.approve(outcome.candidate_id, kit.approvals(outcome.candidate_id), kit.admin)
    kit.workflow.publish(outcome.candidate_id, kit.admin)
    service = kit.start()
    with kit.manager.pin() as bundle:
        found = bundle.retriever.retrieve("fictional new synonym", kit.settings.principals[0])
        assert found[0].metric_id == "loan_exposure"
    assert kit.query(service).rows[0]["loan_exposure"] == "175000.50"


@pytest.mark.parametrize("component", ["JoinGraph", "Retriever"])
def test_failed_graph_or_index_build_preserves_working_bundle(kit, monkeypatch, component):
    active = kit.publish()
    service = kit.start()

    def fail(*_args):
        raise ValueError("confidential provider explanation")

    monkeypatch.setattr("nl2sql.infrastructure.metadata.builder." + component, fail)
    changed = kit.catalog.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"definition": metric.definition + " reviewed"})
                for metric in kit.catalog.metrics
            )
        }
    )
    outcome = kit.workflow.stage(changed)
    assert "bundle_build_failed:ValueError" in outcome.issues
    assert "confidential" not in str(kit.repository.history())
    assert kit.repository.control().active == active
    assert kit.query(service).rows[0]["loan_exposure"] == "175000.50"


def test_grant_revocation_during_actual_execution_discards_response(kit, monkeypatch):
    kit.publish()
    service = kit.start()
    with kit.manager.pin() as bundle:
        original = bundle.database.execute

        def execute_then_revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            restricted = tuple(
                user.model_copy(
                    update={"metrics": tuple(key for key in user.metrics if key != "loan_exposure")}
                )
                for user in kit.settings.principals
            )
            kit.publish(principals=restricted)
            kit.manager.reload()
            return result

        monkeypatch.setattr(bundle.database, "execute", execute_then_revoke)
        with pytest.raises(Failure) as error:
            kit.query(service)
        assert error.value.code == "DENIED"


def test_scheduler_disabled_due_claim_retry_and_safe_failure(kit, monkeypatch):
    kit.publish()
    waits = []
    refresh = MetadataRefreshService(kit.workflow, clock=lambda: 1000, wait=waits.append)
    assert not refresh.tick().ran
    kit.repository.configure_schedule(True, 5, True, "test-admin")
    assert refresh.tick().outcome.no_change
    with closing(MetadataRepository(kit.root)) as other:
        assert other.claim_schedule(1001) is None
    kit.repository.configure_schedule(True, 5, True, "test-admin")

    def fail():
        raise Failure("DISCOVERY_UNAVAILABLE", "private endpoint and secret", 503)

    monkeypatch.setattr(kit.workflow.provider, "discover", fail)
    failed = refresh.tick()
    assert failed.error_code == "DISCOVERY_UNAVAILABLE" and failed.attempts == 2
    assert waits == [1]
    assert "private endpoint" not in str(kit.repository.history())
    assert kit.repository.control().active is not None


def test_stale_publication_and_expired_refresh_worker_cannot_activate(kit, monkeypatch):
    active = kit.publish()
    expected = kit.repository.control()
    with kit.repository.refresh_lease():
        kit.repository.quarantine(("account_current",))
        with pytest.raises(Failure, match="changed"):
            kit.repository.activate(active, expected, "test-admin", rollback=True)
    monkeypatch.setattr("nl2sql.infrastructure.metadata.store.time.time", lambda: 0)
    with kit.repository.refresh_lease(1):
        monkeypatch.setattr("nl2sql.infrastructure.metadata.store.time.time", lambda: 2)
        with pytest.raises(Failure):
            kit.repository.activate(active, kit.repository.control(), "test-admin")
    assert kit.repository.control().active == active


def test_physical_inventory_without_business_certification_stays_pending(kit):
    staged = kit.workflow.stage()
    assert "business_semantics_required" in staged.issues
    record = kit.repository.get(staged.candidate_id)
    assert record.spec.inventory.objects and record.spec.catalog is None
    with pytest.raises(Failure):
        kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), kit.admin)
    assert kit.repository.control().active is None


def test_forged_approval_admin_and_candidate_substitution_fail(kit):
    staged = kit.workflow.stage(kit.catalog, kit.settings.principals)
    with pytest.raises(Failure) as error:
        kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), "forged")
    assert error.value.code == "ADMIN_DENIED"
    forged = jwt.encode(
        {"candidate_id": staged.candidate_id, "roles": ["physical", "business", "security"]},
        "wrong-key" * 8,
        algorithm="HS256",
        headers={"kid": "test-physical"},
    )
    with pytest.raises(Failure) as error:
        kit.workflow.approve(staged.candidate_id, (forged,), kit.admin)
    assert error.value.code == "APPROVAL_DENIED"
    with pytest.raises(Failure):
        kit.workflow.approve(staged.candidate_id, kit.approvals("0" * 64), kit.admin)
    assert kit.repository.control().active is None


def test_breaking_metric_mapping_and_ambiguous_graph_cannot_certify(kit):
    active = kit.publish()
    broken = kit.catalog.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"column": "unknown_amount"})
                if metric.id == "loan_exposure"
                else metric
                for metric in kit.catalog.metrics
            )
        }
    )
    failed = kit.workflow.stage(broken)
    assert failed.state == "pending_verification"
    with pytest.raises(Failure):
        kit.workflow.approve(failed.candidate_id, kit.approvals(failed.candidate_id), kit.admin)
    edges = (
        *kit.catalog.relations,
        kit.catalog.relations[0].model_copy(update={"id": "duplicate_route"}),
    )
    views = tuple(
        view.model_copy(update={"relationships": (*view.relationships, "duplicate_route")})
        if kit.catalog.relations[0].id in view.relationships
        else view
        for view in kit.catalog.views
    )
    ambiguous = kit.workflow.stage(
        kit.catalog.model_copy(update={"relations": edges, "views": views})
    )
    assert ambiguous.state == "pending_verification"
    assert kit.repository.control().active == active


def test_restored_physical_source_requires_reviewed_candidate_to_clear_quarantine(kit):
    active = kit.publish()
    original = kit.workflow.provider.discover()

    class MutableSource:
        inventory = original.model_copy(
            update={"objects": tuple(item for item in original.objects if item.name != "accounts")}
        )

        def discover(self):
            return self.inventory

    source = MutableSource()
    kit.workflow.provider = source
    assert kit.workflow.stage().issues
    assert "account_current" in kit.repository.control().blocked_views
    source.inventory = original
    restored = kit.workflow.stage()
    assert not restored.no_change and restored.candidate_id != active and not restored.issues
    kit.workflow.approve(restored.candidate_id, kit.approvals(restored.candidate_id), kit.admin)
    kit.workflow.publish(restored.candidate_id, kit.admin)
    assert not kit.repository.control().blocked_views


def test_old_approved_candidate_cannot_replace_newer_revocations(kit):
    first = kit.publish()
    changed = kit.catalog.model_copy(
        update={
            "metrics": tuple(
                metric.model_copy(update={"aliases": (*metric.aliases, "older approved candidate")})
                if metric.id == "loan_exposure"
                else metric
                for metric in kit.catalog.metrics
            )
        }
    )
    stale = kit.workflow.stage(changed)
    kit.workflow.approve(stale.candidate_id, kit.approvals(stale.candidate_id), kit.admin)
    assert kit.repository.get(stale.candidate_id).spec.base_version == first
    revoked = tuple(
        user.model_copy(
            update={"metrics": tuple(key for key in user.metrics if key != "loan_exposure")}
        )
        for user in kit.settings.principals
    )
    current = kit.publish(principals=revoked)
    with pytest.raises(Failure) as error:
        kit.workflow.publish(stale.candidate_id, kit.admin)
    assert error.value.code == "CANDIDATE_STALE"
    assert kit.repository.control().active == current
    restaged = kit.workflow.stage(changed, kit.settings.principals)
    assert restaged.candidate_id != stale.candidate_id and not restaged.no_change
    assert kit.repository.get(restaged.candidate_id).spec.base_version == current


def test_changed_security_policy_requires_fresh_revision_and_redacts_history(kit):
    kit.publish()
    answer = kit.query(kit.start())
    user = kit.settings.principals[0]
    views = tuple(
        view.model_copy(update={"mandatory_status": "closed"})
        if view.id == "loan_snapshot"
        else view
        for view in kit.catalog.views
    )
    changed = kit.catalog.model_copy(update={"views": views})
    refused = kit.workflow.stage(changed)
    assert "policy_version_change_required" in refused.issues
    changed = changed.model_copy(update={"policy_version": "synthetic-policy-v2"})
    mismatch = kit.workflow.stage(changed)
    assert "bundle_build_failed:POLICY_VERSION" in mismatch.issues
    grants = tuple(
        item.model_copy(update={"policy_version": "synthetic-policy-v2"})
        for item in kit.settings.principals
    )
    kit.publish(changed, grants)
    kit.manager.reload()
    assert kit.sessions.messages(answer.session_id, user.id, principal_hash(user))[1].results
    history = kit.sessions.messages(answer.session_id, user.id, principal_hash(grants[0]))
    assert all(not message.results for message in history)
    assert "policy_version_change_required" in kit.workflow.stage(kit.catalog).issues


def test_unchanged_and_daily_data_change_do_not_rebuild_metadata(kit):
    version = kit.publish()
    service = kit.start()
    builds = kit.workflow.builder.builds
    with closing(sqlite3.connect(kit.settings.data_dir / "banking.db")) as conn, conn:
        conn.execute(
            "UPDATE loans SET amount_minor=10000100 WHERE tenant_id='demo' AND loan_id='L1' AND as_of='2026-09-30'"
        )
    assert kit.workflow.stage().no_change
    assert kit.workflow.builder.builds == builds
    assert kit.repository.control().active == version
    assert kit.query(service).rows[0]["loan_exposure"] == "175001.50"


def test_new_unmapped_column_has_no_automatic_metric_or_grant(kit):
    first = kit.publish()
    service = kit.start()
    with kit.manager.pin() as old:
        search = old.retriever
        with closing(sqlite3.connect(kit.settings.data_dir / "banking.db")) as conn, conn:
            conn.execute("ALTER TABLE loans ADD COLUMN confidential_new_flag TEXT")
        staged = kit.workflow.stage()
        assert staged.change_count == 1 and not staged.affected_views and not staged.issues
        assert kit.repository.control().active == first
        record = kit.repository.get(staged.candidate_id)
        assert record.spec.artifacts.rebuilt == ()
        assert all(metric.id != "confidential_new_flag" for metric in record.spec.catalog.metrics)
        kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), kit.admin)
        kit.workflow.publish(staged.candidate_id, kit.admin)
        kit.manager.reload()
        with kit.manager.pin() as new:
            assert new.retriever is search and new.version != old.version
        assert kit.query(service).rows[0]["loan_exposure"] == "175000.50"


def test_removed_account_source_quarantines_only_dependent_reports(kit):
    kit.publish()
    service = kit.start()
    with closing(sqlite3.connect(kit.settings.data_dir / "banking.db")) as conn, conn:
        conn.execute("DROP TABLE accounts")
    staged = kit.workflow.stage()
    assert "account_current" in kit.repository.control().blocked_views
    assert "loan_snapshot" not in kit.repository.control().blocked_views
    assert staged.issues
    assert kit.query(service).rows[0]["loan_exposure"] == "175000.50"
    with pytest.raises(Failure) as error:
        service.chat("Show account count by region", None, kit.settings.principals[0], None, {})
    assert error.value.code == "SCHEMA_DRIFT"


def test_failed_complete_runtime_build_keeps_active_version(kit):
    first = kit.publish()
    metrics = list(kit.catalog.metrics)
    metrics[0] = metrics[0].model_copy(
        update={"aliases": (*metrics[0].aliases, "exposure balance approved")}
    )
    new = kit.catalog.model_copy(update={"metrics": tuple(metrics)})
    staged = kit.workflow.stage(new, kit.settings.principals)
    kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), kit.admin)

    def fail(_spec):
        raise Failure("INJECTED_RUNTIME", "Synthetic resource build failed.", 503)

    kit.workflow.runtime_check = fail
    with pytest.raises(Failure):
        kit.workflow.publish(staged.candidate_id, kit.admin)
    assert kit.repository.control().active == first


def test_compatible_rollback_and_restart_recover_actual_results(kit):
    first = kit.publish()
    metrics = list(kit.catalog.metrics)
    metrics[0] = metrics[0].model_copy(
        update={"aliases": (*metrics[0].aliases, "approved synonym")}
    )
    second = kit.publish(kit.catalog.model_copy(update={"metrics": tuple(metrics)}))
    assert first != second
    service = kit.start()
    assert kit.query(service).provenance.bundle_version == second
    kit.workflow.rollback(first, kit.admin)
    assert kit.query(service).provenance.bundle_version == first
    kit.manager.close()
    kit.manager = None
    assert kit.query(kit.start()).rows[1]["loan_exposure"] == "75000.00"


def test_rollback_never_restores_security_grants(kit):
    first = kit.publish()
    grants = tuple(
        user.model_copy(update={"regions": ("north",)}) for user in kit.settings.principals
    )
    second = kit.publish(principals=grants)
    assert second != first
    with pytest.raises(Failure) as error:
        kit.workflow.rollback(first, kit.admin)
    assert error.value.code == "ROLLBACK_SECURITY"
    assert kit.repository.control().active == second
    with pytest.raises(Failure) as error:
        kit.query(kit.start(), kit.settings.principals[0])
    assert error.value.code == "DENIED"


def test_inflight_query_is_pinned_and_old_resources_retire_after_release(kit):
    first = kit.publish()
    kit.start()
    with kit.manager.pin() as old:
        metrics = list(kit.catalog.metrics)
        metrics[0] = metrics[0].model_copy(
            update={"aliases": (*metrics[0].aliases, "another approved synonym")}
        )
        second = kit.publish(kit.catalog.model_copy(update={"metrics": tuple(metrics)}))
        kit.manager.reload()
        with ThreadPoolExecutor(max_workers=2) as workers:
            old_answer = workers.submit(kit.query, old.service).result()
            new_answer = workers.submit(kit.query, BundleChatService(kit.manager)).result()
        assert old_answer.provenance.bundle_version == first
        assert new_answer.provenance.bundle_version == second
        assert old_answer.rows == new_answer.rows
        assert not old.database._pool.empty()
    assert old.database._pool.empty()


def test_refresh_lease_and_dry_run_do_not_change_publication(kit):
    before = kit.repository.control()
    events = kit.repository.history()
    result = kit.workflow.stage(kit.catalog, kit.settings.principals, dry_run=True)
    assert (
        result.dry_run and kit.repository.control() == before and kit.repository.history() == events
    )
    with kit.repository.refresh_lease():
        with pytest.raises(Failure) as error:
            kit.workflow.stage(kit.catalog, kit.settings.principals)
        assert error.value.code == "REFRESH_BUSY"


def test_source_change_after_approval_requires_rediscovery(kit):
    staged = kit.workflow.stage(kit.catalog, kit.settings.principals)
    kit.workflow.approve(staged.candidate_id, kit.approvals(staged.candidate_id), kit.admin)
    with closing(sqlite3.connect(kit.settings.data_dir / "banking.db")) as conn, conn:
        conn.execute("ALTER TABLE loans ADD COLUMN changed_after_review TEXT")
    with pytest.raises(Failure) as error:
        kit.workflow.publish(staged.candidate_id, kit.admin)
    assert error.value.code == "SOURCE_CHANGED"
    assert kit.repository.control().active is None
