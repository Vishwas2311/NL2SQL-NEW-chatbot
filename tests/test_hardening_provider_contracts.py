"""Failure, cache and egress contracts use fake transports and synthetic content only."""

import json
import ssl
import time
from threading import Event

import httpx
import oracledb
import pytest
from nl2sql.config import Settings
from nl2sql.domain import Failure
from nl2sql.embeddings import (
    ManagedEncoder,
    PrivateEmbedding,
    build_embedding,
    register_local_embedding,
)
from nl2sql.model import (
    DisabledModel,
    HostedHTTPModel,
    PrivateHTTPModel,
    build_context,
    build_model,
    register_model,
)
from nl2sql.oracle_discovery import OracleDiscovery, OracleDiscoverySettings
from nl2sql.search_metadata import schema_records
from test_hardening import embedding_settings
from test_pipeline import plan_for


def envelope(plan, model="contract-model"):
    return {
        "id": "synthetic",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "choices": [
            {
                "message": {"role": "assistant", "content": plan.model_dump_json()},
                "finish_reason": "stop",
            }
        ],
    }


@pytest.mark.parametrize("failure", [429, 502, 503, "connect", "read", "tls", "invalid"])
def test_http_retries_only_transient_failures(resources, failure):
    attempts = []
    plan = plan_for(resources)

    def respond(request):
        attempts.append(request)
        if len(attempts) == 1:
            if failure == "connect":
                raise httpx.ConnectError("FICTIONAL_SECRET")
            if failure == "read":
                raise httpx.ReadError("FICTIONAL_SECRET")
            if failure == "tls":
                raise httpx.ConnectError("FICTIONAL_SECRET") from ssl.SSLError("FICTIONAL_SECRET")
            if failure == "invalid":
                return httpx.Response(200, json={})
            return httpx.Response(failure)
        return httpx.Response(200, json=envelope(plan))

    settings = Settings(
        model_name="contract-model",
        model_endpoint="http://127.0.0.1/plans",
        approved_model_hosts=("127.0.0.1",),
        model_retries=1,
    )
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = PrivateHTTPModel(settings, client)
        if failure in {"tls", "invalid"}:
            with pytest.raises(Failure) as error:
                provider.plan("synthetic", "{}", time.time() + 5)
            assert "SECRET" not in str(error.value) and len(attempts) == 1
        else:
            assert provider.plan("synthetic", "{}", time.time() + 5).plan == plan
            assert len(attempts) == 2


def test_hosted_positive_and_precancelled_calls_use_explicit_gate(resources):
    calls = []
    plan = plan_for(resources)

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=envelope(plan))

    settings = Settings(
        model_mode="hosted_http",
        model_name="contract-model",
        public_model_authorized=True,
        data_classification="synthetic",
        model_endpoint="https://synthetic.invalid/plans",
        approved_model_hosts=("synthetic.invalid",),
    )
    cancelled = Event()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = HostedHTTPModel(settings, client)
        assert (
            provider.plan("synthetic", '{"classification":"synthetic"}', time.time() + 5).plan
            == plan
        )
        cancelled.set()
        with pytest.raises(Failure) as error:
            provider.plan("synthetic", '{"classification":"synthetic"}', time.time() + 5, cancelled)
        assert error.value.code == "MODEL_CANCELLED" and len(calls) == 1
    for endpoint in ("http://synthetic.invalid/plans", "https://user:pass@synthetic.invalid/plans"):
        with pytest.raises(ValueError):
            HostedHTTPModel(settings.model_copy(update={"model_endpoint": endpoint}))


def test_model_registration_rejects_unknown_and_duplicate_adapters():
    name = "synthetic_contract_adapter"
    register_model(name, lambda _: DisabledModel())
    assert isinstance(build_model(Settings(model_mode=name)), DisabledModel)
    with pytest.raises(ValueError):
        register_model(name, lambda _: DisabledModel())
    with pytest.raises(ValueError):
        build_model(Settings(model_mode="unregistered_adapter"))


def test_context_budget_and_unapproved_metadata_are_enforced(resources):
    catalog = resources.service.compiler.catalog
    user = resources.auth.principals["analyst"]
    candidates = resources.retriever.retrieve("loan exposure", user)
    base = json.loads(build_context(catalog, user, candidates))
    base["schema_records"] = []
    required_bytes = len(json.dumps(base, separators=(",", ":"), sort_keys=True).encode())
    shortened = build_context(catalog, user, candidates, max_bytes=required_bytes + 100)
    assert json.loads(shortened)["truncated"] is True
    assert len(shortened.encode()) <= required_bytes + 100
    assert shortened == build_context(catalog, user, candidates, max_bytes=required_bytes + 100)
    with pytest.raises(Failure, match="budget"):
        build_context(catalog, user, candidates, max_bytes=1)
    with pytest.raises(ValueError, match="certified"):
        schema_records(catalog.model_copy(update={"approved": False}))


def test_embedding_success_identity_and_normalization_none():
    settings = embedding_settings(
        embedding_endpoint="http://127.0.0.1/embeddings",
        approved_embedding_hosts=("127.0.0.1",),
        embedding_normalization="none",
    )

    def respond(request):
        assert json.loads(request.content)["model"] == "synthetic"
        return httpx.Response(
            200,
            json={
                "model": "synthetic",
                "version": "1",
                "data": [{"index": 0, "embedding": [3.0, 4.0]}],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = PrivateEmbedding(settings, client)
        encoder = ManagedEncoder(settings, provider)
        assert encoder.encode(("fictional",)) == ((3.0, 4.0),)
        encoder.close()


@pytest.mark.parametrize("kind", ["invalid_json", "oversized", "empty"])
def test_embedding_responses_are_bounded(kind):
    settings = embedding_settings(
        embedding_endpoint="http://127.0.0.1/embeddings", approved_embedding_hosts=("127.0.0.1",)
    )
    payload = {"invalid_json": b"not-json", "oversized": b"x" * 4_000_001, "empty": b""}[kind]
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=payload))
    ) as client:
        with pytest.raises(ValueError):
            PrivateEmbedding(settings, client).encode(("fictional",))


def test_embedding_partial_batch_does_not_publish_and_lru_is_bounded():
    class Partial:
        def encode(self, texts):
            return ((1.0, 0.0),)

    partial = ManagedEncoder(embedding_settings(), Partial())
    with pytest.raises(ValueError, match="incomplete"):
        partial.encode(("one", "two"))
    assert not partial._cache

    class Encoder:
        def encode(self, texts):
            return tuple((1.0, 0.0) for _ in texts)

    bounded = ManagedEncoder(embedding_settings(embedding_cache_entries=1), Encoder())
    bounded.encode(("one", "two", "three"))
    assert len(bounded._cache) == 1
    with pytest.raises(ValueError, match="budget"):
        bounded.encode(("x" * 10_000_001,))


def test_local_encoder_registration_requires_existing_model_and_explicit_identity(tmp_path):
    class Installed:
        def encode(self, texts):
            return tuple((1.0, 0.0) for _ in texts)

    register_local_embedding("installed-synthetic", lambda path: Installed())
    settings = Settings(
        embedding_mode="local",
        embedding_model="installed-synthetic",
        embedding_version="v1",
        embedding_dimension=2,
        embedding_local_path=tmp_path,
    )
    encoder = build_embedding(settings)
    assert encoder.encode(("fictional",)) == ((1.0, 0.0),)
    with pytest.raises(ValueError):
        register_local_embedding("installed-synthetic", lambda path: Installed())
    for update in (
        {"embedding_local_path": tmp_path / "missing"},
        {"embedding_model": "unknown"},
        {"embedding_version": "disabled"},
    ):
        with pytest.raises(ValueError):
            build_embedding(settings.model_copy(update=update))
    with pytest.raises(ValueError, match="synthetic"):
        build_embedding(
            embedding_settings().model_copy(update={"data_classification": "restricted"})
        )


def test_optional_cache_write_failure_keeps_valid_memory_results(tmp_path, monkeypatch, caplog):
    (tmp_path / ".metadata-private").touch()
    encoder = build_embedding(embedding_settings(index_storage_path=tmp_path))

    def unavailable(*_):
        raise OSError("FICTIONAL_SECRET_PATH")

    monkeypatch.setattr("nl2sql.embeddings.save_vectors", unavailable)
    assert len(encoder.encode(("fictional",))) == 1
    assert "embedding_cache_write_failed" in caplog.text and "SECRET" not in caplog.text


@pytest.mark.parametrize("step", ["acquire", "rollback", "release", "drop"])
def test_oracle_discovery_pool_failures_are_sanitized(step):
    from test_discovery import DictionaryConnection

    class Connection(DictionaryConnection):
        def rollback(self):
            if step in {"rollback", "drop"}:
                raise oracledb.DatabaseError("FICTIONAL_PRIVATE_CREDENTIALS")

    class Pool:
        def acquire(self):
            if step == "acquire":
                raise oracledb.DatabaseError("FICTIONAL_PRIVATE_CREDENTIALS")
            return Connection()

        def release(self, connection):
            if step == "release":
                raise oracledb.DatabaseError("FICTIONAL_PRIVATE_CREDENTIALS")

        def drop(self, connection):
            if step == "drop":
                raise oracledb.DatabaseError("FICTIONAL_PRIVATE_CREDENTIALS")

    settings = OracleDiscoverySettings(
        approved_environment=True,
        owner_authorized=True,
        network_authorized=True,
        owners=("Fictional Office",),
    )
    with pytest.raises(Failure) as error:
        OracleDiscovery(settings, Pool()).discover()
    assert "PRIVATE" not in str(error.value) and error.value.__suppress_context__


def test_cache_compatibility_corruption_and_path_guards(tmp_path, monkeypatch):
    from pathlib import Path

    from nl2sql.embedding_cache import checksum, load_vectors, restricted_path

    (tmp_path / ".metadata-private").touch()
    encoder = build_embedding(embedding_settings(index_storage_path=tmp_path))
    encoder.encode(("fictional",))
    path = restricted_path(tmp_path, encoder.identity)
    original = json.loads(path.read_text())
    for update in (
        {"identity": "wrong"},
        {"dimension": 3},
        {"normalization": "none"},
        {"checksum": "wrong"},
    ):
        path.write_text(json.dumps(original | update))
        assert load_vectors(path, encoder.identity, 2, "l2") == {}
    for vector in ((1.0,), (0.0, 0.0), (3.0, 4.0)):
        entries = dict.fromkeys(original["entries"], vector)
        path.write_text(json.dumps(original | {"entries": entries, "checksum": checksum(entries)}))
        assert load_vectors(path, encoder.identity, 2, "l2") == {}
    with pytest.raises(ValueError, match="identity"):
        restricted_path(tmp_path, "../../escape")
    monkeypatch.setattr(Path, "is_symlink", lambda _: True)
    with pytest.raises(ValueError, match="symbolic"):
        restricted_path(tmp_path, encoder.identity)


def test_http_embedding_deadline_and_factory_selection():
    from nl2sql.telemetry import stage_metrics

    settings = embedding_settings(
        embedding_endpoint="http://127.0.0.1/embeddings", approved_embedding_hosts=("127.0.0.1",)
    )
    encoder = build_embedding(settings.model_copy(update={"embedding_mode": "private_http"}))
    try:
        assert isinstance(encoder.provider, PrivateEmbedding)
        with stage_metrics({}, time.time() - 1), pytest.raises(Failure) as error:
            encoder.provider.encode(("fictional",))
        assert error.value.code == "EMBEDDING_TIMEOUT"
    finally:
        encoder.close()


def test_cancelled_stream_closes_without_parsing_or_retry(resources):
    cancelled = Event()
    closed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            cancelled.set()
            yield b'{"untrusted":"incomplete"}'

        def close(self):
            closed.append(True)

    settings = Settings(
        model_endpoint="http://127.0.0.1/plans", approved_model_hosts=("127.0.0.1",)
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=Stream()))
    ) as client:
        with pytest.raises(Failure) as error:
            PrivateHTTPModel(settings, client).plan("fictional", "{}", time.time() + 5, cancelled)
        assert error.value.code == "MODEL_CANCELLED" and closed == [True]


def test_metadata_dotenv_reaches_staging_publication_and_managed_runtime(tmp_path, monkeypatch):
    from pathlib import Path

    from nl2sql.config import load_settings
    from nl2sql.managed_resources import build_managed_resources
    from nl2sql.metadata_cli import MetadataOptions, run_metadata
    from nl2sql.metadata_store import MetadataRepository

    root = tmp_path / "private"
    selected = tmp_path / "synthetic.env"
    selected.write_text(
        "NL2SQL_DATA_CLASSIFICATION=synthetic\nNL2SQL_EMBEDDING_MODE=fake\n"
        "NL2SQL_EMBEDDING_MODEL=synthetic\nNL2SQL_EMBEDDING_VERSION=1\n"
        "NL2SQL_EMBEDDING_DIMENSION=2\n"
    )

    def run(action, **options):
        return run_metadata(MetadataOptions(action=action, root=root, env_file=selected, **options))

    staged = run("bootstrap", source="synthetic")
    version = staged["candidate_id"]
    trust = run("demo-trust")
    for key, value in json.loads(Path(trust["private_credentials"]).read_text()).items():
        monkeypatch.setenv(key, value)
    signatures = run("sign-demo", candidate_id=version)
    run("approve", candidate_id=version, approval_file=Path(signatures["private_output"]))
    run("publish", candidate_id=version)
    assert run("sync")["no_change"]
    with pytest.raises(Failure, match="restricted"):
        run("inspect", candidate_id=version, output=tmp_path / "public.txt")
    repository = MetadataRepository(root)
    try:
        assert repository.get(version).spec.artifacts.encoder_version is not None
    finally:
        repository.close()
    settings = load_settings(root / "data/settings.json", selected).model_copy(
        update={"metadata_root": root}
    )
    managed = build_managed_resources(settings)
    try:
        answer = managed.service.chat(
            "Show total loan exposure by region", None, managed.auth.principals["analyst"], None, {}
        )
        assert answer.rows[0]["loan_exposure"] == "175000.50"
    finally:
        managed.close()


def test_configuration_validation_cli_does_not_expose_invalid_values(tmp_path, monkeypatch, capsys):
    import sys

    from nl2sql.__main__ import main

    path = tmp_path / "config.json"
    path.write_text('{"model_mode":"unregistered","model_key":"FICTIONAL_PRIVATE_KEY"}')
    monkeypatch.setattr(sys, "argv", ["nl2sql", "validate-config", "--settings", str(path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 1
    assert "PRIVATE" not in capsys.readouterr().err


@pytest.mark.parametrize("change", ["missing_role", "function_call"])
def test_model_missing_role_and_legacy_tool_calls_are_rejected(resources, change):
    reply = envelope(plan_for(resources))
    if change == "missing_role":
        reply["choices"][0]["message"].pop("role")
    else:
        reply["choices"][0]["message"]["function_call"] = {
            "name": "execute_sql",
            "arguments": "untrusted",
        }
    settings = Settings(
        model_name="contract-model",
        model_endpoint="http://127.0.0.1/plans",
        approved_model_hosts=("127.0.0.1",),
    )
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply))
    ) as client:
        with pytest.raises(Failure) as error:
            PrivateHTTPModel(settings, client).plan("fictional", "{}", time.time() + 5)
        assert error.value.code == "MODEL_INVALID_JSON"


def test_missing_optional_driver_cli_error_is_safe(tmp_path):
    import subprocess
    import sys

    code = """
import sys
class BlockOracle:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'oracledb':
            raise ImportError('FICTIONAL_PRIVATE_DEPENDENCY_DETAIL')
sys.meta_path.insert(0, BlockOracle())
from nl2sql.__main__ import main
sys.argv = ['nl2sql','metadata','bootstrap','--source','oracle','--root',sys.argv[1]]
main()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "private")], capture_output=True, text=True
    )
    assert result.returncode == 1
    assert json.loads(result.stderr)["code"] == "OPTIONAL_DEPENDENCY"
    assert "PRIVATE" not in result.stderr and "Traceback" not in result.stderr


def test_startup_missing_optional_dependency_has_no_chained_details(settings):
    from fastapi.testclient import TestClient
    from nl2sql.api import create_app

    def unavailable(*_):
        raise ImportError("FICTIONAL_PRIVATE_DEPENDENCY_DETAIL")

    with (
        pytest.raises(Failure) as error,
        TestClient(create_app(settings, resources_factory=unavailable)),
    ):
        pass
    assert error.value.code == "OPTIONAL_DEPENDENCY"
    assert error.value.__suppress_context__ and "PRIVATE" not in str(error.value)
