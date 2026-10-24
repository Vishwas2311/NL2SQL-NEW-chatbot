"""Real embedded Surreal vectors: no FAISS dependency or fake native qualification."""

import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.retrieval.lexical import Retriever
from nl2sql.infrastructure.retrieval.vector_index import SurrealVectorIndex, normalized

from tests.unit.test_retrieval_extensions import ToyEncoder


def test_surreal_vector_filtering_precedes_limit_and_cleanup():
    entries = tuple((f"hidden{i}", (1.0, 0.0)) for i in range(110)) + (("permitted", (0.1, 1.0)),)
    index = SurrealVectorIndex(entries)
    try:
        found = index.search((1.0, 0.0), {"permitted"})
        assert len(found) == 1 and found[0][0] == "permitted"
        assert found[0][1] == pytest.approx(0.099503719)
        assert index.search((1.0, 0.0), set()) == ()
        with pytest.raises(ValueError, match="dimension"):
            index.search((1.0,), {"permitted"})
    finally:
        index.close()
    index.close()
    with pytest.raises(Failure, match="closed"):
        index.search((1.0, 0.0), {"permitted"})


@pytest.mark.parametrize("vector", [(), (0.0,), (math.inf,), (math.nan,), (1.0,) * 4097])
def test_native_vectors_reject_invalid_values(vector):
    with pytest.raises(ValueError):
        normalized(vector)


def test_configured_encoder_builds_surreal_projection_automatically(resources):
    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("account_count",)})
    retriever = Retriever(resources.service.compiler.catalog, (user,), ToyEncoder())
    try:
        assert isinstance(next(iter(retriever._native_indexes.values())), SurrealVectorIndex)
        assert retriever.vector_manifest()["backend"] == "surreal-exact-cosine"
        assert retriever.retrieve("deposit tally", user)[0].metric_id == "account_count"
    finally:
        retriever.close()


def test_concurrent_scopes_bound_keys_ties_and_store_isolation():
    key = "metric:'; DELETE metric; --"
    index = SurrealVectorIndex(((key, (1.0, 0.0)), ("a", (1.0, 0.0))))
    other = SurrealVectorIndex((("other", (0.0, 1.0)),))
    try:

        def search(i):
            allowed = {key} if i % 2 else {"a"}
            return index.search((1.0, 0.0), allowed)

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = tuple(pool.map(search, range(20)))
        assert all(rows == (((key if i % 2 else "a"), 1.0),) for i, rows in enumerate(results))
        assert index.search((1.0, 0.0), {key, "a"}) == (("a", 1.0), (key, 1.0))
        assert other.search((0.0, 1.0), {key, "a"}) == ()
        index.close()
        assert other.search((0.0, 1.0), {"other"}) == (("other", 1.0),)
    finally:
        index.close()
        other.close()


@pytest.mark.parametrize(
    "entries", [(), (("a", (1.0,)), ("a", (1.0,))), (("a", (1.0,)), ("b", (1.0, 0.0)))]
)
def test_invalid_partitions_fail_before_allocation(entries):
    with pytest.raises(ValueError):
        SurrealVectorIndex(entries)
