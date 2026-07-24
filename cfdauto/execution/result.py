"""ExecutionResult — the standard outcome of executing a study (Phase 7).

A single, transport-friendly summary of a batch run: status, case counts,
duration, artifact locations, and log locations. Today the orchestrator
still returns its integer failure count for backward compatibility and
*additionally* builds one of these (exposed via
``Orchestrator.execution_result``); the object exists to give future
distributed/remote execution a uniform result to serialize and return.

Pure data holder; no behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# Batch outcome vocabulary.
STATUS_COMPLETED = "completed"    # every queued case ran (some may have failed)
STATUS_STOPPED = "stopped"        # halted early (user stop / cascade / stop_on_failure)
STATUS_NOTHING_TO_DO = "nothing_to_do"


@dataclass
class ExecutionResult:
    """Standard result of one :meth:`Orchestrator.run` call."""

    status: str
    completed_cases: int = 0
    failed_cases: int = 0
    duration_s: float = 0.0
    artifacts: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    @property
    def total_cases(self) -> int:
        return self.completed_cases + self.failed_cases

    @property
    def ok(self) -> bool:
        """True when the batch finished with no failed cases."""
        return self.failed_cases == 0
