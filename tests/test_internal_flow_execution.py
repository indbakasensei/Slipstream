"""Capability 1 — executable Internal Flow workflow (Phase 8A, generic).

The Internal Flow strategy executes end-to-end through the *same* execution
framework as External Aerodynamics (mesh via the Workbench adapter + a
minimal analytical pipe-flow solve), producing generic :class:`CaseResult`
objects whose metrics are the template's declared ``pressure_drop`` /
``reynolds_number`` / ``friction_factor``.

Since Phase 8A, internal-flow experiments are built through the generic
``ExperimentDefinition.build_experiment`` path — the old airfoil-shaped
bridge (``build_internal_flow_experiment``) is gone, and identity /
geometry / validation are driven by the Internal Flow template contract. No
``aoa`` is fabricated anywhere.

These tests cover: template dispatch, the placeholder physics, generic
construction + input read-back, per-case execution, geometry-only mesh reuse,
graceful degradation with no mesh backend, bridge removal, and a full
end-to-end study run (build → execute → record result.json) driven straight
off the Internal Flow study definition — no core-runtime change, no
orchestrator branching.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import load_config                          # noqa: E402
from cfdauto.events import EventBus                             # noqa: E402
from cfdauto.execution import (                                 # noqa: E402
    ExecutionContext,
    InternalFlowExecutionStrategy,
    internal_flow_inputs,
    solve_internal_flow,
    strategy_for_template,
)
from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.models import STATUS_DONE                          # noqa: E402
from cfdauto.platform import INTERNAL_FLOW                      # noqa: E402
from cfdauto.simulation_context import SimulationContext        # noqa: E402
from cfdauto.state import RunState                              # noqa: E402
from tools.make_experiment_template import build_template       # noqa: E402


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
class _RecordingMesh:
    """A MeshBackend that writes a dummy pipe mesh and records every call."""

    def __init__(self):
        self.calls = []

    def prepare_mesh(self, exp, case_dir):
        self.calls.append(exp.geometry_key)
        p = Path(case_dir) / "FFF.msh.h5"
        p.write_text(f"pipe mesh for {exp.geometry_key}")
        return p


def _ed():
    """The generic ExperimentDefinition for the Internal Flow template."""
    return ExperimentDefinition.from_context(
        SimulationContext(template=INTERNAL_FLOW))


def _build(row, values):
    """Build one internal-flow Experiment through the generic path — the
    replacement for the removed ``build_internal_flow_experiment`` bridge."""
    return _ed().build_experiment(row=row, values=values)


def _context(tmp_path, mesh_backend=None):
    """A minimal ExecutionContext for the Internal Flow template. The workbook
    manager is unused by this strategy (its solve is analytical and it never
    reads output cells), so it is left as None."""
    xlsx = tmp_path / "placeholder.xlsx"
    build_template(xlsx)                    # only so load_config is satisfied
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(f"""
fluent: {{aoa_method: "geometry", wall_zones: ["wing"], reference: {{density: 1.225, area: 1.0}}}}
excel: {{file: "{xlsx.as_posix()}"}}
runtime: {{work_dir: "{(tmp_path / 'runs').as_posix()}", mock: true}}
""")
    cfg = load_config(cfg_file)
    return ExecutionContext(
        config=cfg, template=INTERNAL_FLOW, state=RunState(cfg.work_dir()),
        solver_backend=None, bus=EventBus(), excel=None,
        work_dir=cfg.work_dir(), mesh_backend=mesh_backend, experiments=[])


def _default_rows():
    """Name→value rows for the Internal Flow study's example sweep."""
    ed = _ed()
    names = [p.name for p in ed.study.ordered()]
    return [dict(zip(names, tup)) for tup in ed.default_experiment_rows()]


# --------------------------------------------------------------------- #
# Dispatch — the runtime resolves the executable strategy data-driven
# --------------------------------------------------------------------- #
def test_internal_flow_template_dispatches_to_executable_strategy():
    strat = strategy_for_template(INTERNAL_FLOW)
    assert isinstance(strat, InternalFlowExecutionStrategy)
    assert strat.strategy_id == "internal-flow"


# --------------------------------------------------------------------- #
# Physics — textbook laminar / turbulent pipe flow
# --------------------------------------------------------------------- #
def test_solve_laminar_branch_uses_hagen_poiseuille():
    # Re < 2300 → f = 64/Re, Δp = f (L/D) ½ρV².
    out = solve_internal_flow({
        "inlet_velocity": 0.02, "fluid_density": 998.2,
        "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.05, "pipe_length": 1.0})
    assert out["reynolds_number"] == pytest.approx(996.21, abs=0.5)
    assert out["reynolds_number"] < 2300
    assert out["friction_factor"] == pytest.approx(64.0 / out["reynolds_number"])
    assert out["pressure_drop"] == pytest.approx(0.25654, abs=1e-4)


def test_solve_turbulent_branch_uses_blasius():
    # Re > 2300 → Blasius f = 0.3164 Re^-0.25.
    out = solve_internal_flow({
        "inlet_velocity": 2.0, "fluid_density": 998.2,
        "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.05, "pipe_length": 1.0})
    assert out["reynolds_number"] == pytest.approx(99620.8, rel=1e-4)
    assert out["reynolds_number"] > 2300
    assert out["friction_factor"] == pytest.approx(0.017809, abs=1e-5)
    assert out["pressure_drop"] == pytest.approx(711.16, rel=1e-3)


# --------------------------------------------------------------------- #
# Generic construction — identity / geometry / validation from the template
# --------------------------------------------------------------------- #
def test_build_experiment_constructs_generic_internal_flow_case():
    exp = _build(row=5, values={
        "inlet_velocity": 5.0, "fluid_density": 998.2,
        "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.1, "pipe_length": 2.0})
    # Generic construction: every input under its own parameter name — no
    # airfoil slots, no fabricated aoa.
    assert "aoa" not in exp.parameters
    assert "velocity" not in exp.parameters
    assert exp.parameter("inlet_velocity").value == 5.0
    assert exp.parameter("pipe_diameter").value == 0.1
    assert set(exp.parameters_dict()) == {
        "inlet_velocity", "fluid_density", "fluid_viscosity",
        "pipe_diameter", "pipe_length"}
    # Template-driven identity / geometry / validation work with no bridge.
    exp.validate()
    assert exp.case_id.startswith("r005_inlet_velocity5")
    assert exp.geometry_key == "pipe_diameter=0.100000|pipe_length=2.000000"


def test_internal_flow_inputs_round_trips_the_generic_experiment():
    values = {"inlet_velocity": 5.0, "fluid_density": 998.2,
              "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.1,
              "pipe_length": 2.0}
    exp = _build(row=5, values=values)
    assert internal_flow_inputs(exp) == pytest.approx(values)


def test_build_internal_flow_experiment_bridge_is_removed():
    # Phase 8A: the airfoil-shaped bridge is gone — generic construction
    # replaces it, so the old entry point must no longer be importable.
    with pytest.raises(ImportError):
        from cfdauto.execution import build_internal_flow_experiment  # noqa: F401


# --------------------------------------------------------------------- #
# Per-case execution — CaseResult carries the template's metrics
# --------------------------------------------------------------------- #
def test_execute_case_produces_template_metrics(tmp_path):
    mesh = _RecordingMesh()
    ctx = _context(tmp_path, mesh_backend=mesh)
    strat = strategy_for_template(INTERNAL_FLOW)
    exp = _build(row=2, values={
        "inlet_velocity": 2.0, "fluid_density": 998.2,
        "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.05, "pipe_length": 1.0})
    res = strat.execute_case(exp, ctx, ctx.state.case_dir(exp))

    assert res.converged is True
    assert res.mesh_file.endswith(".msh.h5")       # stored copy from the cache
    assert mesh.calls == [exp.geometry_key]        # meshed once via the adapter
    metrics = res.metrics_dict()
    assert set(metrics) == {"pressure_drop", "reynolds_number", "friction_factor"}
    assert metrics["pressure_drop"] == pytest.approx(711.16, rel=1e-3)
    # airfoil metrics are simply absent — no cross-contamination of the model.
    assert res.cl is None and res.cd is None


def test_execute_case_without_mesh_backend_still_solves(tmp_path):
    ctx = _context(tmp_path, mesh_backend=None)
    strat = strategy_for_template(INTERNAL_FLOW)
    exp = _build(row=2, values={
        "inlet_velocity": 2.0, "fluid_density": 998.2,
        "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.05, "pipe_length": 1.0})
    res = strat.execute_case(exp, ctx, ctx.state.case_dir(exp))
    assert res.mesh_file == ""                     # no mesh required
    assert res.metric("reynolds_number").value == pytest.approx(99620.8, rel=1e-4)


# --------------------------------------------------------------------- #
# Mesh reuse — the pipe is meshed once per geometry, reused across velocity
# --------------------------------------------------------------------- #
def test_mesh_is_reused_across_velocity_for_one_geometry(tmp_path):
    mesh = _RecordingMesh()
    ctx = _context(tmp_path, mesh_backend=mesh)
    strat = strategy_for_template(INTERNAL_FLOW)
    base = {"fluid_density": 998.2, "fluid_viscosity": 1.002e-3,
            "pipe_diameter": 0.05, "pipe_length": 1.0}
    for row, v in enumerate((1.0, 2.0, 5.0), start=2):    # same pipe, 3 speeds
        exp = _build(row=row, values={**base, "inlet_velocity": v})
        strat.execute_case(exp, ctx, ctx.state.case_dir(exp))
    assert len(mesh.calls) == 1                    # Workbench ran once, then cache hits


# --------------------------------------------------------------------- #
# End-to-end — the whole Internal Flow study through the generic pipeline
# --------------------------------------------------------------------- #
def test_end_to_end_study_executes_and_records_results(tmp_path):
    mesh = _RecordingMesh()
    ctx = _context(tmp_path, mesh_backend=mesh)
    strat = strategy_for_template(INTERNAL_FLOW)

    rows = _default_rows()
    assert len(rows) == 8                          # 4 velocities × 2 diameters

    for i, values in enumerate(rows, start=2):
        exp = _build(row=i, values=values)
        exp.validate()
        res = strat.execute_case(exp, ctx, ctx.state.case_dir(exp))
        ctx.state.write_result_json(exp, {
            "status": STATUS_DONE,
            "experiment": exp.to_json_dict(),
            **res.metrics_dict()})

    # Two distinct pipe diameters → the pipe is meshed exactly twice.
    assert len(set(mesh.calls)) == 2
    assert len(mesh.calls) == 2

    # Every case wrote a result.json carrying the internal-flow metrics.
    result_files = sorted(ctx.state.cases_dir.glob("*/result.json"))
    assert len(result_files) == 8
    for f in result_files:
        payload = json.loads(f.read_text())
        assert payload["status"] == STATUS_DONE
        assert payload["reynolds_number"] > 0
        assert payload["pressure_drop"] > 0
        assert "friction_factor" in payload
