"""Shared search preparation failures release resources and wake every caller."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from nl2sql.bootstrap import runtime
from nl2sql.infrastructure.retrieval.embeddings import FakeEmbedding, ManagedEncoder


def test_checkpoint_failure_closes_search_and_wakes_waiter(settings, monkeypatch):
    entered, release, waiting = Event(), Event(), Event()
    created = []

    class Search:
        closed = False

        def close(self):
            self.closed = True

    def prepare(*_args):
        search = Search()
        created.append(search)
        return search

    def checkpoint(_texts):
        entered.set()
        assert release.wait(5)
        raise RuntimeError("synthetic checkpoint failure")

    encoder = ManagedEncoder(settings, FakeEmbedding(settings.embedding_dimension))
    monkeypatch.setattr(encoder, "checkpoint", checkpoint)
    monkeypatch.setattr(runtime, "Retriever", prepare)
    factory = runtime.RuntimeFactory(
        settings.model_copy(update={"request_timeout_seconds": 1}),
        None,
        None,
        encoder,
        "synthetic-1",
        inference_admission=None,
    )
    catalog = runtime.Catalog.model_validate_json(settings.catalog_path.read_text())
    try:
        with ThreadPoolExecutor(2) as workers:
            first = workers.submit(factory._search, catalog, settings.principals)
            try:
                assert entered.wait(5)
                shared = next(iter(factory._searches.values())).future
                original = shared.result

                def wait(timeout=None):
                    waiting.set()
                    return original(timeout)

                monkeypatch.setattr(shared, "result", wait)
                second = workers.submit(factory._search, catalog, settings.principals)
                assert waiting.wait(5)
            finally:
                release.set()
            for task in (first, second):
                with pytest.raises(RuntimeError, match="synthetic checkpoint failure"):
                    task.result(timeout=5)
        assert created[0].closed
        assert not factory._searches
        monkeypatch.setattr(encoder, "checkpoint", lambda _texts: None)
        search, retire = factory._search(catalog, settings.principals)
        assert search is created[1] and not search.closed
        retire()
        assert search.closed and not factory._searches
    finally:
        release.set()
        for search in created:
            search.close()
