"""Opt-in foreground refresh runner with a deterministic tick seam for tests."""

import logging
import time
from collections.abc import Callable
from threading import Event

from nl2sql.domain import Failure, FrozenModel
from nl2sql.metadata_workflow import MetadataWorkflow, StageOutcome


class RefreshResult(FrozenModel):
    """No provider messages or private schema names enter routine scheduling telemetry."""

    ran: bool
    attempts: int = 0
    outcome: StageOutcome | None = None
    error_code: str | None = None


class MetadataRefreshService:
    """No threads are spawned automatically; deployment chooses one approved scheduler."""

    def __init__(
        self,
        workflow: MetadataWorkflow,
        clock: Callable[[], float] = time.time,
        wait: Callable[[float], None] = time.sleep,
        retries: int = 1,
    ) -> None:
        if not 0 <= retries <= 2:
            raise ValueError("Metadata refresh retries must be bounded")
        self.workflow = workflow
        self.clock = clock
        self.wait = wait
        self.retries = retries

    def tick(self) -> RefreshResult:
        """Claim due work atomically, stage changes, and never auto-approve or publish."""
        try:
            with self.workflow.repository.refresh_lease(name="schedule"):
                return self._tick()
        except Failure as error:
            if error.code != "REFRESH_BUSY":
                raise
            return RefreshResult(ran=False)

    def _tick(self) -> RefreshResult:
        """Keep dry-run discoveries under the same cross-process scheduler lease."""
        dry_run = self.workflow.repository.claim_schedule(self.clock())
        if dry_run is None:
            return RefreshResult(ran=False)
        for attempt in range(self.retries + 1):
            try:
                return RefreshResult(
                    ran=True, attempts=attempt + 1, outcome=self.workflow.stage(dry_run=dry_run)
                )
            except (Failure, OSError, ValueError) as error:
                code = error.code if isinstance(error, Failure) else type(error).__name__
                if (
                    code not in {"DISCOVERY_UNAVAILABLE", "DISCOVERY_TIMEOUT", "REFRESH_BUSY"}
                    or attempt == self.retries
                ):
                    self.workflow.repository.record_failure(code)
                    return RefreshResult(ran=True, attempts=attempt + 1, error_code=code)
                self.wait(min(2**attempt, 4))
        raise AssertionError("Bounded retry loop did not return")

    def run(self, stop: Event) -> None:
        """Foreground only; use company-approved services/cron/Task Scheduler in deployment."""
        while not stop.is_set():
            result = self.tick()
            if result.error_code or (result.outcome and result.outcome.issues):
                logging.getLogger(__name__).warning(
                    "metadata_refresh_attention error=%s issues=%d",
                    result.error_code or "COMPATIBILITY_REVIEW",
                    len(result.outcome.issues) if result.outcome else 0,
                )
            stop.wait(1)
