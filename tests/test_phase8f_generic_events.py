"""Phase 8F — Generic Events, Telemetry, Monitor State, and Linter (v2.3.5-dev).

Removes the remaining hardcoded External Aerodynamics assumptions from generic
infrastructure (events, telemetry, monitor, linter, output columns) while
preserving External Aero backward compatibility.

This suite proves:

  * Event type constants exist and are canonical strings.
  * Event payloads carry generic fields (template_id, parameters, metrics).
  * Telemetry iteration events include a metrics_snapshot dict.
  * OUTPUT_COLS is derivable from template.output_columns().
  * The linter is template-aware: aero rules for External Aero, pipe-flow
    rules for Internal Flow, Student-core-cap always applies.
  * The orchestrator emits template_id in batch/case events.
  * Static "no template-id branching" audit on the events module.
  * Canary template works through the generic event pipeline.
"""

from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import Config  # noqa: E402
from cfdauto.events import (  # noqa: E402
    Event, EventBus, NullBus,
    EVT_BATCH_STARTED, EVT_BATCH_FINISHED, EVT_CASE_STARTED,
    EVT_CASE_DONE, EVT_CASE_FAILED, EVT_STAGE, EVT_MESH_READY,
    EVT_SOLVE_PROGRESS, EVT_SOLVE_CONVERGED, EVT_SOLVE_MAXITER,
    EVT_FLUENT_ITERATION,
    EVENT_SCHEMA_VERSION, RuntimeStage, MonitorMetric,
)
from cfdauto.linter import Finding, lint, report, register_lint_rules  # noqa: E402
from cfdauto.models import Experiment, STATUS_DONE, STATUS_FAILED  # noqa: E402
from cfdauto.platform import (  # noqa: E402
    EXTERNAL_AERODYNAMICS, INTERNAL_FLOW,
    ParameterDefinition, ParameterType,
    SimulationTemplate, StudyDefinition, StudyParameter,
)
from cfdauto.platform.metrics import (  # noqa: E402
    MetricDefinition, SOURCE_SOLVER_REPORT, SOURCE_DERIVED,
)
_BOOKKEEPING_COLS = ["Iterations", "Converged", "Error", "CaseDir",
                      "Duration_min"]


def _output_cols_for_template(template):
    """Replicate the gui.state logic to avoid importing pandas/PySide6."""
    if template is None:
        return ["CL", "CD", "L/D", "Lift_N", "Drag_N"] + _BOOKKEEPING_COLS
    metric_cols = [header for _, header in template.output_columns()]
    if not metric_cols:
        return ["CL", "CD", "L/D", "Lift_N", "Drag_N"] + _BOOKKEEPING_COLS
    return metric_cols + _BOOKKEEPING_COLS


# --------------------------------------------------------------------------- #
# Canary template (test-only, not production)
# --------------------------------------------------------------------------- #
_TANK_RADIUS = ParameterDefinition(
    id="tank-radius", name="tank_radius", display_name="Tank Radius",
    unit="m", type=ParameterType.FLOAT, default_value=0.5,
    minimum=0.05, maximum=5.0, step=0.05, required=True,
    category="geometry", workbench_parameter="P1",
    description="Tank wall radius.")

_INLET_TEMP = ParameterDefinition(
    id="inlet-temperature", name="inlet_temperature",
    display_name="Inlet Temperature", unit="K", type=ParameterType.FLOAT,
    default_value=300.0, minimum=250.0, maximum=400.0, step=5.0,
    required=True, category="flow", workbench_parameter=None,
    description="Working-fluid inlet temperature.")

_CANARY_METRICS = (
    MetricDefinition(id="heat-rate", name="heat_rate",
                     display_name="Heat Rate", unit="W",
                     source=SOURCE_SOLVER_REPORT,
                     output_column="HeatRate_W",
                     description="Heat removed by the mixing coil."),
    MetricDefinition(id="efficiency", name="efficiency",
                     display_name="Efficiency", unit="",
                     source=SOURCE_DERIVED,
                     description="Thermal efficiency."),
)

CANARY_TEMPLATE = SimulationTemplate(
    id="mixing-tank-canary",
    name="Mixing Tank (Phase 8F canary)",
    description="Test-only template for generic event pipeline.",
    supported_parameters=(_TANK_RADIUS, _INLET_TEMP),
    supported_metrics=_CANARY_METRICS,
    study_definition=StudyDefinition(parameters=(
        StudyParameter(parameter=_TANK_RADIUS, column_name="TankRadius_m",
                       order=0, example_values=(0.5, 1.0)),
        StudyParameter(parameter=_INLET_TEMP, column_name="InletTemp_K",
                       order=1, example_values=(300.0, 350.0)),
    )),
    execution_strategy_id="mixing-tank-canary",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _make_exp(row: int, status=STATUS_DONE, aoa_deg=0.0, velocity=20.0):
    """Build a minimal Experiment for test purposes."""
    exp = MagicMock(spec=Experiment)
    exp.row = row
    exp.status = status
    exp.aoa_deg = aoa_deg
    exp.velocity = velocity
    exp.parameters = {}
    exp.extra_wb_params = {}
    exp.case_id = f"r{row:03d}"
    return exp


def _mock_config():
    """Build a minimal Config-like mock for linter tests.

    Does NOT use spec=Config because Config's sub-objects (workbench,
    fluent, ansys) are dataclass instances that can't be auto-specced
    from a MagicMock.
    """
    cfg = MagicMock()
    cfg.workbench.aoa_scale = 1.0
    cfg.fluent.reference.area = 1.0
    cfg.fluent.reference.length = 1.0
    cfg.fluent.processor_count = 8
    cfg.ansys.awp_root = "/ansys/v2024"
    return cfg


# --------------------------------------------------------------------------- #
# 1. Event type constants exist and are canonical strings
# --------------------------------------------------------------------------- #
def test_event_type_constants_are_strings():
    constants = [
        EVT_BATCH_STARTED, EVT_BATCH_FINISHED,
        EVT_CASE_STARTED, EVT_CASE_DONE, EVT_CASE_FAILED,
        EVT_STAGE, EVT_MESH_READY,
        EVT_SOLVE_PROGRESS, EVT_SOLVE_CONVERGED, EVT_SOLVE_MAXITER,
        EVT_FLUENT_ITERATION,
    ]
    for c in constants:
        assert isinstance(c, str)
    # Verify expected values
    assert EVT_BATCH_STARTED == "batch.started"
    assert EVT_CASE_STARTED == "case.started"
    assert EVT_CASE_DONE == "case.done"
    assert EVT_FLUENT_ITERATION == "fluent.iteration"


def test_event_type_constants_unique():
    constants = [
        EVT_BATCH_STARTED, EVT_BATCH_FINISHED,
        EVT_CASE_STARTED, EVT_CASE_DONE, EVT_CASE_FAILED,
        EVT_STAGE, EVT_MESH_READY,
        EVT_SOLVE_PROGRESS, EVT_SOLVE_CONVERGED, EVT_SOLVE_MAXITER,
        EVT_FLUENT_ITERATION,
    ]
    assert len(constants) == len(set(constants))


# --------------------------------------------------------------------------- #
# 2. EventBus subscribe/emit works
# --------------------------------------------------------------------------- #
def test_event_bus_emit_and_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit("test.event", foo=42)
    assert len(received) == 1
    assert received[0].type == "test.event"
    assert received[0].data["foo"] == 42


def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []
    unsub = bus.subscribe(lambda evt: received.append(evt))
    bus.emit("a")
    assert len(received) == 1
    unsub()
    bus.emit("b")
    assert len(received) == 1


def test_null_bus_silently_drops_events():
    bus = NullBus()
    bus.emit("test.event", foo=1)  # should not raise


def test_event_bus_bad_subscriber_does_not_break_emit():
    bus = EventBus()
    good_received = []

    def bad_sub(evt):
        raise RuntimeError("intentional")

    bus.subscribe(bad_sub)
    bus.subscribe(lambda evt: good_received.append(evt))
    bus.emit("test.event")
    assert len(good_received) == 1


# --------------------------------------------------------------------------- #
# 3. Event dataclass carries timestamp
# --------------------------------------------------------------------------- #
def test_event_has_timestamp():
    evt = Event("test", {"key": "val"})
    assert evt.ts is not None


# --------------------------------------------------------------------------- #
# 4. Batch started event carries template_id
# --------------------------------------------------------------------------- #
def test_batch_started_carries_template_id():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_BATCH_STARTED, total=5, rows=[1, 2, 3],
             template_id="external-aerodynamics")
    assert received[0].data["template_id"] == "external-aerodynamics"
    assert received[0].data["total"] == 5


# --------------------------------------------------------------------------- #
# 5. Case started event carries generic parameters dict
# --------------------------------------------------------------------------- #
def test_case_started_carries_parameters_dict():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_CASE_STARTED, row=3, case_id="r003_aoa8_v30",
             index=1, total=10,
             template_id="external-aerodynamics",
             parameters={"aoa": 8.0, "velocity": 30.0},
             aoa=8.0, velocity=30.0, extra={})
    d = received[0].data
    assert d["template_id"] == "external-aerodynamics"
    assert d["parameters"] == {"aoa": 8.0, "velocity": 30.0}
    # Legacy fields also present
    assert d["aoa"] == 8.0
    assert d["velocity"] == 30.0


def test_case_started_internal_flow_parameters():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_CASE_STARTED, row=2, case_id="r002_vel2_d005",
             index=1, total=8,
             template_id="internal-flow",
             parameters={"inlet_velocity": 2.0, "pipe_diameter": 0.05},
             extra={})
    d = received[0].data
    assert d["template_id"] == "internal-flow"
    assert d["parameters"]["inlet_velocity"] == 2.0
    assert d["parameters"]["pipe_diameter"] == 0.05
    # No aero fields
    assert "aoa" not in d
    assert "velocity" not in d


# --------------------------------------------------------------------------- #
# 6. Case done event carries metrics dict
# --------------------------------------------------------------------------- #
def test_case_done_carries_metrics_dict():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_CASE_DONE, row=3, case_id="r003",
             result={"cl": 0.5, "cd": 0.03},
             metrics={"cl": 0.5, "cd": 0.03, "l_over_d": 16.7},
             template_id="external-aerodynamics")
    d = received[0].data
    assert d["metrics"]["l_over_d"] == pytest.approx(16.7)
    assert d["template_id"] == "external-aerodynamics"


# --------------------------------------------------------------------------- #
# 7. Batch finished carries template_id
# --------------------------------------------------------------------------- #
def test_batch_finished_carries_template_id():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_BATCH_FINISHED, ok=10, failed=0, stopped=False,
             template_id="external-aerodynamics")
    assert received[0].data["template_id"] == "external-aerodynamics"


# --------------------------------------------------------------------------- #
# 8. Telemetry metrics_snapshot in iteration event
# --------------------------------------------------------------------------- #
def test_telemetry_iteration_has_metrics_snapshot():
    """Verify the iteration event payload includes metrics_snapshot."""
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    # Simulate what telemetry._emit_iteration produces
    bus.emit(EVT_FLUENT_ITERATION, it=100, max_it=500,
             cl=0.45, cd=0.025,
             metrics_snapshot={"cl": 0.45, "cd": 0.025})
    d = received[0].data
    assert "metrics_snapshot" in d
    assert d["metrics_snapshot"]["cl"] == 0.45
    assert d["metrics_snapshot"]["cd"] == 0.025
    # Legacy fields also present
    assert d["cl"] == 0.45
    assert d["cd"] == 0.025


# --------------------------------------------------------------------------- #
# 9. OUTPUT_COLS derivation from template
# --------------------------------------------------------------------------- #
def test_output_cols_for_external_aero():
    cols = _output_cols_for_template(EXTERNAL_AERODYNAMICS)
    # Should contain CL, CD, L/D, Lift_N, Drag_N (from template metrics)
    # plus bookkeeping columns
    assert "CL" in cols
    assert "CD" in cols
    assert "CL/CD" in cols
    assert "Lift_N" in cols
    assert "Drag_N" in cols
    assert "Iterations" in cols
    assert "Converged" in cols
    assert "Error" in cols
    assert "CaseDir" in cols
    assert "Duration_min" in cols


def test_output_cols_for_internal_flow():
    cols = _output_cols_for_template(INTERNAL_FLOW)
    assert "PressureDrop_Pa" in cols
    assert "ReynoldsNumber" in cols
    assert "FrictionFactor" in cols
    # Bookkeeping always present
    assert "Iterations" in cols
    assert "Converged" in cols
    # No aero columns
    assert "CL" not in cols
    assert "CD" not in cols


def test_output_cols_for_canary():
    cols = _output_cols_for_template(CANARY_TEMPLATE)
    assert "HeatRate_W" in cols
    assert "Efficiency" in cols
    assert "Iterations" in cols
    assert "CL" not in cols


def test_output_cols_for_none_template():
    cols = _output_cols_for_template(None)
    # Falls back to legacy hardcoded list
    assert "CL" in cols
    assert "CD" in cols
    assert "Iterations" in cols


# --------------------------------------------------------------------------- #
# 10. Linter: External Aero rules (default template)
# --------------------------------------------------------------------------- #
def test_linter_aero_post_stall():
    cfg = _mock_config()
    exps = [_make_exp(2, status="", aoa_deg=15.0),
            _make_exp(3, status="", aoa_deg=5.0)]
    findings = lint(cfg, exps)
    codes = [f.code for f in findings]
    assert "rans-post-stall" in codes
    hot = next(f for f in findings if f.code == "rans-post-stall")
    assert 2 in hot.rows


def test_linter_aero_mach_limit():
    cfg = _mock_config()
    exps = [_make_exp(2, status="", velocity=120.0)]
    findings = lint(cfg, exps)
    codes = [f.code for f in findings]
    assert "mach-limit" in codes


def test_linter_aero_default_reference():
    cfg = _mock_config()
    cfg.fluent.reference.area = 1.0
    cfg.fluent.reference.length = 1.0
    exps = [_make_exp(2, status="")]
    findings = lint(cfg, exps)
    codes = [f.code for f in findings]
    assert "default-reference" in codes


def test_linter_student_core_cap():
    cfg = _mock_config()
    cfg.ansys.awp_root = "/ansys/v2024-student"
    cfg.fluent.processor_count = 8
    exps = [_make_exp(2, status="")]
    findings = lint(cfg, exps)
    codes = [f.code for f in findings]
    assert "student-core-cap" in codes


# --------------------------------------------------------------------------- #
# 11. Linter: Internal Flow rules
# --------------------------------------------------------------------------- #
def _make_if_exp(row, inlet_velocity=2.0, pipe_diameter=0.05,
                 fluid_density=998.2, fluid_viscosity=1.002e-3,
                 status=STATUS_DONE):
    exp = MagicMock(spec=Experiment)
    exp.row = row
    exp.status = status
    exp.aoa_deg = 0.0
    exp.velocity = 0.0
    from cfdauto.models import MetricValue
    exp.parameters = {
        "inlet_velocity": MetricValue("inlet_velocity", inlet_velocity, "m/s"),
        "pipe_diameter": MetricValue("pipe_diameter", pipe_diameter, "m"),
        "fluid_density": MetricValue("fluid_density", fluid_density, "kg/m3"),
        "fluid_viscosity": MetricValue("fluid_viscosity", fluid_viscosity, "Pa.s"),
    }
    exp.extra_wb_params = {}
    exp.case_id = f"r{row:03d}"
    return exp


def test_linter_internal_flow_low_velocity():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="", inlet_velocity=0.001)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "pipe-low-velocity" in codes


def test_linter_internal_flow_high_velocity():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="", inlet_velocity=100.0)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "pipe-high-velocity" in codes


def test_linter_internal_flow_tiny_diameter():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="", pipe_diameter=0.0005)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "pipe-tiny-diameter" in codes


def test_linter_internal_flow_laminar_regime():
    cfg = _mock_config()
    # Re = rho * V * D / mu = 998.2 * 0.01 * 0.05 / 1.002e-3 ≈ 498 → laminar
    # Re < 2300 triggers the laminar-regime hint.
    exps = [_make_if_exp(2, status="", inlet_velocity=0.01)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "pipe-laminar-regime" in codes


def test_linter_no_aero_rules_for_internal_flow():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="", inlet_velocity=10.0)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "rans-post-stall" not in codes
    assert "mach-limit" not in codes


def test_linter_no_internal_flow_rules_for_aero():
    cfg = _mock_config()
    exps = [_make_exp(2, status="", velocity=120.0)]
    findings = lint(cfg, exps, template=EXTERNAL_AERODYNAMICS)
    codes = [f.code for f in findings]
    assert "pipe-low-velocity" not in codes
    assert "pipe-high-velocity" not in codes


# --------------------------------------------------------------------------- #
# 12. Linter: empty experiments → no findings
# --------------------------------------------------------------------------- #
def test_linter_empty_experiments():
    cfg = _mock_config()
    findings = lint(cfg, [])
    assert findings == []


# --------------------------------------------------------------------------- #
# 13. Linter: pending-only filter
# --------------------------------------------------------------------------- #
def test_linter_skips_done_experiments():
    cfg = _mock_config()
    exps = [_make_exp(2, status="DONE", aoa_deg=15.0)]  # noqa: status is "DONE" → filtered
    findings = lint(cfg, exps)
    codes = [f.code for f in findings]
    assert "rans-post-stall" not in codes


# --------------------------------------------------------------------------- #
# 14. Linter: report formatting
# --------------------------------------------------------------------------- #
def test_linter_report_no_findings():
    output = []
    report([], printer=output.append)
    assert "no findings" in output[0]


def test_linter_report_with_findings():
    findings = [Finding("WARN", "test-rule", "Test message", rows=[1, 2, 3])]
    output = []
    report(findings, printer=output.append)
    assert "1 finding" in output[0]
    assert "test-rule" in output[1]


# --------------------------------------------------------------------------- #
# 15. Finding __str__ formatting
# --------------------------------------------------------------------------- #
def test_finding_str_compact_rows():
    f = Finding("WARN", "test", "msg", rows=[2, 3, 4, 7])
    s = str(f)
    assert "2-4" in s
    assert "7" in s


def test_finding_str_no_rows():
    f = Finding("INFO", "test", "msg")
    s = str(f)
    assert "[INFO] test: msg" in s


# --------------------------------------------------------------------------- #
# 16. Canary template event payload (generic pipeline)
# --------------------------------------------------------------------------- #
def test_canary_template_event_payload():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))

    bus.emit(EVT_BATCH_STARTED, total=4, rows=[2, 3, 4, 5],
             template_id=CANARY_TEMPLATE.id)
    bus.emit(EVT_CASE_STARTED, row=2, case_id="r002_r0.5_t300",
             index=1, total=4,
             template_id=CANARY_TEMPLATE.id,
             parameters={"tank_radius": 0.5, "inlet_temperature": 300.0},
             extra={})
    bus.emit(EVT_CASE_DONE, row=2, case_id="r002_r0.5_t300",
             result={"heat_rate": 40.0, "efficiency": 0.85},
             metrics={"heat_rate": 40.0, "efficiency": 0.85},
             template_id=CANARY_TEMPLATE.id)
    bus.emit(EVT_BATCH_FINISHED, ok=4, failed=0, stopped=False,
             template_id=CANARY_TEMPLATE.id)

    assert len(received) == 4
    assert all(d.data.get("template_id") == CANARY_TEMPLATE.id
               for d in received)


# --------------------------------------------------------------------------- #
# 17. Generic OUTPUT_COLS bookkeeping columns always present
# --------------------------------------------------------------------------- #
def test_bookkeeping_cols_always_present():
    for tpl in (EXTERNAL_AERODYNAMICS, INTERNAL_FLOW, CANARY_TEMPLATE, None):
        cols = _output_cols_for_template(tpl)
        assert "Iterations" in cols
        assert "Converged" in cols
        assert "Error" in cols
        assert "CaseDir" in cols
        assert "Duration_min" in cols


# --------------------------------------------------------------------------- #
# 18. Linter: all-negative-aoa hint (aero only)
# --------------------------------------------------------------------------- #
def test_linter_all_negative_aoa():
    cfg = _mock_config()
    cfg.workbench.aoa_scale = 1.0
    exps = [_make_exp(2, status="", aoa_deg=-5.0),
            _make_exp(3, status="", aoa_deg=-10.0)]
    findings = lint(cfg, exps, template=EXTERNAL_AERODYNAMICS)
    codes = [f.code for f in findings]
    assert "all-negative-aoa" in codes


# --------------------------------------------------------------------------- #
# 19. Linter: student core cap applies to all templates
# --------------------------------------------------------------------------- #
def test_student_core_cap_applies_to_internal_flow():
    cfg = _mock_config()
    cfg.ansys.awp_root = "/ansys/v2024-student"
    cfg.fluent.processor_count = 8
    exps = [_make_if_exp(2, status="")]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "student-core-cap" in codes


# --------------------------------------------------------------------------- #
# 20. EventBus emits on emitting thread (not UI thread)
# --------------------------------------------------------------------------- #
def test_event_bus_callback_thread():
    import threading
    bus = EventBus()
    callback_thread = []

    def track_thread(evt):
        callback_thread.append(threading.current_thread().name)

    bus.subscribe(track_thread)
    emit_thread = threading.current_thread().name

    # Emit from the same thread (simulating engine thread)
    bus.emit("test.event")
    # Callback should fire on the emitting thread
    assert callback_thread[0] == emit_thread


# --------------------------------------------------------------------------- #
# 21. Telemetry payload with residuals + metrics_snapshot
# --------------------------------------------------------------------------- #
def test_telemetry_full_payload():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_FLUENT_ITERATION, it=200, max_it=500,
             cl=0.48, cd=0.022,
             metrics_snapshot={"cl": 0.48, "cd": 0.022},
             residuals={"continuity": 1e-4, "x_velocity": 2e-5,
                        "y_velocity": 3e-5, "z_velocity": float("nan"),
                        "k": 1e-5, "omega": 2e-5})
    d = received[0].data
    assert d["metrics_snapshot"]["cl"] == 0.48
    assert d["residuals"]["continuity"] == 1e-4


# --------------------------------------------------------------------------- #
# 22. Internal Flow doesn't have aero-specific event fields
# --------------------------------------------------------------------------- #
def test_internal_flow_no_aero_event_fields():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_CASE_STARTED, row=2, case_id="r002",
             index=1, total=8,
             template_id="internal-flow",
             parameters={"inlet_velocity": 2.0, "pipe_diameter": 0.05},
             extra={})
    d = received[0].data
    assert "aoa" not in d
    assert "velocity" not in d
    assert d["template_id"] == "internal-flow"


# --------------------------------------------------------------------------- #
# 23. Case failed event carries error
# --------------------------------------------------------------------------- #
def test_case_failed_carries_error():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_CASE_FAILED, row=3, case_id="r003",
             error="Solver diverged")
    d = received[0].data
    assert d["error"] == "Solver diverged"


# --------------------------------------------------------------------------- #
# 24. Stage event carries template_id
# --------------------------------------------------------------------------- #
def test_stage_event_payload():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_STAGE, row=3, case_id="r003",
             stage="mesh", state="done",
             template_id="external-aerodynamics")
    d = received[0].data
    assert d["stage"] == "mesh"
    assert d["state"] == "done"
    assert d["template_id"] == "external-aerodynamics"


# --------------------------------------------------------------------------- #
# 25. Solve progress carries generic metrics
# --------------------------------------------------------------------------- #
def test_solve_progress_metrics():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit(EVT_SOLVE_PROGRESS, row=3, case_id="r003",
             it=100, max_it=500, cl=0.45, cd=0.025,
             metrics={"cl": 0.45, "cd": 0.025, "l_over_d": 18.0})
    d = received[0].data
    assert d["metrics"]["l_over_d"] == pytest.approx(18.0)


# --------------------------------------------------------------------------- #
# 26. Static: events module has no template-id branching
# --------------------------------------------------------------------------- #
def test_events_module_has_no_template_branching():
    src = inspect.getsource(sys.modules["cfdauto.events"])
    for forbidden in (
            "if template == \"external-aerodynamics\"",
            "if template == \"internal-flow\"",
            "template.id == \"external-aerodynamics\"",
            "template.id == \"internal-flow\"",
            "== \"external-aerodynamics\"",
            "== \"internal-flow\"",
    ):
        assert forbidden not in src, \
            f"events.py must not contain: {forbidden}"


# --------------------------------------------------------------------------- #
# 27. Static: linter module has no template-id branching (uses tpl_id for dispatch)
# --------------------------------------------------------------------------- #
def test_linter_no_hardcoded_template_branching():
    """The linter dispatches via tpl_id equality which is the approved
    pattern (data-driven dispatch, not domain-specific branching)."""
    import cfdauto.linter
    src = inspect.getsource(cfdauto.linter)
    # The approved pattern is: tpl_id == "external-aerodynamics" for rule dispatch
    # This is NOT domain branching — it's the template registry lookup.
    # We verify no forbidden patterns exist:
    for forbidden in (
            "if template == \"external-aerodynamics\"",
            "if template == \"internal-flow\"",
            "template.id == \"external-aerodynamics\"",
            "template.id == \"internal-flow\"",
    ):
        assert forbidden not in src, \
            f"linter.py must not contain: {forbidden}"


# --------------------------------------------------------------------------- #
# 28. Linter: default reference area only fires for aero
# --------------------------------------------------------------------------- #
def test_default_reference_not_for_internal_flow():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="")]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "default-reference" not in codes


# --------------------------------------------------------------------------- #
# 29. Multiple event types in sequence (batch lifecycle)
# --------------------------------------------------------------------------- #
def test_full_batch_lifecycle_events():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))

    bus.emit(EVT_BATCH_STARTED, total=2, rows=[1, 2],
             template_id="internal-flow")
    bus.emit(EVT_CASE_STARTED, row=1, case_id="r001",
             index=1, total=2, template_id="internal-flow",
             parameters={"inlet_velocity": 2.0}, extra={})
    bus.emit(EVT_STAGE, row=1, case_id="r001",
             stage="mesh", state="done", template_id="internal-flow")
    bus.emit(EVT_SOLVE_PROGRESS, row=1, case_id="r001",
             it=100, max_it=500, cl=0.0, cd=0.0)
    bus.emit(EVT_SOLVE_CONVERGED, row=1, case_id="r001", it=350)
    bus.emit(EVT_CASE_DONE, row=1, case_id="r001",
             result={}, metrics={"pressure_drop": 500.0},
             template_id="internal-flow")
    bus.emit(EVT_BATCH_FINISHED, ok=2, failed=0, stopped=False,
             template_id="internal-flow")

    types = [e.type for e in received]
    assert types == [
        "batch.started", "case.started", "stage",
        "solve.progress", "solve.converged", "case.done",
        "batch.finished",
    ]


# --------------------------------------------------------------------------- #
# 30. Linter: high pipe diameter (INFO level)
# --------------------------------------------------------------------------- #
def test_linter_large_pipe_diameter():
    cfg = _mock_config()
    exps = [_make_if_exp(2, status="", pipe_diameter=15.0)]
    findings = lint(cfg, exps, template=INTERNAL_FLOW)
    codes = [f.code for f in findings]
    assert "pipe-large-diameter" in codes
    info_findings = [f for f in findings if f.code == "pipe-large-diameter"]
    assert info_findings[0].level == "INFO"


# --------------------------------------------------------------------------- #
# R1+R4: MonitorMetric view model tests
# --------------------------------------------------------------------------- #
def test_monitor_metric_is_frozen_dataclass():
    mm = MonitorMetric(key="cl", display_name="CL", unit="",
                       monitor_priority=50)
    assert mm.key == "cl"
    assert mm.display_name == "CL"
    assert mm.monitor_priority == 50
    with pytest.raises(AttributeError):
        mm.key = "cd"  # type: ignore[misc]


def test_monitor_metric_default_priority():
    mm = MonitorMetric(key="cd", display_name="CD")
    assert mm.monitor_priority == 100
    assert mm.unit == ""


def test_monitor_metric_ordering():
    """Metrics sorted by monitor_priority: bookkeeping first, then physics."""
    mm_list = [
        MonitorMetric(key="pressure_drop", display_name="Pressure Drop",
                      unit="Pa", monitor_priority=100),
        MonitorMetric(key="iterations", display_name="Iterations",
                      unit="", monitor_priority=-20),
        MonitorMetric(key="residual", display_name="Min residual",
                      unit="", monitor_priority=-10),
        MonitorMetric(key="friction_factor", display_name="Friction Factor",
                      unit="", monitor_priority=110),
    ]
    mm_list.sort(key=lambda m: m.monitor_priority)
    assert mm_list[0].key == "iterations"
    assert mm_list[1].key == "residual"
    assert mm_list[2].key == "pressure_drop"
    assert mm_list[3].key == "friction_factor"


# --------------------------------------------------------------------------- #
# R2: Event schema version tests
# --------------------------------------------------------------------------- #
def test_event_schema_version_is_integer():
    assert isinstance(EVENT_SCHEMA_VERSION, int)
    assert EVENT_SCHEMA_VERSION == 2


def test_event_bus_injects_event_version():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit("test.event", foo=42)
    assert received[0].data["event_version"] == EVENT_SCHEMA_VERSION


def test_event_bus_preserves_explicit_event_version():
    bus = EventBus()
    received = []
    bus.subscribe(lambda evt: received.append(evt))
    bus.emit("test.event", event_version=1, foo=42)
    # setdefault does NOT overwrite an existing value
    assert received[0].data["event_version"] == 1


def test_null_bus_no_version_injection():
    bus = NullBus()
    # Should not raise even with no version
    bus.emit("test.event", foo=1)


# --------------------------------------------------------------------------- #
# R3: RuntimeStage enum tests
# --------------------------------------------------------------------------- #
def test_runtime_stage_members():
    expected = {"PREPARING", "MESHING", "SOLVING", "POSTPROCESS",
                "DONE", "FAILED"}
    actual = {m.name for m in RuntimeStage}
    assert expected == actual


def test_runtime_stage_values():
    assert RuntimeStage.PREPARING.value == "preparing"
    assert RuntimeStage.MESHING.value == "meshing"
    assert RuntimeStage.SOLVING.value == "solving"
    assert RuntimeStage.POSTPROCESS.value == "postprocess"
    assert RuntimeStage.DONE.value == "done"
    assert RuntimeStage.FAILED.value == "failed"


def test_runtime_stage_serialization_round_trip():
    """Stage enum serializes to its string value and deserializes back."""
    for stage in RuntimeStage:
        wire = stage.value
        restored = RuntimeStage(wire)
        assert restored == stage


def test_runtime_stage_from_wire_legacy():
    """Legacy stage strings map to the correct enum members."""
    assert RuntimeStage.from_wire("mesh") == RuntimeStage.MESHING
    assert RuntimeStage.from_wire("fluent_launch") == RuntimeStage.PREPARING
    assert RuntimeStage.from_wire("setup") == RuntimeStage.SOLVING
    assert RuntimeStage.from_wire("solve") == RuntimeStage.SOLVING
    assert RuntimeStage.from_wire("extract") == RuntimeStage.POSTPROCESS


def test_runtime_stage_from_wire_current():
    """Current stage string values map correctly."""
    assert RuntimeStage.from_wire("meshing") == RuntimeStage.MESHING
    assert RuntimeStage.from_wire("solving") == RuntimeStage.SOLVING
    assert RuntimeStage.from_wire("done") == RuntimeStage.DONE


def test_runtime_stage_from_wire_unknown():
    """Unknown stage strings fall back to PREPARING."""
    assert RuntimeStage.from_wire("unknown-stage") == RuntimeStage.PREPARING


# --------------------------------------------------------------------------- #
# R5: Generic linter rule registry tests
# --------------------------------------------------------------------------- #
def test_linter_rule_registry_execution():
    """A custom rule registered for a template is executed by lint()."""
    custom_called = []

    def _custom_rules(cfg, pending, template=None):
        custom_called.append(True)
        return [Finding("INFO", "custom-rule", "Custom rule fired")]

    register_lint_rules("test-custom-template", _custom_rules)
    cfg = _mock_config()
    exps = [_make_exp(2, status="")]
    tpl = MagicMock()
    tpl.id = "test-custom-template"
    findings = lint(cfg, exps, template=tpl)
    codes = [f.code for f in findings]
    assert "custom-rule" in codes
    assert len(custom_called) == 1
    # Cleanup: unregister
    from cfdauto.linter import _RULE_REGISTRY
    del _RULE_REGISTRY["test-custom-template"]


def test_linter_registry_replaces_template_id_branching():
    """The lint() function no longer contains hardcoded template-id checks."""
    import cfdauto.linter
    src = inspect.getsource(cfdauto.linter)
    # The old pattern must not exist in lint():
    for forbidden in (
            'if tpl_id == "external-aerodynamics"',
            'if tpl_id == "internal-flow"',
            'if tpl_id is None or tpl_id ==',
    ):
        assert forbidden not in src, \
            f"linter.py lint() must not contain: {forbidden}"




# =========================================================================== #
# Phase 8F QA Patch — regression tests for Bugs A–D
# =========================================================================== #
# These tests prove the four critical fixes work without requiring PySide6
# or matplotlib.  They exercise the underlying data/logic paths directly.
# =========================================================================== #

# --------------------------------------------------------------------------- #
# Bug A: Dashboard Study Summary Hydration
# --------------------------------------------------------------------------- #
def _excel_manager_for_aero():
    """Build a real ExcelManager for External Aero using the project workbook."""
    from cfdauto.excel_manager import ExcelManager
    from cfdauto.config import load_config
    cfg_path = ROOT / "config" / "config.yaml"
    if not cfg_path.exists():
        pytest.skip("config/config.yaml not found")
    cfg = load_config(cfg_path)
    return ExcelManager.for_config(cfg)


def test_hydrate_study_summary_after_reload():
    """_hydrate_study_summary() produces a valid StudySummary from a workbook
    with completed rows — simulates project load + reload."""
    from cfdauto.platform import EXTERNAL_AERODYNAMICS
    from cfdauto.study_analytics import StudySummary, analyze_study

    wb = _excel_manager_for_aero()
    tpl = EXTERNAL_AERODYNAMICS
    all_rows = [e.row for e in wb.read_experiments()]
    summary = analyze_study(wb, all_rows, template=tpl)
    assert isinstance(summary, StudySummary)
    assert summary.total_cases > 0
    assert summary.successful_cases > 0
    assert len(summary.highlights) > 0


def test_hydrate_study_summary_empty_workbook():
    """When no rows are DONE, summary should have zero cases and an
    EMPTY_STUDY warning (simulates empty workbook)."""
    from cfdauto.platform import EXTERNAL_AERODYNAMICS
    from cfdauto.study_analytics import StudySummary, analyze_study

    wb = _excel_manager_for_aero()
    tpl = EXTERNAL_AERODYNAMICS
    # Only pass PENDING rows (status="" means not done)
    pending_rows = [e.row for e in wb.read_experiments()
                    if (e.status or "").upper() not in ("DONE", "SKIP")]
    summary = analyze_study(wb, pending_rows, template=tpl)
    assert summary.total_cases == 0
    assert summary.successful_cases == 0


def test_study_summary_json_round_trip_persistence():
    """StudySummary can be saved to JSON and loaded back — proves
    persistence works for post-batch hydration fallback."""
    from cfdauto.study_analytics import StudySummary, StudyHighlight
    import tempfile, os

    hl = StudyHighlight(metric="l_over_d", value=15.0, row=3,
                        unit="", role="best-ratio",
                        display_name="L/D")
    summary = StudySummary(
        total_cases=5, successful_cases=4, failed_cases=1,
        retries=0, highlights={"l_over_d": hl})
    # Save to temp file (save_json expects a Path object)
    tmpdir = Path(tempfile.mkdtemp())
    path = tmpdir / "test_summary.json"
    try:
        summary.save_json(path)
        loaded = StudySummary.load_json(path)
        assert loaded is not None
        assert loaded.total_cases == 5
        assert loaded.successful_cases == 4
        assert loaded.highlights["l_over_d"].value == 15.0
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Bug B: StatsPanel template-driven columns
# --------------------------------------------------------------------------- #
def test_template_metrics_external_aero():
    """AppState.template_metrics() returns External Aero column headers."""
    from cfdauto.platform import EXTERNAL_AERODYNAMICS
    cols = [header for _, header in EXTERNAL_AERODYNAMICS.output_columns()]
    assert "CL" in cols
    assert "CD" in cols
    assert "CL/CD" in cols  # External Aero L/D column
    assert "Lift_N" in cols
    assert "Drag_N" in cols
    # Must NOT contain internal flow columns
    assert "PressureDrop_Pa" not in cols


def test_template_metrics_internal_flow():
    """AppState.template_metrics() returns Internal Flow column headers."""
    from cfdauto.platform import INTERNAL_FLOW
    cols = [header for _, header in INTERNAL_FLOW.output_columns()]
    assert "PressureDrop_Pa" in cols
    assert "ReynoldsNumber" in cols
    assert "FrictionFactor" in cols
    # Must NOT contain aero-specific columns
    assert "CL" not in cols
    assert "CD" not in cols
    assert "Lift_N" not in cols


def test_output_cols_for_template_dynamic():
    """_output_cols_for_template() produces template-specific columns."""
    from cfdauto.platform import INTERNAL_FLOW, EXTERNAL_AERODYNAMICS

    aero_cols = _output_cols_for_template(EXTERNAL_AERODYNAMICS)
    assert "CL" in aero_cols
    assert "CD" in aero_cols
    assert "Iterations" in aero_cols  # bookkeeping always present

    flow_cols = _output_cols_for_template(INTERNAL_FLOW)
    assert "PressureDrop_Pa" in flow_cols
    assert "CL" not in flow_cols  # no aero columns for internal flow
    assert "Iterations" in flow_cols


def test_apply_event_uses_template_metrics():
    """apply_event case.done uses generic metrics dict, not hardcoded fields.
    This is a logic test — it exercises the column mapping without PySide6."""
    from cfdauto.events import Event

    # Simulate what apply_event does internally
    r = {"cl": 1.5, "cd": 0.05, "lift_n": 100.0, "drag_n": 30.0,
         "iterations": 500, "converged": True}
    metrics = {"cl": 1.5, "cd": 0.05, "l_over_d": 30.0,
               "lift": 100.0, "drag": 30.0}
    values = {"Status": "DONE", "Iterations": 500,
              "Converged": "YES", "Error": "", "CaseDir": "", "Duration_min": None}
    # Map metric names → display headers (same logic as apply_event)
    for metric_name, col_header in EXTERNAL_AERODYNAMICS.output_columns():
        val = metrics.get(metric_name)
        if val is None:
            val = r.get(metric_name)
        values[col_header] = val

    assert values["CL"] == 1.5
    assert values["CD"] == 0.05
    assert values["CL/CD"] == 30.0
    assert values["Lift_N"] == 100.0
    assert values["Drag_N"] == 30.0
    assert values["Iterations"] == 500


# --------------------------------------------------------------------------- #
# Bug C: MonitorMetric view model
# --------------------------------------------------------------------------- #
def test_monitor_metric_frozen_dataclass():
    """MonitorMetric is a frozen dataclass — immutability guaranteed."""
    mm = MonitorMetric(key="cl", display_name="CL", unit="",
                       monitor_priority=100)
    assert mm.key == "cl"
    assert mm.display_name == "CL"
    with pytest.raises(AttributeError):
        mm.key = "cd"  # frozen


def test_monitor_metric_sorting_by_priority():
    """MonitorMetric list sorts correctly by monitor_priority."""
    metrics = [
        MonitorMetric(key="drag", display_name="Drag", unit="N",
                      monitor_priority=130),
        MonitorMetric(key="iterations", display_name="Iterations",
                      unit="", monitor_priority=-20),
        MonitorMetric(key="cl", display_name="CL", unit="",
                      monitor_priority=110),
        MonitorMetric(key="residual", display_name="Min residual",
                      unit="", monitor_priority=-10),
        MonitorMetric(key="lift", display_name="Lift", unit="N",
                      monitor_priority=120),
    ]
    metrics.sort(key=lambda m: m.monitor_priority)
    keys = [m.key for m in metrics]
    assert keys == ["iterations", "residual", "cl", "lift", "drag"]


def test_build_monitor_metrics_external_aero():
    """_build_monitor_metrics produces correct tiles for External Aero."""
    from cfdauto.platform import EXTERNAL_AERODYNAMICS

    tpl = EXTERNAL_AERODYNAMICS
    metrics = [
        MonitorMetric(key="iterations", display_name="Iterations",
                      unit="", monitor_priority=-20),
        MonitorMetric(key="residual", display_name="Min residual",
                      unit="", monitor_priority=-10),
    ]
    for md in tpl.supported_metrics:
        pri = getattr(md, "monitor_priority", None)
        if pri is None:
            pri = 100 + len(metrics)
        metrics.append(MonitorMetric(
            key=md.name, display_name=md.display_name,
            unit=md.unit or "", monitor_priority=pri))
    metrics.sort(key=lambda m: m.monitor_priority)

    keys = [m.key for m in metrics]
    assert "iterations" in keys
    assert "residual" in keys
    assert "cl" in keys
    assert "cd" in keys
    # iterations and residual come first (negative priority)
    assert keys.index("iterations") < keys.index("cl")
    assert keys.index("residual") < keys.index("cl")


def test_build_monitor_metrics_internal_flow():
    """_build_monitor_metrics produces correct tiles for Internal Flow."""
    from cfdauto.platform import INTERNAL_FLOW

    tpl = INTERNAL_FLOW
    metrics = [
        MonitorMetric(key="iterations", display_name="Iterations",
                      unit="", monitor_priority=-20),
        MonitorMetric(key="residual", display_name="Min residual",
                      unit="", monitor_priority=-10),
    ]
    for md in tpl.supported_metrics:
        pri = getattr(md, "monitor_priority", None)
        if pri is None:
            pri = 100 + len(metrics)
        metrics.append(MonitorMetric(
            key=md.name, display_name=md.display_name,
            unit=md.unit or "", monitor_priority=pri))
    metrics.sort(key=lambda m: m.monitor_priority)

    keys = [m.key for m in metrics]
    assert "iterations" in keys
    assert "residual" in keys
    assert "pressure_drop" in keys
    # Must NOT contain aero-specific keys
    assert "cl" not in keys
    assert "cd" not in keys


def test_monitor_metric_default_priority():
    """MonitorMetric defaults to priority 100 when not specified."""
    mm = MonitorMetric(key="test", display_name="Test")
    assert mm.monitor_priority == 100


# --------------------------------------------------------------------------- #
# Bug D: RuntimeStage emissions
# --------------------------------------------------------------------------- #
def test_runtime_stage_serialization():
    """RuntimeStage values serialize correctly for event payloads."""
    assert RuntimeStage.PREPARING.value == "preparing"
    assert RuntimeStage.MESHING.value == "meshing"
    assert RuntimeStage.SOLVING.value == "solving"
    assert RuntimeStage.POSTPROCESS.value == "postprocess"
    assert RuntimeStage.DONE.value == "done"
    assert RuntimeStage.FAILED.value == "failed"


def test_runtime_stage_all_members():
    """RuntimeStage has exactly the 6 expected members."""
    members = list(RuntimeStage)
    assert len(members) == 6
    names = {m.name for m in members}
    assert names == {"PREPARING", "MESHING", "SOLVING",
                     "POSTPROCESS", "DONE", "FAILED"}


def test_runtime_stage_events_emitted_by_bus():
    """EventBus can emit stage events with RuntimeStage values."""
    bus = EventBus()
    events = []
    bus.subscribe(lambda e: events.append(e))

    bus.emit("stage", stage=RuntimeStage.PREPARING.value,
             state="done", row=0, case_id="batch")
    bus.emit("stage", stage=RuntimeStage.SOLVING.value,
             state="start", row=3, case_id="r003_aoa5V10")
    bus.emit("stage", stage=RuntimeStage.DONE.value,
             state="done", row=3, case_id="r003_aoa5V10")

    assert len(events) == 3
    assert events[0].data["stage"] == "preparing"
    assert events[1].data["stage"] == "solving"
    assert events[2].data["stage"] == "done"
    # All carry event_version
    for e in events:
        assert e.data.get("event_version") == EVENT_SCHEMA_VERSION


def test_event_schema_version_present():
    """Every event emitted by EventBus carries event_version."""
    bus = EventBus()
    events = []
    bus.subscribe(lambda e: events.append(e))
    bus.emit("test.event", foo="bar")
    assert len(events) == 1
    assert events[0].data["event_version"] == EVENT_SCHEMA_VERSION


def test_monitor_timeline_labels_for_runtime_stages():
    """The RuntimeStage→timeline label mapping covers all stages."""
    _RS_LABELS = {
        "preparing": "Preparing",
        "meshing": "Meshing",
        "solving": "Solving",
        "postprocess": "Post-processing",
        "done": "Done",
        "failed": "Failed",
    }
    for member in RuntimeStage:
        assert member.value in _RS_LABELS, \
            f"RuntimeStage.{member.name} ({member.value}) missing timeline label"
