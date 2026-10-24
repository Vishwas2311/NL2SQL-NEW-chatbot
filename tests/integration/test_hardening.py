"""Regressions for the independent audit and development hardening trust boundaries."""

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import httpx
import oracledb
import pytest
from nl2sql.application.catalog import validate_catalog
from nl2sql.application.context import build_context
from nl2sql.application.metadata.certification import reconcile
from nl2sql.application.metadata.drift import analyze_impact
from nl2sql.application.metadata.refresh import MetadataRefreshService
from nl2sql.application.query.planning import check_value
from nl2sql.bootstrap.runtime import RuntimeFactory
from nl2sql.domain.metadata import SchemaChange
from nl2sql.domain.models import Failure, Predicate, TypedValue
from nl2sql.domain.search import authorized_records, schema_records
from nl2sql.infrastructure.inference.model import HostedHTTPModel, PrivateHTTPModel, build_model
from nl2sql.infrastructure.metadata.builder import BundleBuilder
from nl2sql.infrastructure.retrieval.embeddings import (
    ManagedEncoder,
    PrivateEmbedding,
    build_embedding,
)
from nl2sql.settings import Settings, load_settings

from tests.contracts.test_oracle_adapter import FakeConnection, adapter_for
from tests.integration.test_metadata_lifecycle import MetadataKit
from tests.integration.test_pipeline import plan_for


def test_configuration_precedence_and_no_implicit_dotenv(tmp_path, monkeypatch):
    configuration = tmp_path / "config.json"
    configuration.write_text('{"pool_size":2}')
    selected = tmp_path / "explicit.env"
    selected.write_text("NL2SQL_POOL_SIZE=3\n")
    (tmp_path / ".env").write_text("NL2SQL_POOL_SIZE=9\n")
    monkeypatch.chdir(tmp_path)
    assert load_settings(configuration).pool_size == 2
    assert load_settings(configuration, selected).pool_size == 3
    monkeypatch.setenv("NL2SQL_POOL_SIZE", "4")
    assert load_settings(configuration, selected).pool_size == 4
    monkeypatch.setenv("NL2SQL_JWT_SECRET", "x" * 40)
    assert "x" * 40 not in repr(load_settings(configuration))


def test_example_configurations_are_valid(monkeypatch):
    from pathlib import Path

    assert load_settings(env_file=Path(".env.example")).model_mode == "disabled"
    laptop = load_settings(Path("config/office.example.json"))
    assert laptop.api_workers == 1 and laptop.max_concurrent_chats == 8
    assert laptop.max_concurrent_inferences == 1 and laptop.model_context_tokens == 100000
    selected = load_settings(Path("config/office.example.json"), Path("config/office.env.example"))
    assert selected.model_context_tokens == 100000 and selected.max_concurrent_inferences == 1
    assert laptop.rate_limit_backend == "memory" and laptop.embedding_mode == "disabled"
    assert laptop.model_mode == "configured_http" and laptop.model_token_budget == "provider"
    assert laptop.model_token_count_endpoint is None
    assert laptop.model_restricted_data_authorized is False
    with pytest.raises(ValueError, match="Redis rate limiting requires"):
        load_settings(Path("config/office.example.json"), Path("config/vm.env.example"))
    monkeypatch.setenv("NL2SQL_REDIS_URL", "redis://127.0.0.1:6379/0")
    office = load_settings(Path("config/office.example.json"), Path("config/vm.env.example"))
    assert office.embedding_mode == "disabled"
    assert office.rate_limit_backend == "redis"
    assert office.api_workers == 2


def test_synthetic_api_import_does_not_require_oracle_driver():
    code = """
import sys
class BlockOracle:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'oracledb':
            raise ImportError('optional driver absent')
sys.meta_path.insert(0, BlockOracle())
from nl2sql.cli.main import main
from nl2sql.api.app import create_app
"""
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


def test_readiness_acquisition_failure_is_safe(resources, monkeypatch):
    adapter, pool, _ = adapter_for(resources, FakeConnection())

    def fail():
        raise oracledb.DatabaseError("FICTIONAL_PRIVATE_DSN")

    monkeypatch.setattr(pool, "acquire", fail)
    with pytest.raises(Failure) as error:
        adapter.ready()
    assert error.value.code == "ORACLE_UNAVAILABLE"
    assert "PRIVATE" not in str(error.value) and pool.released == 0


def test_drift_tracks_time_only_column_and_semantic_table(settings, tmp_path):
    kit = MetadataKit(settings, tmp_path / "private")
    try:
        catalog = kit.catalog.model_copy(
            update={
                "dimensions": tuple(d for d in kit.catalog.dimensions if d.column != "paid_on"),
                "views": tuple(
                    v.model_copy(
                        update={"dimensions": tuple(d for d in v.dimensions if d != "payment_date")}
                    )
                    for v in kit.catalog.views
                ),
            }
        )
        inventory = kit.workflow.provider.discover()
        payments = next(obj for obj in inventory.objects if obj.name == "payments")
        impact = analyze_impact(
            (
                SchemaChange(
                    kind="column_removed",
                    classification="breaking_physical",
                    object_id=payments.id,
                    column="paid_on",
                ),
            ),
            catalog,
            inventory,
        )
        assert "payment_events" in impact.blocked_views
        impact = analyze_impact(
            (
                SchemaChange(
                    kind="semantic_tables", classification="metadata_only", semantic_id="loans"
                ),
            ),
            catalog,
            inventory,
        )
        assert "loan_snapshot" in impact.views and "loans" not in impact.views
        assert "loan_exposure" in impact.retrieval
    finally:
        kit.close()


def test_scheduled_dry_run_cannot_overlap(settings, tmp_path):
    kit = MetadataKit(settings, tmp_path / "private")
    entered, release = Event(), Event()
    original = kit.workflow.provider

    class Blocked:
        def discover(self):
            entered.set()
            assert release.wait(5)
            return original.discover()

    try:
        kit.publish()
        kit.workflow.provider = Blocked()
        kit.repository.configure_schedule(True, 5, True, "test")
        first = MetadataRefreshService(kit.workflow, clock=lambda: 1000)
        second = MetadataRefreshService(kit.workflow, clock=lambda: 1006)
        with ThreadPoolExecutor(2) as workers:
            running = workers.submit(first.tick)
            assert entered.wait(5)
            try:
                assert second.tick().ran is False
            finally:
                release.set()
            assert running.result().ran
    finally:
        release.set()
        kit.close()


def test_numeric_entity_ids_are_resolved_after_typed_validation(resources, monkeypatch):
    catalog = resources.service.compiler.catalog
    catalog = catalog.model_copy(
        update={
            "dimensions": tuple(
                d.model_copy(update={"kind": "integer"}) if d.id == "customer_id" else d
                for d in catalog.dimensions
            )
        }
    )
    resources.service.compiler.catalog = catalog
    seen = []

    def resolve(entity, phrase, principal, deadline):
        seen.append(phrase)
        return "123"

    monkeypatch.setattr(resources.database, "resolve_entity", resolve)
    plan = plan_for(
        resources,
        filters=Predicate(
            field="customer_id", op="eq", value=TypedValue(kind="integer", value=123)
        ),
    )
    resolved = resources.service._resolve_entities(plan, resources.auth.principals["analyst"])
    assert resolved.filters.value == TypedValue(kind="integer", value=123)
    assert seen == ["123"]


def test_decimal_filter_uses_certified_scale():
    predicate = Predicate(
        field="amount", op="gt", value=TypedValue(kind="decimal", value="1.123456")
    )
    check_value(predicate, "decimal", decimal_places=6, precision=38)
    for places in (0, 2, 5):
        with pytest.raises(Failure):
            check_value(predicate, "decimal", decimal_places=places, precision=38)
    for value in ("NaN", "Infinity", "1e33", "0.0000001"):
        with pytest.raises(Failure):
            check_value(
                predicate.model_copy(update={"value": TypedValue(kind="decimal", value=value)}),
                "decimal",
                decimal_places=6,
                precision=38,
            )


def test_structured_records_and_context_hide_ungranted_schema(resources):
    catalog = resources.service.compiler.catalog
    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("account_count",)})
    records = authorized_records(schema_records(catalog), user)
    assert {r.kind for r in records} >= {"domain", "table", "column", "metric", "view", "grain"}
    assert all(r.catalog_version == catalog.version for r in records)
    assert not any(
        r.id == "metric:loan_exposure" or r.id.startswith("column:loans.") for r in records
    )
    candidates = resources.retriever.retrieve("account count", resources.auth.principals["analyst"])
    context = build_context(catalog, user, candidates)
    assert "loan_exposure" not in context and "column:accounts.account_id" in context
    assert len(context.encode()) <= 64_000
    assert resources.retriever.retrieve_schema("region", resources.auth.principals["analyst"])


@pytest.mark.parametrize("mode", ["json_schema", "json_object", "text_json"])
def test_model_capabilities_share_typed_parser(resources, mode):
    expected = plan_for(resources)

    def reply(request):
        payload = json.loads(request.content)
        if mode == "text_json":
            assert "response_format" not in payload
        else:
            assert payload["response_format"]["type"] == mode
        text = expected.model_dump_json()
        if mode == "text_json":
            text = "```json\n" + text + "\n```"
        return httpx.Response(
            200,
            json={
                "id": "mock",
                "object": "chat.completion",
                "created": 1,
                "model": "synthetic-plan",
                "choices": [
                    {"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
                ],
            },
        )

    settings = Settings(
        data_classification="synthetic",
        model_mode="private_http",
        model_name="synthetic-plan",
        model_endpoint="http://127.0.0.1/plans",
        approved_model_hosts=("127.0.0.1",),
        model_output_mode=mode,
    )
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        provider = PrivateHTTPModel(settings, client)
        assert provider.plan("synthetic", "{}", time.time() + 5).plan == expected


def test_hosted_egress_gate_rechecks_catalog_before_network():
    with pytest.raises(ValueError):
        Settings(model_mode="hosted_http")
    settings = Settings(
        model_mode="hosted_http",
        public_model_authorized=True,
        data_classification="synthetic",
        model_endpoint="https://synthetic.invalid/plans",
        approved_model_hosts=("synthetic.invalid",),
    )

    def forbidden(_):
        raise AssertionError("Restricted metadata reached the network")

    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        provider = HostedHTTPModel(settings, client)
        for context in ('{"classification":"restricted"}', "{}", "[]", "invalid"):
            with pytest.raises(Failure, match="classif|restricted"):
                provider.plan("synthetic", context, time.time() + 5)
    assert build_model(Settings()).__class__.__name__ == "DisabledModel"
    assert build_model(Settings(model_mode="scripted")).__class__.__name__ == "MockModel"


def embedding_settings(**changes):
    return Settings(
        embedding_mode="fake",
        data_classification="synthetic",
        embedding_model="synthetic",
        embedding_version="1",
        embedding_dimension=2,
        embedding_batch_size=2,
        **changes,
    )


@pytest.mark.parametrize(
    "vector", [(), (0.0, 0.0), (float("nan"), 1.0), (float("inf"), 1.0), (1.0,)]
)
def test_embedding_validation(vector):
    class Invalid:
        def encode(self, texts):
            return tuple(vector for _ in texts)

    encoder = ManagedEncoder(embedding_settings(), Invalid())
    with pytest.raises(ValueError):
        encoder.encode(("certified synthetic",))


def test_embedding_cache_batches_singleflight_and_cancellation():
    calls = []

    class Encoder:
        def encode(self, texts):
            calls.append(texts)
            return tuple((3.0, 4.0) for _ in texts)

    encoder = ManagedEncoder(embedding_settings(), Encoder())
    with ThreadPoolExecutor(10) as workers:
        outputs = list(workers.map(lambda _: encoder.encode(("one", "two", "three")), range(10)))
    assert calls == [("one", "two"), ("three",)]
    assert all(result == ((0.6, 0.8),) * 3 for result in outputs)
    cancelled = Event()
    cancelled.set()
    with pytest.raises(Failure, match="cancelled"):
        encoder.encode_bounded(("one",), cancelled=cancelled)
    with pytest.raises(Failure, match="timed out"):
        encoder.encode_bounded(("one",), deadline=time.time() - 1)
    with pytest.raises(ValueError, match="budget"):
        encoder.encode(("x",) * 10001)
    assert build_embedding(Settings()) is None
    assert build_embedding(embedding_settings()).identity == encoder.identity


@pytest.mark.parametrize(
    "scenario", ["model", "version", "partial", "shape", "unavailable", "timeout"]
)
def test_private_embeddings_fail_closed(scenario):
    def response(request):
        assert json.loads(request.content)["input"] == ["synthetic"]
        if scenario == "timeout":
            raise httpx.ReadTimeout("FICTIONAL_SECRET")
        if scenario == "unavailable":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "model": "other" if scenario == "model" else "synthetic",
                "version": "other" if scenario == "version" else "1",
                "data": []
                if scenario == "partial"
                else [{"index": 2 if scenario == "shape" else 0, "embedding": [1.0, 0.0]}],
            },
        )

    settings = embedding_settings(
        embedding_endpoint="http://127.0.0.1/embeddings", approved_embedding_hosts=("127.0.0.1",)
    )
    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        provider = PrivateEmbedding(settings, client)
        with pytest.raises((ValueError, Failure)) as error:
            provider.encode(("synthetic",))
        assert "FICTIONAL_SECRET" not in str(error.value)


def test_normal_managed_runtime_wires_same_encoder_without_startup_discovery(
    settings, tmp_path, monkeypatch
):
    from nl2sql.bootstrap.managed import build_managed_resources
    from nl2sql.infrastructure.metadata.config import SourceProfile

    root = tmp_path / "private"
    configuration = settings.model_copy(
        update={
            "metadata_root": root,
            "embedding_mode": "fake",
            "embedding_model": "synthetic",
            "embedding_version": "1",
            "data_classification": "synthetic",
        }
    )
    kit = MetadataKit(configuration, root)
    encoder = build_embedding(configuration)
    kit.workflow.builder = BundleBuilder(encoder, encoder.identity)
    kit.factory = RuntimeFactory(
        configuration,
        kit.sessions,
        kit.model,
        encoder,
        encoder.identity,
        inference_admission=kit.inference,
    )
    kit.workflow.runtime_check = kit.factory.check
    try:
        published = kit.publish()
        monkeypatch.setattr(
            "nl2sql.bootstrap.managed.authority_from_environment", lambda: kit.authority
        )
        monkeypatch.setattr(
            "nl2sql.bootstrap.managed.load_profile",
            lambda _: SourceProfile(
                source="synthetic",
                source_id="synthetic-banking",
                database_path=configuration.data_dir / "banking.db",
            ),
        )

        def no_discovery(_):
            class Forbidden:
                def discover(self):
                    raise AssertionError("Ordinary startup must not discover or stage")

            return Forbidden()

        monkeypatch.setattr(SourceProfile, "provider", no_discovery)
        managed = build_managed_resources(configuration)
        try:
            with managed.manager.pin() as bundle:
                assert bundle.version == published
                assert bundle.retriever.encoder.identity == encoder.identity
                assert bundle.retriever.retrieve("deposit tally", configuration.principals[0])
            answer = managed.service.chat(
                "Show total loan exposure by region",
                None,
                managed.auth.principals["analyst"],
                None,
                {},
            )
            assert answer.rows[0]["loan_exposure"] == "175000.50"
        finally:
            managed.close()
        changed = build_embedding(configuration.model_copy(update={"embedding_version": "2"}))
        kit.workflow.builder = BundleBuilder(changed, changed.identity)
        staged = kit.workflow.stage()
        assert not staged.no_change and staged.candidate_id != published
        assert kit.repository.control().active == published
    finally:
        kit.close()


def test_logical_relationship_requires_explicit_compatible_evidence_and_signed_publication(
    settings, tmp_path
):
    from nl2sql.domain.models import LogicalJoinEvidence

    kit = MetadataKit(settings, tmp_path / "private")
    try:
        catalog = kit.catalog
        inventory = kit.workflow.provider.discover()
        inventory = inventory.model_copy(
            update={
                "objects": tuple(
                    obj.model_copy(
                        update={"keys": tuple(key for key in obj.keys if key.kind != "foreign")}
                    )
                    for obj in inventory.objects
                )
            }
        )
        assert any(
            issue.startswith("relationship_unverified")
            for issue in reconcile(catalog, inventory).issues
        )
        tables = {table.id: table for table in catalog.tables}
        relationships = tuple(
            relation.model_copy(
                update={
                    "logical_evidence": LogicalJoinEvidence(
                        review_reference="fictional-review-1",
                        effective_catalog_version=catalog.version,
                        source_grain=tables[relation.left].grain,
                        target_grain=tables[relation.right].grain,
                        partition_pairs=(("tenant_id", "tenant_id"),),
                        column_types=tuple(
                            (
                                next(c.kind for c in tables[relation.left].columns if c.name == a),
                                next(c.kind for c in tables[relation.right].columns if c.name == b),
                            )
                            for a, b in relation.pairs
                        ),
                        evidence="Fictional explicit steward proposal",
                    )
                }
            )
            for relation in catalog.relations
        )
        proposal = catalog.model_copy(update={"relations": relationships})
        validate_catalog(proposal)
        assert not reconcile(proposal, inventory).issues
        for update in (
            {"column_types": (("text", "decimal"),)},
            {"partition_pairs": ()},
            {"target_grain": ("wrong",)},
            {"effective_catalog_version": "stale"},
        ):
            bad = relationships[0].model_copy(
                update={
                    "logical_evidence": relationships[0].logical_evidence.model_copy(update=update)
                }
            )
            with pytest.raises(ValueError, match="Logical"):
                validate_catalog(
                    proposal.model_copy(update={"relations": (bad, *relationships[1:])})
                )

        class Imported:
            def discover(self):
                return inventory

        kit.workflow.provider = Imported()
        staged = kit.workflow.stage(proposal, settings.principals)
        with pytest.raises(Failure):
            kit.workflow.publish(staged.candidate_id, kit.admin)
        assert kit.repository.control().active is None
    finally:
        kit.close()


def test_restricted_cache_survives_restart_and_rebuilds_corruption(tmp_path):
    from nl2sql.infrastructure.retrieval.embedding_cache import restricted_path

    root = tmp_path / "private"
    root.mkdir()
    settings = embedding_settings(index_storage_path=root)
    with pytest.raises(ValueError, match="restricted"):
        build_embedding(settings)
    (root / ".metadata-private").touch()
    first = build_embedding(settings)
    expected = first.encode(("fictional metric",))
    first.checkpoint(("fictional metric",))
    second = build_embedding(settings)

    class Unavailable:
        def encode(self, texts):
            raise AssertionError("Unchanged content should load from its validated snapshot")

    second.provider = Unavailable()
    assert second.encode(("fictional metric",)) == expected
    path = restricted_path(root, first.identity)
    assert "fictional metric" not in path.read_text()
    path.write_text("corrupt")
    third = build_embedding(settings)
    assert third.encode(("fictional metric",)) == expected


def test_load_measurements_and_retrieval_ablations_are_independent(settings, tmp_path):
    from nl2sql.domain.models import Catalog
    from nl2sql.evaluation.load import evaluate_load
    from nl2sql.evaluation.retrieval import evaluate_retrieval

    report = evaluate_load(tmp_path / "load", levels=(1, 2))
    assert [row["requests"] for row in report["levels"]] == [3, 6]
    assert all(
        row["correct_results"] == row["requests"] and row["errors"] == 0 for row in report["levels"]
    )
    catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
    retrieval = evaluate_retrieval(catalog, settings.principals)
    assert retrieval["model_calls"] == 0
    assert set(retrieval["modes"]) == {"exact_only", "exact_bm25", "graph_filtered"}
    assert all(row["authorization_violations"] == 0 for row in retrieval["modes"].values())
    assert (
        retrieval["modes"]["exact_bm25"]["recall_at_10"]
        >= retrieval["modes"]["exact_only"]["recall_at_10"]
    )


def test_followups_are_bounded_and_reauthorized(resources):
    user = resources.auth.principals["analyst"]
    service = resources.service
    first = service.chat("Show total loan exposure", None, user, None, {})
    grouped = service.chat("Now group it by region", first.session_id, user, None, {})
    assert grouped.rows == (
        {"region": "Demo North", "loan_exposure": "175000.50"},
        {"region": "Demo South", "loan_exposure": "75000.00"},
    )
    top = service.chat("Give the top five", first.session_id, user, None, {})
    assert top.rows[0]["region"] == "Demo North"
    for question in ("Compare those results", "Show the same for another branch"):
        before = resources.database.execute_count
        answer = service.chat(question, first.session_id, user, None, {})
        assert (
            answer.status == "clarification_required" and resources.database.execute_count == before
        )
    revoked = user.model_copy(update={"metrics": ()})
    with pytest.raises(Failure):
        service.chat("Now group it by region", first.session_id, revoked, None, {})
    resources.sessions.delete(first.session_id, user.id)
    with pytest.raises(Failure, match="not found"):
        service.chat("Give the top five", first.session_id, user, None, {})


def test_session_queue_is_bounded_by_request_deadline(resources):
    from nl2sql.telemetry import stage_metrics

    entered, release = Event(), Event()

    def hold():
        with resources.sessions._lock:
            entered.set()
            assert release.wait(5)

    with ThreadPoolExecutor(1) as workers:
        held = workers.submit(hold)
        assert entered.wait(5)
        try:
            with stage_metrics({}, time.time() + 0.02), pytest.raises(Failure) as error:
                resources.sessions.create("analyst", "synthetic")
            assert error.value.code == "SESSION_BUSY"
        finally:
            release.set()
        held.result()


def test_component_readiness_and_storage_failure_are_safe(settings, credentials, monkeypatch):
    import sqlite3

    from fastapi.testclient import TestClient
    from nl2sql.bootstrap.factory import create_app
    from nl2sql.bootstrap.resources import build_resources

    resources = build_resources(settings)

    original_connection = resources.sessions._connection

    class UnavailableConnection:
        def execute(self, *_args):
            raise sqlite3.OperationalError("FICTIONAL_PRIVATE_STORAGE")

        def close(self):
            original_connection.close()

    with TestClient(create_app(settings, resources_factory=lambda *_: resources)) as client:
        headers = {"Authorization": "Bearer " + credentials["analyst"]}
        assert client.get("/api/v1/health/components").status_code == 401
        status = client.get("/api/v1/health/components", headers=headers)
        assert status.json()["model"] == "disabled" and status.json()["index"] == "compatible"
        monkeypatch.setattr(resources.sessions, "_connection", UnavailableConnection())
        response = client.get("/ews-chatbot/get_all_sessions", headers=headers)
        assert response.status_code == 503 and "PRIVATE" not in response.text


def test_oracle_decimal_entity_keys_and_zero_decimal_filter():
    from decimal import Decimal

    from nl2sql.application.query.entity_lookup import exact_entity

    assert exact_entity([(Decimal("123"),)]) == "123"
    for value in (Decimal("1.5"), Decimal("NaN"), Decimal("Infinity"), True):
        with pytest.raises(Failure):
            exact_entity([(value,)])
    check_value(
        Predicate(field="amount", op="eq", value=TypedValue(kind="decimal", value="0.0")),
        "decimal",
        decimal_places=1,
        precision=1,
    )


def test_runtime_builds_coalesce_without_holding_resource_lock(settings, tmp_path):
    kit = MetadataKit(settings, tmp_path / "private")
    entered, release = Event(), Event()

    class Encoder:
        blocking = False
        calls = 0

        def encode(self, texts):
            self.calls += 1
            if self.blocking:
                entered.set()
                assert release.wait(5)
            return tuple((1.0, 0.0) for _ in texts)

    encoder = Encoder()
    try:
        kit.workflow.builder = BundleBuilder(encoder, "synthetic-1")
        staged = kit.workflow.stage(kit.catalog, settings.principals)
        spec = kit.repository.get(staged.candidate_id).spec
        factory = RuntimeFactory(
            settings,
            kit.sessions,
            kit.model,
            encoder,
            "synthetic-1",
            inference_admission=kit.inference,
        )
        encoder.calls = 0
        encoder.blocking = True
        with ThreadPoolExecutor(2) as workers:
            first = workers.submit(factory.build, spec)
            assert entered.wait(5)
            second = workers.submit(factory.build, spec)
            assert factory._lock.acquire(blocking=False)
            factory._lock.release()
            release.set()
            bundles = [first.result(), second.result()]
        assert bundles[0].retriever is bundles[1].retriever and encoder.calls == 1
        for bundle in bundles:
            bundle.close()
        assert not factory._searches
    finally:
        release.set()
        kit.close()


def test_integer_customer_identifier_runs_full_pipeline(settings, tmp_path):
    import sqlite3
    from contextlib import closing

    from nl2sql.bootstrap.resources import build_resources
    from nl2sql.domain.fingerprints import digest
    from nl2sql.domain.models import Catalog, QueryPlan
    from nl2sql.infrastructure.inference.model import MockModel

    numeric = tmp_path / "numeric"
    numeric.mkdir()
    with (
        closing(sqlite3.connect(settings.data_dir / "banking.db")) as source,
        closing(sqlite3.connect(numeric / "banking.db")) as target,
    ):
        tables = source.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
        for name, sql in tables:
            target.execute(sql.replace("customer_id TEXT", "customer_id INTEGER"))
            columns = [row[1] for row in source.execute(f'PRAGMA table_info("{name}")')]
            rows = source.execute(f'SELECT * FROM "{name}"').fetchall()
            converted = [
                tuple(
                    int(value[1:]) if columns[i] == "customer_id" else value
                    for i, value in enumerate(row)
                )
                for row in rows
            ]
            target.executemany(
                f'INSERT INTO "{name}" VALUES ({",".join("?" for _ in columns)})', converted
            )
        target.commit()
        assert not target.execute("PRAGMA foreign_key_check").fetchall()
    catalog = Catalog.model_validate_json(settings.catalog_path.read_text())
    catalog = catalog.model_copy(
        update={
            "tables": tuple(
                table.model_copy(
                    update={
                        "columns": tuple(
                            column.model_copy(update={"kind": "integer"})
                            if column.name == "customer_id"
                            else column
                            for column in table.columns
                        )
                    }
                )
                for table in catalog.tables
            ),
            "dimensions": tuple(
                dimension.model_copy(update={"kind": "integer"})
                if dimension.id == "customer_id"
                else dimension
                for dimension in catalog.dimensions
            ),
        }
    )
    path = numeric / "catalog.json"
    payload = catalog.model_dump_json()
    path.write_text(payload)
    configuration = settings.model_copy(
        update={"data_dir": numeric, "catalog_path": path, "catalog_digest": digest(payload)}
    )
    plan = QueryPlan(
        catalog_version=catalog.version,
        view_id="account_current",
        metrics=("account_count",),
        dimensions=("customer_id",),
        filters=Predicate(field="customer_id", op="eq", value=TypedValue(kind="integer", value=1)),
    )
    resources = build_resources(
        configuration, MockModel({"account count for customer 1": plan.model_dump_json()})
    )
    try:
        answer = resources.service.chat(
            "account count for customer 1", None, resources.auth.principals["analyst"], None, {}
        )
        assert answer.rows == ({"customer_id": 1, "account_count": 2},)
    finally:
        resources.close()


@pytest.mark.parametrize(
    "text,identity",
    [
        ("paid_on", "column:payments.paid_on"),
        ("loan_snapshot", "view:loan_snapshot"),
        ("loans", "table:loans"),
    ],
)
def test_typed_schema_retrieval_finds_sources_and_views(resources, text, identity):
    candidates = resources.retriever.retrieve_schema(text, resources.auth.principals["analyst"])
    assert identity in {candidate.id for candidate in candidates}


@pytest.mark.parametrize("workers", [1, 10, 25, 50])
def test_concurrent_bm25_searches_preserve_partition_and_ranking(resources, workers):
    from nl2sql.infrastructure.retrieval.lexical import Retriever

    full = resources.auth.principals["analyst"]
    limited = full.model_copy(update={"id": "limited", "metrics": ("account_count",)})
    search = Retriever(resources.service.compiler.catalog, (full, limited))
    try:
        queries = (("half open ISO business date intervals", full), ("fictional now", limited))
        expected = tuple(search.retrieve(text, user) for text, user in queries)
        assert all(
            result and all(candidate.method == "bm25" for candidate in result)
            for result in expected
        )

        def execute(index):
            text, user = queries[index % 2]
            candidates = search.retrieve(text, user)
            assert candidates == expected[index % 2]
            assert all(candidate.metric_id in user.metrics for candidate in candidates)
            if user is limited:
                assert search.retrieve_schema("paid_on", user) == ()
            return True

        with ThreadPoolExecutor(workers) as pool:
            assert all(pool.map(execute, range(workers * 3)))
    finally:
        search.close()


@pytest.mark.parametrize(
    "amount", ["1000000000000000000000000000000.00", "-1000000000000000000000000000000.00"]
)
def test_sqlite_numeric_range_is_separate_from_oracle_precision(resources, amount):
    from tests.integration.test_pipeline import run_plan

    plan = plan_for(
        resources,
        having=Predicate(
            field="loan_exposure", op="gt", value=TypedValue(kind="decimal", value=amount)
        ),
    )
    with pytest.raises(Failure) as error:
        run_plan(resources, plan)
    assert error.value.code == "NUMERIC_RANGE" and resources.database.execute_count == 0
    oracle = run_plan(resources, plan, dialect="oracle")
    expected = int(amount.partition(".")[0]) * 100
    assert expected in dict(oracle.binds).values()
