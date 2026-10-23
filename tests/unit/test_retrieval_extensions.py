"""Optional encoder plumbing is synthetic evidence, never semantic model accuracy."""

import math
from datetime import date

import pytest
from nl2sql.application.catalog import JoinGraph, validate_catalog
from nl2sql.application.query.planning import PlanValidator
from nl2sql.domain.models import Failure, Period
from nl2sql.evaluation.experiments import compare_retrieval
from nl2sql.infrastructure.retrieval.lexical import Retriever

from tests.integration.test_pipeline import plan_for


class ToyEncoder:
    """Controlled vectors test fusion/scope; this is not an embedding model."""

    def __init__(self):
        self.inputs = []
        self.invalid = False

    def encode(self, texts):
        self.inputs.extend(texts)
        if self.invalid:
            return ((math.nan,),)
        return tuple(
            (1.0, 0.0) if "account" in text.lower() or "deposit" in text.lower() else (0.0, 1.0)
            for text in texts
        )


def test_hybrid_search_and_authorized_metadata_only(resources):
    catalog = resources.service.compiler.catalog
    user = resources.auth.principals["analyst"].model_copy(update={"metrics": ("account_count",)})
    encoder = ToyEncoder()
    retriever = Retriever(catalog, (user,), encoder)
    try:
        assert all("Loan exposure" not in text for text in encoder.inputs)
        candidate = retriever.retrieve("deposit tally", user)[0]
        assert candidate.metric_id == "account_count" and candidate.method == "hybrid_rrf"
        assert retriever.retrieve("loan exposure", user, domain="lending") == ()
        assert retriever.retrieve("account count", user)[0].method == "exact"
    finally:
        retriever.close()


@pytest.mark.parametrize(
    "question,key",
    [
        ("EOP exposure", "loan_exposure"),
        ("outstanding exposure", "loan_exposure"),
        ("mean loan exposure", "average_exposure"),
        ("fee percentage", "fee_rate"),
    ],
)
def test_synonyms_and_nested_exact_spans(resources, question, key):
    user = resources.auth.principals["analyst"]
    assert [item.metric_id for item in resources.retriever.retrieve(question, user)] == [key]


def test_shared_alias_clarifies_even_with_a_covering_view(resources):
    catalog = resources.service.compiler.catalog
    metrics = tuple(
        metric.model_copy(update={"aliases": (*metric.aliases, "position")})
        if metric.id in {"loan_exposure", "loan_count"}
        else metric
        for metric in catalog.metrics
    )
    retriever = Retriever(
        catalog.model_copy(update={"metrics": metrics}), tuple(resources.auth.principals.values())
    )
    original = resources.service.retriever
    resources.service.retriever = retriever
    try:
        before = resources.model.calls
        result = resources.service.chat(
            "Show position", None, resources.auth.principals["analyst"], None, {}
        )
        assert result.status == "clarification_required"
        assert resources.model.calls == before and resources.database.execute_count == 0
    finally:
        resources.service.retriever = original
        retriever.close()


def test_encoder_failures_fall_back_or_fail_safely(resources):
    catalog = resources.service.compiler.catalog
    user = resources.auth.principals["analyst"]
    encoder = ToyEncoder()
    retriever = Retriever(catalog, (user,), encoder)
    encoder.invalid = True
    try:
        assert retriever.retrieve("fictional", user)[0].method == "bm25"
        with pytest.raises(Failure, match="unavailable"):
            retriever.retrieve("xyzqz", user)
    finally:
        retriever.close()
    with pytest.raises(ValueError, match="shape"):
        Retriever(catalog, (user,), encoder)
    empty = user.model_copy(update={"metrics": ()})
    restricted = Retriever(catalog, (empty,), encoder)
    try:
        assert restricted.retrieve("deposit", empty) == ()
    finally:
        restricted.close()


def test_historical_current_only_relationship_fails_closed(resources):
    catalog = resources.service.compiler.catalog
    edge = catalog.relations[0].model_copy(update={"temporal": "current_only"})
    changed = catalog.model_copy(update={"relations": (edge, *catalog.relations[1:])})
    validate_catalog(changed)
    with pytest.raises(Failure, match="historical"):
        PlanValidator(changed).validate(
            plan_for(resources, period=Period(as_of=date(2025, 9, 30))),
            resources.auth.principals["analyst"],
        )
    assert JoinGraph(changed).resolve(changed.views[0], {"regions"})


def test_paired_harness_uses_identical_corpus_and_business_goldens(tmp_path):
    report = compare_retrieval(tmp_path, ToyEncoder(), "synthetic-toy-not-a-model")
    lexical, hybrid = report["lexical"], report["hybrid"]
    assert lexical["distinct_questions"] == hybrid["distinct_questions"] == 46
    assert lexical["catalog_digest"] == hybrid["catalog_digest"]
    assert lexical["correct_results"] == hybrid["correct_results"] == 37
    assert lexical["safe_rejection_rate"] == 1
    # The toy encoder incorrectly retrieves an out-of-domain question. Report that regression.
    assert hybrid["safe_rejection_rate"] == 8 / 9
    unknown = next(item for item in hybrid["cases"] if item["id"] == "unsupported")
    assert unknown["status"] == "MODEL_INVALID_JSON" and unknown["database_calls"] == 0
    assert [item["id"] for item in lexical["cases"]] == [item["id"] for item in hybrid["cases"]]
    with pytest.raises(ValueError, match="identity"):
        compare_retrieval(tmp_path / "invalid", ToyEncoder())
