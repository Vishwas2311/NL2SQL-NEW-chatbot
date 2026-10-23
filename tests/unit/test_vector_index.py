"""Real embedded Ladybug vectors: no FAISS dependency or fake native qualification."""

import math

import pytest
from nl2sql.domain.models import Failure
from nl2sql.infrastructure.retrieval.lexical import Retriever
from nl2sql.infrastructure.retrieval.vector_index import LadybugVectorIndex, normalized

from tests.unit.test_retrieval_extensions import ToyEncoder


def test_ladybug_vector_filtering_precedes_limit_and_cleanup():
    entries = tuple((f"hidden{i}", (1.0, 0.0)) for i in range(110)) + (("permitted", (0.1, 1.0)),)
    index = LadybugVectorIndex(entries)
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


def test_configured_encoder_builds_ladybug_projection_automatically(resources):
    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("account_count",)})
    retriever = Retriever(resources.service.compiler.catalog, (user,), ToyEncoder())
    try:
        assert isinstance(next(iter(retriever._native_indexes.values())), LadybugVectorIndex)
        assert retriever.vector_manifest()["backend"] == "ladybug-exact-cosine"
        assert retriever.retrieve("deposit tally", user)[0].metric_id == "account_count"
    finally:
        retriever.close()
