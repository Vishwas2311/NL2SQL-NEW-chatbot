"""Reject oversized authorized projections before encoding or native allocation."""

import pytest
from nl2sql.domain.models import Failure
from nl2sql.domain.search import SearchRecord
from nl2sql.evaluation.synthetic import synthetic_catalog
from nl2sql.infrastructure.retrieval.lexical import Retriever
from nl2sql.settings import RetrievalOptions


def test_schema_text_counts_toward_preflight(settings, monkeypatch):
    metric = settings.principals[0].metrics[0]
    record = SearchRecord(
        id="column:large",
        kind="column",
        catalog_version="synthetic-v1",
        domain="lending",
        description="large",
        metric_scope=(metric,),
        embedding_text="x" * 6000,
    )
    monkeypatch.setattr(
        "nl2sql.infrastructure.retrieval.lexical.schema_records", lambda _: (record,)
    )
    with pytest.raises(Failure) as error:
        Retriever(
            synthetic_catalog(), settings.principals, options=RetrievalOptions(max_text_bytes=5000)
        )
    assert error.value.code == "BUNDLE_LIMIT"


def test_native_partition_budget_precedes_encoding(settings):
    class Encoder:
        def encode(self, _texts):
            pytest.fail("Budget must reject before encoding")

    users = tuple(
        settings.principals[0].model_copy(update={"id": str(i), "metrics": (metric.id,)})
        for i, metric in enumerate(synthetic_catalog().metrics[:2])
    )
    with pytest.raises(Failure) as error:
        Retriever(synthetic_catalog(), users, Encoder(), RetrievalOptions(max_native_mb=32))
    assert error.value.code == "BUNDLE_LIMIT"
