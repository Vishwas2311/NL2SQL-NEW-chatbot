"""Bound inference independently from the complete chat turn."""

import time

from nl2sql.application.ports import ModelProvider, ModelResult, RateLimiter
from nl2sql.domain.models import Failure, Principal


class InferencePlanner:
    """One process-shared admission handle, including across catalog replacements."""

    def __init__(self, provider: ModelProvider, admission: RateLimiter) -> None:
        self.provider = provider
        self.admission = admission

    def plan(
        self, question: str, context: str, deadline: float, principal: Principal
    ) -> ModelResult:
        """Reject excess work promptly and release the slot on every provider outcome."""
        if time.time() >= deadline:
            raise Failure("REQUEST_TIMEOUT", "The request deadline expired.", "timeout")
        try:
            with self.admission.chat(principal):
                return self.provider.plan(question, context, deadline)
        except Failure as error:
            if error.code == "CHAT_CAPACITY":
                raise Failure(
                    "INFERENCE_CAPACITY", "Model capacity is busy; please retry shortly.", "busy"
                ) from None
            raise
