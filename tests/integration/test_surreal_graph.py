"""Exercise the actual embedded engine, including durable reopen."""

import json
import os
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest
from nl2sql.application.catalog import JoinGraph
from nl2sql.domain.models import Catalog, Failure
from nl2sql.infrastructure.graph import SurrealGraph


def test_persistent_graph_and_filtered_traversal(tmp_path):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "catalog.surreal.json"
    with SurrealGraph.build(path, catalog) as graph:
        pairs = {(edge.left, edge.right) for edge in catalog.relations if edge.certified}
        for view in catalog.views:
            targets = {dim.table for dim in catalog.dimensions if dim.id in view.dimensions}
            assert JoinGraph(catalog, graph).resolve(view, targets) == JoinGraph(catalog).resolve(
                view, targets
            )
        edge = next(iter(pairs))
        assert graph.shortest_path(*edge, {edge}) == list(edge)
        assert graph.shortest_path(*edge, set()) == []
        assert graph.shortest_path(*edge, {edge}, edge) == []
        assert graph.lineage({"table:loans"}) >= {"table:loans", "metric:loan_exposure"}
    with SurrealGraph(path, catalog) as reopened:
        assert reopened.shortest_path(*edge, {edge}) == list(edge)
    with pytest.raises(Failure, match="unavailable"):
        graph.shortest_path(*edge, {edge})


@pytest.mark.parametrize("fresh", [False, True])
def test_two_real_readonly_processes_and_wrong_catalog(tmp_path, fresh):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "shared.surreal.json"
    with nullcontext() if fresh else SurrealGraph.build(path, catalog):
        code = """
import sys, time
from pathlib import Path
from nl2sql.domain.models import Catalog
from nl2sql.infrastructure.graph import SurrealGraph
catalog = Catalog.model_validate_json(Path(sys.argv[2]).read_text())
factory = SurrealGraph.build if sys.argv[3] == "True" else SurrealGraph
with factory(Path(sys.argv[1]), catalog) as graph:
    assert 'metric:loan_exposure' in graph.lineage({'table:loans'})
    time.sleep(0.2)
"""
        workers = [
            subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    code,
                    str(path),
                    "metadata/synthetic/catalog.json",
                    str(fresh),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(2)
        ]
        for worker in workers:
            output, error = worker.communicate(timeout=60)
            assert worker.returncode == 0, (output, error)
    with pytest.raises(Failure):
        SurrealGraph(path, catalog.model_copy(update={"version": "wrong"}))


def test_corruption_and_failed_build_do_not_publish(tmp_path, monkeypatch):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "bad.surreal.json"
    path.write_bytes(b"corrupt")
    with pytest.raises(Failure):
        SurrealGraph.build(path, catalog)
    assert path.read_bytes() == b"corrupt"
    path.unlink()

    def fail(*_args):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(SurrealGraph, "_populate", fail)
    with pytest.raises(Failure):
        SurrealGraph.build(path, catalog)
    assert not path.exists()
    assert not path.with_suffix(".building").exists()


@pytest.mark.parametrize("field", ["catalog", "nodes", "joins", "lineage", "format"])
def test_snapshot_tampering_fails_before_native_allocation(tmp_path, monkeypatch, field):
    from nl2sql.infrastructure.graph import snapshot

    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    payload = json.loads(snapshot(catalog))
    payload[field] = "tampered"
    path = tmp_path / "tampered.surreal.json"
    path.write_text(json.dumps(payload))
    original = path.read_bytes()

    def unexpected():
        pytest.fail("Unverified snapshot must not allocate a native store")

    monkeypatch.setattr("nl2sql.infrastructure.graph.open_projection", unexpected)
    with pytest.raises(Failure):
        SurrealGraph.build(path, catalog)
    assert path.read_bytes() == original


def test_independent_handles_survive_retirement(tmp_path):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "leases.surreal.json"
    old = SurrealGraph.build(path, catalog)
    with SurrealGraph(path, catalog) as current:
        old.close()
        old.close()
        assert "metric:loan_exposure" in current.lineage({"table:loans"})
    assert path.exists()


@pytest.mark.parametrize(
    "corruption",
    [
        "DELETE link WHERE kind='join'",
        "DELETE link WHERE kind='lineage'",
        "DELETE node",
        "UPDATE link SET pair='wrong' WHERE kind='join'",
    ],
)
def test_partial_native_population_is_not_published(tmp_path, monkeypatch, corruption):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    populate = SurrealGraph._populate

    def incomplete(self, approved):
        populate(self, approved)
        self._rows(corruption)

    monkeypatch.setattr(SurrealGraph, "_populate", incomplete)
    path = tmp_path / "incomplete.surreal.json"
    with pytest.raises(Failure):
        SurrealGraph.build(path, catalog)
    assert not path.exists()
    assert not path.with_suffix(".building").exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_engine_loads_without_external_graph_dll_directory(tmp_path):
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith(("NL2SQL_", "LBUG_", "SURREAL_")) or name in {
            "OPENSSL_CONF",
            "OPENSSL_MODULES",
        }:
            environment.pop(name)
    if os.name == "nt":
        environment["PATH"] = os.pathsep.join(
            (
                str(Path(sys.base_prefix)),
                str(Path(sys.base_prefix) / "DLLs"),
                str(Path(os.environ["SystemRoot"]) / "System32"),
            )
        )
    code = """
import sys
from pathlib import Path
from nl2sql.evaluation.synthetic import synthetic_catalog
from nl2sql.infrastructure.graph import SurrealGraph
from nl2sql.infrastructure.retrieval.vector_index import SurrealVectorIndex
with SurrealGraph.build(Path(sys.argv[1]), synthetic_catalog()) as graph:
    assert 'metric:loan_exposure' in graph.lineage({'table:loans'})
index = SurrealVectorIndex((('metric', (1.0, 0.0)),))
try:
    assert index.search((1.0, 0.0), {'metric'}) == (('metric', 1.0),)
finally:
    index.close()
assert 'ladybug' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "clean.surreal.json")],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
