"""Template-aware execution framework (Universal Platform, Phase 7).

Execution — *how* a study runs — is owned by the template's
:class:`ExecutionStrategy`, resolved data-driven through the strategy
registry. The orchestrator keeps the generic batch loop (resume, retries,
ledger, cascade, result recording) and delegates the per-case workflow to
the strategy; it never branches on which template is active.

* :class:`ExecutionStrategy` — the per-case workflow (+ cascade hooks).
* :class:`ExecutionContext` — everything a strategy needs to run.
* :class:`ExecutionResult` — the standard batch outcome.
* :class:`MeshBackend` / :class:`SolverBackend` — the adapter seams
  (Workbench / Fluent controllers structurally satisfy them).

Dependency direction: ``orchestrator`` → ``execution`` → (``platform``,
``models``, ``state``, …); the platform layer imports none of this.
"""

from .adapters import MeshBackend, SolverBackend          # noqa: F401
from .context import ExecutionContext                     # noqa: F401
from .external_aerodynamics import (                       # noqa: F401
    ExternalAerodynamicsExecutionStrategy,
)
from .internal_flow import (                               # noqa: F401
    InternalFlowExecutionStrategy,
    build_internal_flow_experiment,
    internal_flow_inputs,
    solve_internal_flow,
)
from .registry import (                                    # noqa: F401
    get_execution_strategy,
    register_strategy,
    registered_ids,
    strategy_for_template,
)
from .result import ExecutionResult                        # noqa: F401
from .strategy import ExecutionStrategy                    # noqa: F401
