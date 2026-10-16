"""Request context propagates through FastAPI's synchronous worker thread boundary."""

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter
from typing import ParamSpec, TypeVar

REQUEST_ID: ContextVar[str] = ContextVar("nl2sql_request_id", default="")
STAGE_SPANS: ContextVar[dict[str, float] | None] = ContextVar("nl2sql_stage_spans", default=None)
REQUEST_DEADLINE: ContextVar[float | None] = ContextVar("nl2sql_deadline", default=None)
P = ParamSpec("P")
R = TypeVar("R")


@contextmanager
def stage_metrics(spans: dict[str, float], deadline: float | None = None) -> Generator[None]:
    """Request-local timings cannot leak between reused worker threads."""
    token = STAGE_SPANS.set(spans)
    deadline_token = REQUEST_DEADLINE.set(deadline)
    try:
        yield
    finally:
        STAGE_SPANS.reset(token)
        REQUEST_DEADLINE.reset(deadline_token)


def measured(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Record only durations, including failures; never log method arguments or bind values."""

    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                spans = STAGE_SPANS.get()
                if spans is not None:
                    spans[name] = spans.get(name, 0) + (perf_counter() - started) * 1000

        return invoke

    return decorate
