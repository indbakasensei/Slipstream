"""Phase 8B — Generic Outputs & Metrics (v2.3.0-dev).

Makes the generic RESULT/output layer domain-neutral, the mirror image of
Phase 8A's generic Experiment layer:

    SimulationTemplate ──► supported/declarative metrics ──► CaseResult
        ──► generic metric storage (name / value / unit / status)
        ──► JSON / result representation

The platform must not assume every CFD study produces CL/CD/Lift/Drag. This
suite proves:

  * templates declare their own metrics (External Aero: cl/cd/l_over_d/lift/
    drag; Internal Flow: pressure_drop/reynolds_number/friction_factor);
  * a template-attached :class:`CaseResult` stores *template-defined* metric
    names and serializes generically (template / case_id / parameters /
    metrics / bookkeeping);
  * template-less legacy results keep the pre-Phase-8B shape byte-identically
    and their JSON stays readable;
  * generic serialization/deserialization round-trips for External Aero,
    Internal Flow, and a third non-aero canary template;
  * the generic output-column contract derives columns from the template
    (External Aero maps to the exact legacy headers);
  * the generic result model contains no template-id branching.

Per the Phase 8B scope firewall this is deliberately *not* an Excel/ledger/
analytics migration — the output-column contract is metadata + tests only.
"""

from __future__ import annotations

import inspect
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import ColumnMap, load_config                    # noqa: E402
from cfdauto.events import EventBus                                   # noqa: E402
from cfdauto.execution import (                                       # noqa: E402
    ExecutionContext,
    InternalFlowExecutionStrategy,
    strategy_for_template,
)
from cfdauto.experiment_definition import ExperimentDefinition        # noqa: E402
from cfdauto.models import CaseResult, MetricValue                    # noqa: E402
from cfdauto.platform import (EXTERNAL_AERODYNAMICS, INTERNAL_FLOW,   # noqa: E402
                              ParameterDefinition, ParameterType,
                              SimulationTemplate, StudyDefinition,
                              StudyParameter)
from cfdauto.platform.metrics import MetricDefinition                 # noqa: E402
from cfdauto.simulation_context import SimulationContext              # noqa: E402
from cfdauto.state import RunState                                    # noqa: E402
from tools.make_experiment_template import build_template             # noqa: E402

_LEGACY_JSON_KEYS = [
    "cl", "cd", "lift_n", "drag_n", "iterations", "converged", "error",
    "started", "finished", "mesh_file", "artifact_dir",
    "cl_over_cd", "fl_over_fd", "duration_min",
]


# --------------------------------------------------------------------------- #
# 1. Template metric declarations — the template owns its output vocabulary
# --------------------------------------------------------------------------- #
def test_internal_flow_template_declares_its_metrics():
    names = {m.name for m in INTERNAL_FLOW.supported_metrics}
    assert names == {"pressure_drop", "reynolds_number", "friction_factor"}
    assert INTERNAL_FLOW.metric("pressure_drop").display_name == "Pressure Drop"
    assert INTERNAL_FLOW.metric("pressure_drop").unit == "Pa"
    assert INTERNAL_FLOW.metric("reynolds_number").unit == ""
    assert INTERNAL_FLOW.metric("friction_factor").unit == ""


def test_external_aero_template_declares_its_metrics():
    names = {m.name for m in EXTERNAL_AERODYNAMICS.supported_metrics}
    assert names == {"cl", "cd", "l_over_d", "lift", "drag"}
    assert EXTERNAL_AERODYNAMICS.metric("lift").unit == "N"
    assert EXTERNAL_AERODYNAMICS.metric("drag").unit == "N"
    assert EXTERNAL_AERODYNAMICS.metric("cl").unit == ""
    assert EXTERNAL_AERODYNAMICS.metric("cd").unit == ""


# --------------------------------------------------------------------------- #
# 2. Generic output-column contract (Phase 8B §16) — template → declared
#    output metrics → output columns. Metadata only; Excel writing is 8C.
# --------------------------------------------------------------------------- #
def test_external_aero_output_columns_match_legacy_column_map():
    columns = dict(EXTERNAL_AERODYNAMICS.output_columns())
    # The four physical metrics map to the exact legacy ColumnMap headers —
    # the generic declaration reproduces today's aero output layer.
    legacy = ColumnMap()
    assert columns["cl"] == legacy.cl == "CL"
    assert columns["cd"] == legacy.cd == "CD"
    assert columns["lift"] == legacy.lift == "Lift_N"
    assert columns["drag"] == legacy.drag == "Drag_N"
    # The ratio column mirrors the legacy CL/CD header too.
    assert columns["l_over_d"] == legacy.cl_cd == "CL/CD"


def test_internal_flow_output_columns_declared():
    assert INTERNAL_FLOW.output_columns() == (
        ("pressure_drop", "PressureDrop_Pa"),
        ("reynolds_number", "ReynoldsNumber"),
        ("friction_factor", "FrictionFactor"),
    )


def test_output_column_falls_back_to_display_name():
    # A metric without an explicit output_column renders its display name.
    m = MetricDefinition(id="x", name="x", display_name="My Column")
    assert (m.name, m.output_column or m.display_name) == ("x", "My Column")


# --------------------------------------------------------------------------- #
# 3. Internal Flow CaseResult — genuine generic result, no aero fields
# --------------------------------------------------------------------------- #
def test_internal_flow_case_result_has_no_aero_metrics():
    res = CaseResult(
        template=INTERNAL_FLOW,
        metrics={
            "pressure_drop": MetricValue("pressure_drop", 711.16, "Pa"),
            "reynolds_number": MetricValue("reynolds_number", 99620.8, ""),
            "friction_factor": MetricValue("friction_factor", 0.017809, ""),
        })
    assert set(res.metrics_dict()) == {
        "pressure_drop", "reynolds_number", "friction_factor"}
    # Mandatory-aero metrics are simply absent — and the legacy accessors
    # report None rather than raising or fabricating a value.
    assert res.cl is None and res.cd is None
    assert res.lift_n is None and res.drag_n is None


def test_internal_flow_case_result_metric_values_and_units():
    res = CaseResult(
        template=INTERNAL_FLOW,
        metrics={
            "pressure_drop": MetricValue("pressure_drop", 711.16, "Pa"),
            "reynolds_number": MetricValue("reynolds_number", 99620.8, ""),
            "friction_factor": MetricValue("friction_factor", 0.017809, ""),
        })
    assert res.metric("pressure_drop").value == pytest.approx(711.16, rel=1e-6)
    assert res.metric("pressure_drop").unit == "Pa"
    assert res.metric("reynolds_number").value == pytest.approx(99620.8, rel=1e-6)
    assert res.metric("friction_factor").value == pytest.approx(0.017809, rel=1e-6)


def test_internal_flow_case_result_metric_units_from_template():
    # Passing plain floats (no MetricValue) must still attach the template's
    # declared units, not an empty fallback.
    res = CaseResult(template=INTERNAL_FLOW,
                     metrics={"pressure_drop": 711.16})
    assert res.metric("pressure_drop").unit == "Pa"


# --------------------------------------------------------------------------- #
# 4. External Aero GOLDEN compatibility (Phase 8B §9, §17)
# --------------------------------------------------------------------------- #
def test_external_aero_template_attached_uses_template_metric_names():
    # Same legacy call, but a template attached → the generic representation
    # keys by the template's declared metric names (lift/drag, not lift_n/
    # drag_n).
    res = CaseResult(template=EXTERNAL_AERODYNAMICS,
                     cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    assert set(res.metrics_dict()) == {"cl", "cd", "lift", "drag"}
    assert res.metric("lift").value == 5.0
    assert res.metric("lift").unit == "N"          # unit from the template
    assert res.metric("drag").unit == "N"


def test_external_aero_legacy_accessors_still_work_when_attached():
    res = CaseResult(template=EXTERNAL_AERODYNAMICS,
                     cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    # The compatibility accessors keep working over the template-named store.
    assert res.cl == 0.51 and res.cd == 0.018
    assert res.lift_n == 5.0 and res.drag_n == 0.18
    assert res.cl_over_cd == pytest.approx(0.51 / 0.018)
    assert res.fl_over_fd == pytest.approx(5.0 / 0.18)
    # Assigning through the legacy accessor writes the template metric.
    res.lift_n = 6.0
    assert res.metric("lift").value == 6.0


def test_legacy_template_less_case_result_unchanged():
    res = CaseResult(cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    assert set(res.metrics_dict()) == {"cl", "cd", "lift_n", "drag_n"}
    assert res.metrics["lift_n"].unit == "N"
    assert res.cl_over_cd == pytest.approx(0.51 / 0.018)


def test_generic_representation_contains_same_physical_values():
    legacy = CaseResult(cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    generic = CaseResult(template=EXTERNAL_AERODYNAMICS,
                         cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    assert generic.metric("cl").value == legacy.metric("cl").value == 0.51
    assert generic.metric("cd").value == legacy.metric("cd").value == 0.018
    assert generic.metric("lift").value == legacy.metric("lift_n").value == 5.0
    assert generic.metric("drag").value == legacy.metric("drag_n").value == 0.18
    # Legacy JSON values are identical too (same numbers, same derived fields).
    assert generic.to_json_dict()["metrics"]["cl"]["value"] == \
        legacy.to_json_dict()["cl"] == 0.51


# --------------------------------------------------------------------------- #
# 5. Serialization
# --------------------------------------------------------------------------- #
def test_generic_serialization_shape():
    res = CaseResult(
        template=INTERNAL_FLOW, case_id="r002_inlet_velocity2",
        parameters={"inlet_velocity": 2.0, "pipe_diameter": 0.05},
        metrics={
            "pressure_drop": MetricValue("pressure_drop", 711.16, "Pa"),
            "reynolds_number": MetricValue("reynolds_number", 99620.8, ""),
        },
        iterations=120, converged=True)
    d = res.to_json_dict()
    assert set(d) == {"template", "case_id", "parameters", "metrics",
                      "bookkeeping"}
    assert d["template"] == "internal-flow"
    assert d["case_id"] == "r002_inlet_velocity2"
    assert d["parameters"] == {"inlet_velocity": 2.0, "pipe_diameter": 0.05}
    # Per-metric value/unit/status, keyed by template metric name.
    assert d["metrics"]["pressure_drop"] == {
        "value": 711.16, "unit": "Pa", "status": "computed"}
    assert "cl" not in d["metrics"] and "lift_n" not in d["metrics"]
    assert d["bookkeeping"]["iterations"] == 120
    assert d["bookkeeping"]["converged"] is True


def test_generic_serialization_is_json_deterministic():
    kwargs = dict(
        template=INTERNAL_FLOW, case_id="r1",
        parameters={"inlet_velocity": 2.0},
        metrics={"pressure_drop": MetricValue("pressure_drop", 711.16, "Pa")},
        started=datetime(2026, 1, 2, 3, 4, 5),
        finished=datetime(2026, 1, 2, 3, 14, 5))
    a = json.dumps(CaseResult(**kwargs).to_json_dict(), sort_keys=True)
    b = json.dumps(CaseResult(**kwargs).to_json_dict(), sort_keys=True)
    assert a == b
    # No Python-only objects survive — it round-trips through real JSON.
    assert json.loads(a)["bookkeeping"]["started"] == "2026-01-02T03:04:05"


def test_legacy_serialization_is_byte_identical():
    res = CaseResult(cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    d = res.to_json_dict()
    assert list(d) == _LEGACY_JSON_KEYS        # exact key order preserved
    assert d["cl_over_cd"] == pytest.approx(0.51 / 0.018)
    assert d["fl_over_fd"] == pytest.approx(5.0 / 0.18)
    assert d["duration_min"] is None


# --------------------------------------------------------------------------- #
# 6. Deserialization + round-trip (Phase 8B §13–§14)
# --------------------------------------------------------------------------- #
def test_round_trip_external_aero_with_template_object():
    res = CaseResult(template=EXTERNAL_AERODYNAMICS, case_id="r001_aoa0_v10",
                     parameters={"aoa": 0.0, "velocity": 10.0},
                     cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18)
    rt = CaseResult.from_json_dict(res.to_json_dict(),
                                   template=EXTERNAL_AERODYNAMICS)
    assert rt.template is EXTERNAL_AERODYNAMICS
    assert rt.case_id == res.case_id
    assert rt.parameters == res.parameters
    assert rt.metrics_dict() == res.metrics_dict()      # metric names survive
    for name in ("cl", "cd", "lift", "drag"):
        assert rt.metric(name).unit == res.metric(name).unit
    assert rt.converged == res.converged


def test_round_trip_internal_flow_resolves_template_by_id():
    res = CaseResult(
        template=INTERNAL_FLOW, case_id="r002_inlet_velocity2",
        parameters={"inlet_velocity": 2.0, "pipe_diameter": 0.05},
        metrics={
            "pressure_drop": MetricValue("pressure_drop", 711.16, "Pa",
                                         status="computed"),
            "reynolds_number": MetricValue("reynolds_number", 99620.8, ""),
            "friction_factor": MetricValue("friction_factor", 0.017809, ""),
        })
    payload = res.to_json_dict()
    # No template object passed — resolved from the platform registry by id.
    rt = CaseResult.from_json_dict(payload)
    assert rt.template is INTERNAL_FLOW
    assert rt.case_id == "r002_inlet_velocity2"
    assert rt.metrics_dict() == res.metrics_dict()
    assert rt.metric("pressure_drop").unit == "Pa"
    assert rt.metric("pressure_drop").status == "computed"


def test_round_trip_legacy_json_remains_readable():
    res = CaseResult(cl=0.51, cd=0.018, lift_n=5.0, drag_n=0.18,
                     iterations=200, converged=True)
    payload = res.to_json_dict()
    assert "template" not in payload          # legacy shape has no template
    rt = CaseResult.from_json_dict(payload)
    assert rt.metrics_dict() == res.metrics_dict()
    assert rt.iterations == 200 and rt.converged is True
    assert rt.cl_over_cd == pytest.approx(res.cl_over_cd)


def test_round_trip_with_datetime_bookkeeping():
    res = CaseResult(
        template=INTERNAL_FLOW, case_id="r1",
        metrics={"pressure_drop": MetricValue("pressure_drop", 711.16, "Pa")},
        started=datetime(2026, 1, 2, 3, 4, 5),
        finished=datetime(2026, 1, 2, 3, 14, 5))
    rt = CaseResult.from_json_dict(res.to_json_dict())
    assert rt.started == datetime(2026, 1, 2, 3, 4, 5)
    assert rt.finished == datetime(2026, 1, 2, 3, 14, 5)
    assert rt.duration_min == pytest.approx(10.0)


def test_from_json_dict_unknown_template_raises():
    payload = {"template": "no-such-template-id", "case_id": "x",
               "parameters": {}, "metrics": {}, "bookkeeping": {}}
    with pytest.raises(ValueError):
        CaseResult.from_json_dict(payload)


# --------------------------------------------------------------------------- #
# 7. Third-template canary — arbitrary non-aero metrics (Phase 8B §12)
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
                     source="solver-report", output_column="HeatRate_W",
                     description="Heat removed by the mixing coil."),
    MetricDefinition(id="efficiency", name="efficiency",
                     display_name="Efficiency", unit="",
                     source="derived",
                     description="Thermal efficiency."),
    MetricDefinition(id="vapor-fraction", name="vapor_fraction",
                     display_name="Vapor Fraction", unit="",
                     source="solver-report",
                     description="Mass fraction of vapor at the outlet."),
)

CANARY_TEMPLATE = SimulationTemplate(
    id="mixing-tank-canary",
    name="Mixing Tank (Phase 8B canary)",
    description=("Test-only third template proving the generic RESULT layer "
                 "handles arbitrary non-aero metrics — heat rate, efficiency, "
                 "vapor fraction. Not a production template; no strategy is "
                 "registered."),
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


def _canary_result():
    return CaseResult(
        template=CANARY_TEMPLATE, case_id="c001_tank_radius0.5",
        parameters={"tank_radius": 0.5, "inlet_temperature": 300.0},
        metrics={
            "heat_rate": MetricValue("heat_rate", 45.7, "W"),
            "efficiency": MetricValue("efficiency", 0.83, ""),
            "vapor_fraction": MetricValue("vapor_fraction", 0.02, ""),
        },
        converged=True)


def test_canary_round_trip():
    res = _canary_result()
    payload = res.to_json_dict()
    assert "cl" not in json.dumps(payload) and "drag" not in json.dumps(payload)
    rt = CaseResult.from_json_dict(payload, template=CANARY_TEMPLATE)
    assert rt.template is CANARY_TEMPLATE
    assert rt.case_id == res.case_id
    assert rt.metrics_dict() == res.metrics_dict()
    assert rt.metric("heat_rate").unit == "W"


def test_canary_output_columns_have_no_aero_columns():
    columns = dict(CANARY_TEMPLATE.output_columns())
    assert columns == {"heat_rate": "HeatRate_W",      # explicit output_column
                       "efficiency": "Efficiency",     # display_name fallback
                       "vapor_fraction": "Vapor Fraction"}
    assert "CL" not in columns.values() and "Lift_N" not in columns.values()


# --------------------------------------------------------------------------- #
# 8. Execution integration — a real Internal Flow run serializes generically
# --------------------------------------------------------------------------- #
class _RecordingMesh:
    def prepare_mesh(self, exp, case_dir):
        p = Path(case_dir) / "FFF.msh.h5"
        p.write_text(f"pipe mesh for {exp.geometry_key}")
        return p


def _internal_flow_context(tmp_path):
    """Minimal ExecutionContext for the Internal Flow template (mirrors
    tests/test_internal_flow_execution.py)."""
    xlsx = tmp_path / "placeholder.xlsx"
    build_template(xlsx)
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
        work_dir=cfg.work_dir(), mesh_backend=_RecordingMesh(), experiments=[])


def test_internal_flow_execute_case_serializes_generically(tmp_path):
    ctx = _internal_flow_context(tmp_path)
    strat = strategy_for_template(INTERNAL_FLOW)
    assert isinstance(strat, InternalFlowExecutionStrategy)
    exp = ExperimentDefinition.from_context(
        SimulationContext(template=INTERNAL_FLOW)).build_experiment(
        row=2, values={"inlet_velocity": 2.0, "fluid_density": 998.2,
                       "fluid_viscosity": 1.002e-3, "pipe_diameter": 0.05,
                       "pipe_length": 1.0})
    res = strat.execute_case(exp, ctx, ctx.state.case_dir(exp))

    # The executed result is a *generic* result: template-attached, generic
    # serialization, template-defined metrics — and NO airfoil fields.
    d = res.to_json_dict()
    assert d["template"] == "internal-flow"
    assert d["case_id"] == exp.case_id
    assert d["parameters"] == exp.parameters_dict()
    assert set(d["metrics"]) == {"pressure_drop", "reynolds_number",
                                 "friction_factor"}
    assert d["metrics"]["pressure_drop"]["unit"] == "Pa"
    assert "cl" not in d["metrics"] and "lift" not in d["metrics"]
    assert d["bookkeeping"]["converged"] is True
    # And it deserializes back to an equivalent generic result.
    rt = CaseResult.from_json_dict(d)
    assert rt.metrics_dict() == res.metrics_dict()
    assert rt.template is INTERNAL_FLOW


# --------------------------------------------------------------------------- #
# 9. Static — the generic result model contains no template-id branching
# --------------------------------------------------------------------------- #
def test_generic_result_core_has_no_template_branching():
    import cfdauto.models
    src = inspect.getsource(cfdauto.models)
    for forbidden in (
            'if template == "external-aerodynamics"',
            'if template == "internal-flow"',
            'if template.id == "external-aerodynamics"',
            'if template.id == "internal-flow"',
            'self.template == "external-aerodynamics"',
            'self.template == "internal-flow"',
            'template == "external-aerodynamics"',
            'template == "internal-flow"'):
        assert forbidden not in src, \
            f"generic result model must not contain: {forbidden}"
