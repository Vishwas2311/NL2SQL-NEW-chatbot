"""Native library contract fakes are explicit; no actual FAISS/model qualification."""

import math
from types import SimpleNamespace

import pytest
from nl2sql.infrastructure.retrieval.lexical import Retriever
from nl2sql.infrastructure.retrieval.vector_index import FaissVectorIndex, normalized

from tests.unit.test_retrieval_extensions import ToyEncoder


def test_faiss_guard_precedes_import(monkeypatch):
    def forbidden(_):
        raise AssertionError("Native import before approval")

    monkeypatch.setattr(
        "nl2sql.infrastructure.retrieval.vector_index.importlib.import_module", forbidden
    )
    with pytest.raises(ValueError, match="approval"):
        FaissVectorIndex((("metric", (1.0,)),))


def test_faiss_exact_normalization_scope_and_shape_contract(monkeypatch):
    class Flat:
        def __init__(self, dimension):
            assert dimension == 2

        def add(self, values):
            assert values == ((1.0, 0.0), (0.0, 1.0))

        def search(self, values, count):
            assert values == ((0.0, 1.0),) and count == 2
            return ((1.0, 0.25),), ((1, 0),)

    modules = {
        "faiss": SimpleNamespace(IndexFlatIP=Flat),
        "numpy": SimpleNamespace(ascontiguousarray=lambda values, dtype: values),
    }
    monkeypatch.setattr(
        "nl2sql.infrastructure.retrieval.vector_index.importlib.import_module", modules.__getitem__
    )
    index = FaissVectorIndex((("secret", (3.0, 0.0)), ("permitted", (0.0, 4.0))), approved=True)
    assert index.search((0.0, 2.0), {"permitted"}) == (("permitted", 1.0),)
    with pytest.raises(ValueError, match="dimension"):
        index.search((1.0,), {"permitted"})


@pytest.mark.parametrize("vector", [(), (0.0,), (math.inf,), (math.nan,), (1.0,) * 4097])
def test_native_vectors_reject_invalid_values(vector):
    with pytest.raises(ValueError):
        normalized(vector)


def test_injected_vector_index_is_partitioned_and_manifested(resources):
    partitions = []

    class Index:
        def __init__(self, entries):
            partitions.append(tuple(key for key, _ in entries))

        def search(self, vector, allowed):
            assert vector == (1.0, 0.0)
            assert allowed == {"account_count"}
            return (("account_count", 1.0),)

    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("account_count",)})
    retriever = Retriever(resources.service.compiler.catalog, (user,), ToyEncoder(), Index)
    try:
        assert partitions == [("account_count",)]
        assert retriever.vector_manifest()["backend"] == "faiss-flat-ip"
        assert retriever.retrieve("deposit tally", user)[0].metric_id == "account_count"
    finally:
        retriever.close()
