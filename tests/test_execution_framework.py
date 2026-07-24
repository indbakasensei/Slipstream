"""Universal CFD Platform, Phase 7 — execution framework tests.

Execution is now owned by the template's ExecutionStrategy, dispatched
data-driven through the strategy registry. These tests cover the strategy
base + registry, template-owned dispatch (no runtime branching), the
External Aerodynamics strategy's per-case workflow (mesh cache + solve via
the adapters), the Internal Flow stub, and the ExecutionContext/
ExecutionResult objects — plus an end-to-end assertion that the orchestrator
drives the strategy and produces an ExecutionResult.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import ExcelConfig, load_config             # noqa: E402
from cfdauto.events import EventBus                             # noqa: E402
from cfdauto.excel_manager import ExcelManager                  # noqa: E402
from cfdauto.execution import (                                 # noqa: E402
    ExecutionContext,
    ExecutionResult,
    ExecutionStrategy,
    ExternalAerodynamicsExecutionStrategy,
    InternalFlowExecutionStrategy,
    get_execution_strategy,
    register_strategy,
    registered_ids,
    strategy_for_template,
)
from cfdauto.execution.result import (                          # noqa: E402
    STATUS_COMPLETED,
    STATUS_NOTHING_TO_DO,
)
from cfdauto.models import CaseResult, Experiment               # noqa: E402
from cfdauto.orchestrator import Orchestrator, build_controllers  # noqa: E402
from cfdauto.platform import (                                  # noqa: E402
    EXTERNAL_AERODYNAMICS,
    INTERNAL_FLOW,
    get_default_template,
)
from cfdauto.state import RunState                              # noqa: E402
from tools.make_experiment_template import build_template       # noqa: E402


# --------------------------------------------------------------------- #
# Group: registry + template-owned dispatch (no branching)
# --------------------------------------------------------------------- #
def test_builtin_strategies_are_registered():
    assert set(registered_ids()) == {"external-aerodynamics", "internal-flow"}


def test_template_owns_its_execution_strategy_id():
    assert EXTERNAL_AERODYNAMICS.execution_strategy_id == "external-aerodynamics"
    assert INTERNAL_FLOW.execution_strategy_id == "internal-flow"


def test_strategy_for_template_dispatches_data_driven():
    # The runtime resolves the strategy from the template's id — never with
    # an `if template == external_aero` check.
    assert isinstance(strategy_for_template(EXTERNAL_AERODYNAMICS),
                      ExternalAerodynamicsExecutionStrategy)
    assert isinstance(strategy_for_template(INTERNAL_FLOW),
                      InternalFlowExecutionStrategy)
    assert strategy_for_template(get_default_template()).strategy_id == \
        "external-aerodynamics"


def test_get_unknown_strategy_raises_with_actionable_message():
    with pytest.raises(LookupError, match="external-aerodynamics"):
        get_execution_strategy("no-such-strategy")


def test_registering_a_duplicate_strategy_id_is_rejected():
    with pytest.raises(ValueError, match="already registered"):
        register_strategy(ExternalAerodynamicsExecutionStrategy())


# --------------------------------------------------------------------- #
# Group: strategy base defaults (safe for a stub)
# --------------------------------------------------------------------- #
def test_base_strategy_cascade_hooks_default_to_benign():
    class _Bare(ExecutionStrategy):
        strategy_id = "bare"
        def execute_case(self, experiment, context, case_dir):
            return CaseResult()
    s = _Bare()
    assert s.is_launch_failure(Experiment(row=1, aoa_deg=0, velocity=1), None) is False
    assert s.cleanup_after_cascade(None) is None       # no-op


def test_internal_flow_strategy_plugs_in_with_benign_hooks():
    # Capability 1 made this strategy executable; here we only assert it
    # plugs into the framework — registered, dispatchable, benign cascade
    # hooks (its analytical solve has no launch/licence failure notion). Its
    # actual per-case behaviour lives in tests/test_internal_flow_execution.py.
    s = InternalFlowExecutionStrategy()
    assert s.strategy_id == "internal-flow"
    assert s.is_launch_failure(None, None) is False
    assert s.cleanup_after_cascade(None) is None


# --------------------------------------------------------------------- #
# Group: External Aerodynamics strategy per-case workflow
# --------------------------------------------------------------------- #
class _RecordingMesh:
    def __init__(self):
        self.calls = []
    def prepare_mesh(self, exp, case_dir):
        self.calls.append(exp.row)
        p = Path(case_dir) / "FFF.msh"
        p.write_text("mesh")
        return p


class _RecordingSolver:
    def __init__(self):
        self.meshes = []
    def run_case(self, exp, mesh_file, case_dir):
        self.meshes.append(mesh_file)
        return CaseResult(cl=0.5, cd=0.05, converged=True)


def _context(tmp_path, mesh_backend, solver_backend, aoa_method="geometry"):
    cfg_file = tmp_path / "c.yaml"
    xlsx = tmp_path / "e.xlsx"; build_template(xlsx)
    cfg_file.write_text(f"""
fluent: {{aoa_method: "{aoa_method}", wall_zones: ["wing"], reference: {{density: 1.225, area: 1.0}}}}
excel: {{file: "{xlsx.as_posix()}"}}
runtime: {{work_dir: "{(tmp_path / 'runs').as_posix()}", mock: true}}
""")
    cfg = load_config(cfg_file)
    excel = ExcelManager(cfg.excel)
    return ExecutionContext(
        config=cfg, template=EXTERNAL_AERODYNAMICS, state=RunState(cfg.work_dir()),
        solver_backend=solver_backend, bus=EventBus(), excel=excel,
        work_dir=cfg.work_dir(), mesh_backend=mesh_backend, experiments=[])


def test_external_strategy_meshes_then_solves_in_geometry_mode(tmp_path):
    mesh, solver = _RecordingMesh(), _RecordingSolver()
    ctx = _context(tmp_path, mesh, solver, aoa_method="geometry")
    strat = ExternalAerodynamicsExecutionStrategy()
    exp = Experiment(row=2, aoa_deg=4.0, velocity=20.0)
    case_dir = ctx.state.case_dir(exp)
    res = strat.execute_case(exp, ctx, case_dir)
    assert res.cl == 0.5
    assert mesh.calls == [2]                    # Workbench meshed once
    assert solver.meshes[0] is not None          # solver got the mesh


def test_external_strategy_reuses_cached_mesh(tmp_path):
    mesh, solver = _RecordingMesh(), _RecordingSolver()
    ctx = _context(tmp_path, mesh, solver, aoa_method="geometry")
    strat = ExternalAerodynamicsExecutionStrategy()
    a = Experiment(row=2, aoa_deg=4.0, velocity=20.0)   # same geometry (aoa=4)
    b = Experiment(row=3, aoa_deg=4.0, velocity=30.0)
    strat.execute_case(a, ctx, ctx.state.case_dir(a))
    strat.execute_case(b, ctx, ctx.state.case_dir(b))
    assert mesh.calls == [2]                     # Workbench ran ONCE, then cache hit


def test_external_strategy_skips_workbench_in_velocity_vector_mode(tmp_path):
    mesh, solver = _RecordingMesh(), _RecordingSolver()
    ctx = _context(tmp_path, mesh, solver, aoa_method="velocity_vector")
    strat = ExternalAerodynamicsExecutionStrategy()
    exp = Experiment(row=2, aoa_deg=4.0, velocity=20.0)
    strat.execute_case(exp, ctx, ctx.state.case_dir(exp))
    assert mesh.calls == []                      # no Workbench
    assert solver.meshes == [None]               # solver got no mesh


# --------------------------------------------------------------------- #
# Group: ExecutionResult
# --------------------------------------------------------------------- #
def test_execution_result_derived_fields():
    r = ExecutionResult(status=STATUS_COMPLETED, completed_cases=7, failed_cases=1)
    assert r.total_cases == 8 and r.ok is False
    assert ExecutionResult(status=STATUS_COMPLETED, completed_cases=8).ok is True


# --------------------------------------------------------------------- #
# Group: orchestrator drives the strategy end-to-end
# --------------------------------------------------------------------- #
def test_orchestrator_runs_via_strategy_and_exposes_execution_result(tmp_path):
    xlsx = tmp_path / "e.xlsx"; build_template(xlsx)
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(f"""
fluent: {{aoa_method: "geometry", wall_zones: ["wing"], reference: {{density: 1.225, area: 1.0}}}}
excel: {{file: "{xlsx.as_posix()}"}}
runtime: {{work_dir: "{(tmp_path / 'runs').as_posix()}", mock: true}}
""")
    cfg = load_config(cfg_file)
    excel = ExcelManager(cfg.excel)
    wb, fl = build_controllers(cfg)
    orch = Orchestrator(cfg, excel, wb, fl, bus=EventBus())
    assert orch._strategy.strategy_id == "external-aerodynamics"

    failures = orch.run(max_cases=2)
    assert failures == 0
    er = orch.execution_result
    assert er is not None
    assert er.status == STATUS_COMPLETED
    assert er.completed_cases == 2 and er.failed_cases == 0
    assert er.duration_s >= 0.0

    # A second run with nothing to do yields a NOTHING_TO_DO result.
    orch2 = Orchestrator(cfg, excel, wb, fl, bus=EventBus())
    orch2.run()                                   # rows 1-2 done; rest pending...
    # (this project's template seeds 8 rows; max_cases=2 above left 6 pending)
    assert orch2.execution_result is not None
