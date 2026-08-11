"""InternalFlowExecutionStrategy — an executable internal-flow workflow
(Capability 1).

Phase 7 shipped this as a stub that proved the strategy *plugs in*. This
sprint makes it *run*: a second, physically distinct CFD workflow now
executes end-to-end through the very same execution framework that drives
External Aerodynamics — with no change to the generic loop, the adapters,
the context/result objects, or the ``Experiment``/``CaseResult`` model.

The per-case workflow
---------------------
1. **Mesh phase** (geometry) — reuse the existing :class:`MeshBackend`
   adapter (the Workbench controller) exactly as External Aerodynamics does,
   including :class:`~cfdauto.state.RunState`'s per-geometry mesh cache, so a
   velocity sweep meshes the pipe once and reuses it. Skipped when no mesh
   backend is available.
2. **Solve phase** — a *minimal, analytical* internal-flow solve
   (Reynolds number → friction factor → Darcy–Weisbach pressure drop). No
   internal-flow Fluent setup exists yet, so this stands in for the solver
   exactly as the vision allows ("Fluent *or* minimal placeholder
   workflow"). The :class:`SolverBackend` seam is unchanged and ready for a
   real internal-flow Fluent adapter to drop in later — only this file would
   change.

The result is a generic :class:`~cfdauto.models.CaseResult` whose
``metrics`` are filled straight from the template's declared
:class:`MetricDefinition`\\ s (``pressure_drop``, ``reynolds_number``,
``friction_factor``) — the strategy never hardcodes which metrics a template
has, it asks the template.

Generic identity — Phase 8A
---------------------------
``Experiment.case_id`` / ``geometry_key`` / ``validate`` are driven by the
template contract (see ``docs/PLATFORM_ARCHITECTURE.md``): identity is every
study input, geometry is the pipe dimensions (the declared
``geometry_parameters``), and validation is each parameter's own
:class:`~cfdauto.platform.parameters.ParameterDefinition`. Internal-flow
experiments are built through the generic
:meth:`~cfdauto.experiment_definition.ExperimentDefinition.build_experiment`
path with no airfoil-shaped slots — there is no bridge between this workflow
and External Aerodynamics, and no ``aoa`` is fabricated anywhere.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ..models import CaseResult, Experiment, MetricValue
from .context import ExecutionContext
from .strategy import ExecutionStrategy

log = logging.getLogger("cfdauto.execution.internal_flow")

# Study parameter names (match cfdauto.platform.internal_flow). These are the
# keys generic construction stores under each experiment's parameters, and the
# keys solve_internal_flow reads back out.
_INLET_VELOCITY = "inlet_velocity"
_FLUID_DENSITY = "fluid_density"
_FLUID_VISCOSITY = "fluid_viscosity"
_PIPE_DIAMETER = "pipe_diameter"
_PIPE_LENGTH = "pipe_length"
_STUDY_PARAMETERS = (_INLET_VELOCITY, _FLUID_DENSITY, _FLUID_VISCOSITY,
                     _PIPE_DIAMETER, _PIPE_LENGTH)

# Reynolds number above which the flow is treated as turbulent (below is the
# laminar Hagen–Poiseuille branch). The classic pipe-flow transition value.
_LAMINAR_RE_LIMIT = 2300.0


# --------------------------------------------------------------------------- #
# Input read-back — generic construction stores every study input under its
# own parameter name, so reading them out is a straight parameter read (no
# bridging slots, no airfoil aliases).
# --------------------------------------------------------------------------- #
def internal_flow_inputs(exp: Experiment) -> Dict[str, float]:
    """Read an internal-flow experiment's physical inputs back out as a clean
    name→value dict — so the solve stays free of airfoil-named fields.

    Phase 8A: experiments are built through the generic
    :meth:`~cfdauto.experiment_definition.ExperimentDefinition.build_experiment`
    path, which stores every study input under its own parameter name in
    ``exp.parameters``. This is therefore a straight read — there is no
    ``velocity`` alias and no fabricated ``aoa`` to translate.
    """
    params = exp.parameters_dict()
    missing = [name for name in _STUDY_PARAMETERS if name not in params]
    if missing:
        raise KeyError(
            f"Internal-flow experiment (row {exp.row}) is missing input(s): "
            f"{', '.join(sorted(missing))}.")
    return {name: float(params[name]) for name in _STUDY_PARAMETERS}


# --------------------------------------------------------------------------- #
# The minimal internal-flow "solver": textbook incompressible pipe flow.
# --------------------------------------------------------------------------- #
def solve_internal_flow(inputs: Dict[str, float]) -> Dict[str, float]:
    """Compute the internal-flow metrics from one experiment's inputs.

    * Reynolds number ``Re = ρ V D / μ``.
    * Darcy friction factor — laminar ``f = 64/Re`` (Hagen–Poiseuille) below
      the transition Reynolds number, else the Blasius smooth-pipe
      correlation ``f = 0.3164 Re^-0.25``.
    * Pressure drop — Darcy–Weisbach ``Δp = f (L/D) ½ ρ V²``.

    Returns a name→value dict keyed by the template's metric names. Deliberate
    placeholder physics: enough to validate the execution framework
    end-to-end, not an industrial internal-flow model.
    """
    v = inputs[_INLET_VELOCITY]
    rho = inputs[_FLUID_DENSITY]
    mu = inputs[_FLUID_VISCOSITY]
    d = inputs[_PIPE_DIAMETER]
    length = inputs[_PIPE_LENGTH]

    reynolds = rho * v * d / mu
    if reynolds < _LAMINAR_RE_LIMIT:
        friction = 64.0 / reynolds if reynolds > 0 else float("inf")
    else:
        friction = 0.3164 * reynolds ** -0.25
    pressure_drop = friction * (length / d) * 0.5 * rho * v * v

    return {
        "reynolds_number": reynolds,
        "friction_factor": friction,
        "pressure_drop": pressure_drop,
    }


class InternalFlowExecutionStrategy(ExecutionStrategy):
    strategy_id = "internal-flow"

    # -- per-case workflow --------------------------------------------- #
    def execute_case(self, experiment: Experiment, context: ExecutionContext,
                     case_dir: Path) -> CaseResult:
        """Mesh phase (with cache, if a mesh backend is present) + minimal
        analytical solve for one internal-flow case."""
        started = datetime.now()
        mesh = self._mesh_for(experiment, context, case_dir)

        inputs = internal_flow_inputs(experiment)
        values = solve_internal_flow(inputs)
        log.info("[internal-flow] row %d: V=%.4g m/s, D=%.4g m, L=%.4g m → "
                 "Re=%.1f, f=%.5f, dp=%.2f Pa", experiment.row,
                 inputs[_INLET_VELOCITY], inputs[_PIPE_DIAMETER],
                 inputs[_PIPE_LENGTH], values["reynolds_number"],
                 values["friction_factor"], values["pressure_drop"])

        # Fill exactly the template's declared metrics from the solved values
        # (data-driven — the strategy never hardcodes which metrics exist).
        metrics: Dict[str, MetricValue] = {}
        for m in context.template.supported_metrics:
            v = values.get(m.name)
            metrics[m.name] = MetricValue(
                m.name, None if v is None else round(float(v), 6), m.unit)

        # Phase 8B: attach the template + case identity so the result
        # serializes through the *generic* CaseResult path (template id,
        # parameters, template-defined metrics, bookkeeping) — never the
        # airfoil-shaped legacy shape.
        res = CaseResult(
            metrics=metrics, iterations=1, converged=True,
            started=started, finished=datetime.now(),
            mesh_file=str(mesh or ""), artifact_dir=str(case_dir),
            template=context.template, case_id=experiment.case_id,
            parameters=experiment.parameters_dict())
        return res

    # -- mesh phase (mirrors ExternalAerodynamics, geometry-only key) --- #
    def _mesh_for(self, exp: Experiment, context: ExecutionContext,
                  case_dir: Path) -> Optional[Path]:
        """Prepare (or reuse) the pipe mesh via the Workbench adapter. Returns
        None when no mesh backend is configured — the analytical solve does
        not require a mesh, so internal flow degrades gracefully."""
        if context.mesh_backend is None:
            return None
        if context.config.runtime.reuse_mesh_per_geometry:
            cached = context.state.cached_mesh(exp.geometry_key)
            if cached:
                log.info("Mesh cache hit for geometry '%s' → %s "
                         "(Workbench skipped).", exp.geometry_key, cached.name)
                context.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                                 stage="mesh", state="cached")
                context.bus.emit("mesh.ready", row=exp.row, case_id=exp.case_id,
                                 path=str(cached), cache_hit=True)
                return cached
        fresh = context.mesh_backend.prepare_mesh(exp, case_dir)
        return context.state.store_mesh(exp.geometry_key, fresh, exp)
