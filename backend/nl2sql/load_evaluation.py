"""Repeatable application-service load measurements over independently checked synthetic rows."""

import statistics
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from nl2sql.api import Resources, build_resources
from nl2sql.config import load_settings
from nl2sql.domain import Failure, FrozenModel
from nl2sql.synthetic import initialize


class LoadSample(FrozenModel):
    """Queue and execution timings describe local application calls, not network/Oracle latency."""

    duration_ms: float
    pool_queue_ms: float
    worker_queue_ms: float
    correct: bool
    error_code: str | None = None
    spans: dict[str, float]


def _client(resources: Resources, barrier: Barrier, submitted: float) -> tuple[LoadSample, ...]:
    queued = (time.perf_counter() - submitted) * 1000
    barrier.wait(timeout=30)
    records: list[LoadSample] = []
    user = resources.auth.principals["analyst"]
    for _ in range(3):
        began = time.perf_counter()
        spans: dict[str, float] = {}
        error_code = None
        correct = False
        try:
            answer = resources.service.chat(
                "Show total loan exposure by region", None, user, None, spans
            )
            correct = answer.rows == (
                {"region": "Demo North", "loan_exposure": "175000.50"},
                {"region": "Demo South", "loan_exposure": "75000.00"},
            )
        except Failure as error:
            error_code = error.code
        records.append(
            LoadSample(
                duration_ms=(time.perf_counter() - began) * 1000,
                pool_queue_ms=spans.get("pool_queue_ms", 0),
                worker_queue_ms=queued,
                correct=correct,
                error_code=error_code,
                spans=spans,
            )
        )
    return tuple(records)


def evaluate_load(
    root: Path,
    levels: tuple[int, ...] = (1, 10, 25, 50),
    trace_memory: bool = True,
) -> dict[str, object]:
    """Three requests per simultaneous caller; each request owns a fresh persisted session."""
    if not levels or any(level < 1 or level > 50 for level in levels):
        raise ValueError("Load levels must be between 1 and 50")
    initialize(root / "data", root / "catalog.json")
    resources = build_resources(load_settings(root / "data/settings.json"))
    report: list[dict[str, object]] = []
    try:
        for level in levels:
            barrier = Barrier(level)
            if trace_memory:
                tracemalloc.start()
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=level) as workers:
                futures = [
                    workers.submit(_client, resources, barrier, time.perf_counter())
                    for _ in range(level)
                ]
                samples = [sample for future in futures for sample in future.result(timeout=60)]
            elapsed = time.perf_counter() - started
            peak = tracemalloc.get_traced_memory()[1] if trace_memory else None
            if trace_memory:
                tracemalloc.stop()
            latency = sorted(sample.duration_ms for sample in samples)
            queues = sorted(sample.pool_queue_ms for sample in samples)
            stage_p95 = {
                key: sorted(sample.spans.get(key, 0) for sample in samples)[
                    int((len(samples) - 1) * 0.95)
                ]
                for key in sorted(
                    {key for sample in samples for key in sample.spans if key.endswith("_ms")}
                )
            }
            report.append(
                {
                    "simultaneous_callers": level,
                    "requests": len(samples),
                    "correct_results": sum(sample.correct for sample in samples),
                    "errors": sum(sample.error_code is not None for sample in samples),
                    "p50_ms": statistics.median(latency),
                    "p95_ms": latency[int((len(latency) - 1) * 0.95)],
                    "pool_queue_p95_ms": queues[int((len(queues) - 1) * 0.95)],
                    "worker_queue_max_ms": max(sample.worker_queue_ms for sample in samples),
                    "peak_traced_python_bytes": peak,
                    "throughput_requests_per_second": len(samples) / elapsed,
                    "stage_p95_ms_nonadditive": stage_p95,
                }
            )
    finally:
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        resources.close()
    return {
        "scope": "synthetic application service, disabled model, four SQLite query connections",
        "network_load_measured": False,
        "python_tracing_enabled": trace_memory,
        "real_model_or_oracle_qualified": False,
        "levels": report,
    }
