"""Exercise the actual embedded engine, including durable reopen."""

import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path

import pytest
from nl2sql.application.catalog import JoinGraph
from nl2sql.domain.models import Catalog, Failure
from nl2sql.infrastructure.graph import LadybugGraph


def test_persistent_graph_and_filtered_traversal(tmp_path):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "catalog.lbdb"
    with LadybugGraph.build(path, catalog) as graph:
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
    with LadybugGraph(path, catalog) as reopened:
        assert reopened.shortest_path(*edge, {edge}) == list(edge)
    with pytest.raises(Failure, match="unavailable"):
        graph.shortest_path(*edge, {edge})


@pytest.mark.parametrize("fresh", [False, True])
def test_two_real_readonly_processes_and_wrong_catalog(tmp_path, fresh):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "shared.lbdb"
    with nullcontext() if fresh else LadybugGraph.build(path, catalog):
        code = """
import os, sys, time
from pathlib import Path
from nl2sql.domain.models import Catalog
from nl2sql.infrastructure.graph import LadybugGraph
catalog = Catalog.model_validate_json(Path(sys.argv[2]).read_text())
native = os.environ.get('NL2SQL_TEST_GRAPH_NATIVE_DIR')
factory = LadybugGraph.build if sys.argv[3] == "True" else LadybugGraph
with factory(Path(sys.argv[1]), catalog, native_dir=Path(native) if native else None) as graph:
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
        LadybugGraph(path, catalog.model_copy(update={"version": "wrong"}))


def test_corruption_and_failed_build_do_not_publish(tmp_path, monkeypatch):
    catalog = Catalog.model_validate_json(Path("metadata/synthetic/catalog.json").read_text())
    path = tmp_path / "bad.lbdb"
    path.write_bytes(b"corrupt")
    with pytest.raises(Failure):
        LadybugGraph.build(path, catalog)
    assert path.read_bytes() == b"corrupt"
    path.unlink()

    def fail(*_args):
        raise ValueError("synthetic failure")

    monkeypatch.setattr(LadybugGraph, "_populate", fail)
    with pytest.raises(Failure):
        LadybugGraph.build(path, catalog)
    assert not path.exists()
    assert not path.with_suffix(".building").exists()
