"""Execution strategy registry — data-driven template → strategy dispatch
(Phase 7).

Maps a strategy id (``SimulationTemplate.execution_strategy_id``) to the
:class:`~cfdauto.execution.strategy.ExecutionStrategy` that runs it. The
runtime resolves a template's strategy through this registry —
``get_execution_strategy(template.execution_strategy_id)`` — and never with
an ``if template == external_aero`` check.

Registering a new workflow is one line here (mirroring the template
registry). Strategies are cheap and stateless, so one shared instance per id
is fine.
"""

from __future__ import annotations

from typing import Dict

from ..platform import SimulationTemplate
from .external_aerodynamics import ExternalAerodynamicsExecutionStrategy
from .internal_flow import InternalFlowExecutionStrategy
from .strategy import ExecutionStrategy

# id -> singleton strategy instance
_STRATEGIES: Dict[str, ExecutionStrategy] = {}


def register_strategy(strategy: ExecutionStrategy) -> None:
    """Register a strategy under its ``strategy_id`` (raises on a clash —
    silent clobbering would be a debugging hazard)."""
    if not strategy.strategy_id:
        raise ValueError(f"{type(strategy).__name__} has no strategy_id.")
    if strategy.strategy_id in _STRATEGIES:
        raise ValueError(
            f"Execution strategy id '{strategy.strategy_id}' already registered.")
    _STRATEGIES[strategy.strategy_id] = strategy


def get_execution_strategy(strategy_id: str) -> ExecutionStrategy:
    """Resolve a strategy by id; raises ``LookupError`` naming what exists."""
    try:
        return _STRATEGIES[strategy_id]
    except KeyError:
        raise LookupError(
            f"Unknown execution strategy '{strategy_id}'. "
            f"Available: {sorted(_STRATEGIES) or '(none)'}") from None


def strategy_for_template(template: SimulationTemplate) -> ExecutionStrategy:
    """The execution strategy a template owns (data-driven — no branching)."""
    return get_execution_strategy(template.execution_strategy_id)


def registered_ids() -> list[str]:
    return sorted(_STRATEGIES)


# --------------------------------------------------------------------------- #
# Built-in registration seam (Phase 8A) — the runtime counterpart of
# cfdauto.platform.registry.register_builtin_templates: a new built-in
# workflow is wired in here, without touching the dispatch core.
# --------------------------------------------------------------------------- #
def register_builtin_strategies() -> None:
    """Register the platform's built-in execution strategies (one shared,
    stateless instance per id). Additive: a new built-in strategy is wired in
    by editing this one function."""
    register_strategy(ExternalAerodynamicsExecutionStrategy())
    register_strategy(InternalFlowExecutionStrategy())


register_builtin_strategies()
