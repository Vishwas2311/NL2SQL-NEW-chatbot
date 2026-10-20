"""Independent retrieval ablations; no model calls or generated SQL enter these measurements."""

import statistics
import time
from collections.abc import Callable

from nl2sql.application.catalog import JoinGraph
from nl2sql.application.ports import Candidate, EmbeddingProvider
from nl2sql.domain.models import Catalog, Failure, Principal
from nl2sql.evaluation.workflow import golden_cases
from nl2sql.infrastructure.retrieval.lexical import Retriever


def _connected(catalog: Catalog, candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    graph = JoinGraph(catalog)
    metrics = {metric.id: metric for metric in catalog.metrics}
    result: list[Candidate] = []
    for candidate in candidates:
        metric = metrics[candidate.metric_id]
        for view in catalog.views:
            if metric.id in view.metrics and not view.components:
                try:
                    graph.resolve(
                        view,
                        {
                            metric.table,
                            *(
                                dimension.table
                                for dimension in catalog.dimensions
                                if dimension.id in view.dimensions
                            ),
                        },
                    )
                except Failure:
                    continue
                result.append(candidate)
                break
    return tuple(result)


def evaluate_retrieval(
    catalog: Catalog, principals: tuple[Principal, ...], encoder: EmbeddingProvider | None = None
) -> dict[str, object]:
    """Use the same held-fixed authored questions and expected metric IDs for every ablation."""
    users = {user.id: user for user in principals}
    modes: dict[str, dict[str, object]] = {}
    lexical = Retriever(catalog, principals)
    hybrid = Retriever(catalog, principals, encoder) if encoder is not None else None
    experiments: dict[str, Callable[[str, Principal], tuple[Candidate, ...]]] = {
        "exact_only": lambda text, user: tuple(
            c for c in lexical.retrieve(text, user) if c.method == "exact"
        ),
        "exact_bm25": lexical.retrieve,
        "graph_filtered": lambda text, user: _connected(catalog, lexical.retrieve(text, user)),
    }
    if hybrid is not None:
        experiments["hybrid"] = hybrid.retrieve
    questions = [
        (case.question, case.principal, set(case.draft.metrics))
        for case in golden_cases(catalog.version)
        if case.draft is not None and case.expected_error is None
    ]
    questions.extend(
        (
            ("active fictional accounts now", "analyst", {"account_count"}),
            ("credit snapshot principal totals", "analyst", {"loan_exposure"}),
            (
                "half open business date intervals",
                "analyst",
                {"payment_amount", "payment_fee", "payment_count"},
            ),
            ("missing aggregates", "analyst", {"net_payments"}),
            ("zero denominator", "analyst", {"fee_rate"}),
        )
    )
    try:
        for name, search in experiments.items():
            precision: list[float] = []
            recall: list[float] = []
            table_recall: list[float] = []
            latencies: list[float] = []
            violations = 0
            metric_tables = {metric.id: metric.table for metric in catalog.metrics}
            for question, identity, expected in questions:
                began = time.perf_counter()
                candidates = search(question, users[identity])[:10]
                latencies.append((time.perf_counter() - began) * 1000)
                actual = {candidate.metric_id for candidate in candidates}
                precision.append(len(actual & expected) / len(actual) if actual else 0)
                recall.append(len(actual & expected) / len(expected))
                tables = {metric_tables[key] for key in actual}
                expected_tables = {metric_tables[key] for key in expected}
                table_recall.append(len(tables & expected_tables) / len(expected_tables))
                violations += len(actual - set(users[identity].metrics))
            times = sorted(latencies)
            modes[name] = {
                "questions": len(recall),
                "precision_at_10": statistics.mean(precision),
                "recall_at_10": statistics.mean(recall),
                "metric_source_table_recall_at_10": statistics.mean(table_recall),
                "authorization_violations": violations,
                "p50_ms": statistics.median(times),
                "p95_ms": times[int((len(times) - 1) * 0.95)],
            }
    finally:
        lexical.close()
        if hybrid is not None:
            hybrid.close()
    return {
        "modes": modes,
        "model_calls": 0,
        "k": 10,
        "qualification": "authored synthetic retrieval fixtures; no real model accuracy",
        "hybrid": "measured" if encoder is not None else "not_run_no_approved_encoder",
    }
