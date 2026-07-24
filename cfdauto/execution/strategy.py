"""ExecutionStrategy — how a template executes one case (Phase 7).

A strategy owns the *workflow*: given one experiment and an
:class:`~cfdauto.execution.context.ExecutionContext`, produce a
:class:`~cfdauto.models.CaseResult`. The orchestrator owns the *loop*
(resume, retries, ledger, cascade counter, result recording) and calls the
strategy per case — it never branches on which template/workflow is active.

The base also exposes two hooks the orchestrator's batch-resilience loop
consults, defaulting to benign no-ops so a strategy that has no notion of a
"launch failure" (e.g. a stub) inherits correct behaviour:

* :meth:`is_launch_failure` — was the case's recorded error a *recoverable*
  launch/licence failure (the signal the cascade detector counts)?
* :meth:`cleanup_after_cascade` — clean up once a cascade halt fires.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..models import CaseResult, Experiment
from .context import ExecutionContext


class ExecutionStrategy(ABC):
    """Template-owned execution workflow for a single case."""

    #: Stable id matching ``SimulationTemplate.execution_strategy_id`` and
    #: the key this strategy is registered under. Set by each subclass.
    strategy_id: str = ""

    @abstractmethod
    def execute_case(self, experiment: Experiment, context: ExecutionContext,
                     case_dir: Path) -> CaseResult:
        """Run one experiment end-to-end and return its result. May raise
        ``CaseError`` (this case failed, batch continues) or
        ``FrameworkError`` (abort the batch)."""
        raise NotImplementedError

    # -- batch-resilience hooks (safe defaults) ------------------------- #
    def is_launch_failure(self, experiment: Experiment,
                          context: ExecutionContext) -> bool:
        """Whether the just-recorded failure for ``experiment`` is a
        recoverable launch/licence failure the cascade detector should
        count. Default: never (no cascade)."""
        return False

    def cleanup_after_cascade(self, context: ExecutionContext) -> None:
        """Best-effort cleanup once the cascade detector halts the batch.
        Default: nothing to do."""
        return None
