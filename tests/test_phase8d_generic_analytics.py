"""Phase 8D — Generic Analytics Engine (v2.3.0-dev).

Removes the final hardcoded External Aerodynamics assumptions from analytics
while preserving backward compatibility. Analytics becomes template-driven:

    SimulationTemplate ──► supported_metrics (with analytics_role)
        ──► analyze_study(template=) ──► StudySummary.highlights

This suite proves:

  * MetricDefinition gains an optional ``analytics_role`` field;
  * External Aero metrics declare analytics roles (best-ratio, highest,
    lowest) that reproduce the legacy hard-coded highlights;
  * Internal Flow metrics declare analytics roles (lowest for pressure
    drop and friction factor);
  * a third-template canary with custom roles works;
  * StudyHighlight is a frozen dataclass with metric/value/row/unit/role;
  * analyze_study() with a template produces generic ``highlights``;
  * analyze_study() without a template uses the legacy hard-coded path
    (backward compatible for pre-Phase-8D callers);
  * External Aero highlights map to the legacy StudySummary fields
    (best_l_over_d, highest_lift_n, lowest_drag_n);
  * tie-breaking is deterministic (strict > / <, first-wins);
  * non-finite values are skipped;
  * failed cases are excluded from highlights;
  * the analytics module contains no template-id branching.

Per the Phase 8D scope firewall the GUI, ledger, excel_manager, state,
and execution are untouched.
"""

from __future__ import annotations

import inspect
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.models import (                             # noqa: E402
    Experiment, MetricValue, STATUS_DONE, STATUS_FAILED,
)
from cfdauto.platform import (                           # noqa: E402
    EXTERNAL_AERODYNAMICS, INTERNAL_FLOW,
    ParameterDefinition, ParameterType,
    SimulationTemplate, StudyDefinition, StudyParameter,
)
from cfdauto.platform.metrics import (                   # noqa: E402
    ANALYTICS_BEST_RATIO, ANALYTICS_HIGHEST,
    ANALYTICS_LOWEST, MetricDefinition,
    SOURCE_DERIVED, SOURCE_SOLVER_REPORT,
)
from cfdauto.study_analytics import (                    # noqa: E402
    StudyHighlight, StudySummary, StudyWarning, WarningCode,
    analyze_study,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _mock_excel(rows_data: Dict[int, Dict[str, object]],
                experiments: list,
                template=None):
    """Build a mock ExcelManager that returns the given row data.

    ``rows_data`` maps row number → the dict that ``read_row_outputs()``
    should return. ``experiments`` is the list ``read_experiments()`` returns.
    When ``template`` is provided, ``read_row_metrics()`` builds MetricValues
    from the template's declared output_columns().
    """
    excel = MagicMock()
    excel.read_experiments.return_value = experiments
    excel.read_row_outputs.side_effect = lambda row: rows_data.get(row, {})

    if template is not None:
        output_cols = dict(template.output_columns())  # metric_name → header
        def _read_metrics(row):
            out = {}
            data = rows_data.get(row, {})
            for metric_name, header in output_cols.items():
                md = template.metric(metric_name)
                unit = md.unit if md else ""
                val = data.get(header)
                out[metric_name] = MetricValue(
                    metric_name, float(val) if val is not None else None, unit)
            return out
        excel.read_row_metrics.side_effect = _read_metrics
    else:
        excel.read_row_metrics.side_effect = lambda row: {}

    return excel


def _make_exp(row: int, status=STATUS_DONE):
    """Build a minimal Experiment for test purposes."""
    exp = MagicMock(spec=Experiment)
    exp.row = row
    exp.status = status
    exp.parameters = {}
    return exp


# Third-template canary with analytics roles (test-only, not production).
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
                     analytics_role=ANALYTICS_LOWEST,
                     description="Heat removed by the mixing coil."),
    MetricDefinition(id="efficiency", name="efficiency",
                     display_name="Efficiency", unit="",
                     source=SOURCE_DERIVED,
                     analytics_role=ANALYTICS_HIGHEST,
                     description="Thermal efficiency."),
    MetricDefinition(id="vapor-fraction", name="vapor_fraction",
                     display_name="Vapor Fraction", unit="",
                     source=SOURCE_SOLVER_REPORT,
                     description="Mass fraction of vapor at the outlet."),
)

CANARY_TEMPLATE = SimulationTemplate(
    id="mixing-tank-canary",
    name="Mixing Tank (Phase 8D canary)",
    description="Test-only template with analytics roles.",
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
# 1. MetricDefinition gains analytics_role field
# --------------------------------------------------------------------------- #
def test_metric_definition_has_analytics_role_field():
    md = MetricDefinition(id="x", name="x", display_name="X")
    assert md.analytics_role is None     # default


def test_metric_definition_analytics_role_settable():
    md = MetricDefinition(id="x", name="x", display_name="X",
                          analytics_role=ANALYTICS_BEST_RATIO)
    assert md.analytics_role == ANALYTICS_BEST_RATIO


# --------------------------------------------------------------------------- #
# 2. External Aero metrics declare analytics roles
# --------------------------------------------------------------------------- #
def test_external_aero_metrics_have_analytics_roles():
    for md in EXTERNAL_AERODYNAMICS.supported_metrics:
        if md.name == "l_over_d":
            assert md.analytics_role == ANALYTICS_BEST_RATIO
        elif md.name == "lift":
            assert md.analytics_role == ANALYTICS_HIGHEST
        elif md.name == "drag":
            assert md.analytics_role == ANALYTICS_LOWEST
        elif md.name in ("cl", "cd"):
            assert md.analytics_role is None  # raw coefficients, no highlight


# --------------------------------------------------------------------------- #
# 3. Internal Flow metrics declare analytics roles
# --------------------------------------------------------------------------- #
def test_internal_flow_metrics_have_correct_analytics_roles():
    for md in INTERNAL_FLOW.supported_metrics:
        if md.name == "pressure_drop":
            assert md.analytics_role == ANALYTICS_LOWEST
        elif md.name == "friction_factor":
            assert md.analytics_role == ANALYTICS_LOWEST
        elif md.name == "reynolds_number":
            assert md.analytics_role is None  # flow regime indicator, not optimisation target


# --------------------------------------------------------------------------- #
# 4. Canary template with analytics roles
# --------------------------------------------------------------------------- #
def test_canary_metrics_have_correct_analytics_roles():
    for md in CANARY_TEMPLATE.supported_metrics:
        if md.name == "heat_rate":
            assert md.analytics_role == ANALYTICS_LOWEST
        elif md.name == "efficiency":
            assert md.analytics_role == ANALYTICS_HIGHEST
        elif md.name == "vapor_fraction":
            assert md.analytics_role is None


# --------------------------------------------------------------------------- #
# 5. StudyHighlight dataclass is frozen and has correct fields
# --------------------------------------------------------------------------- #
def test_study_highlight_is_frozen_dataclass():
    hl = StudyHighlight(metric="lift", value=50.0, row=3, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    assert hl.metric == "lift"
    assert hl.value == 50.0
    assert hl.row == 3
    assert hl.unit == "N"
    assert hl.role == ANALYTICS_HIGHEST
    assert hl.display_name == "Lift"
    # Frozen: assignment must raise
    with pytest.raises(AttributeError):
        hl.value = 999.0  # type: ignore[misc]


def test_study_highlight_to_dict():
    hl = StudyHighlight(metric="lift", value=50.0, row=3, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    d = asdict(hl)
    assert d == {"metric": "lift", "value": 50.0, "row": 3, "unit": "N",
                 "role": "highest", "display_name": "Lift"}


# --------------------------------------------------------------------------- #
# 6. StudySummary has highlights dict of StudyHighlight
# --------------------------------------------------------------------------- #
def test_study_summary_has_highlights_dict():
    s = StudySummary()
    assert isinstance(s.highlights, dict)
    assert len(s.highlights) == 0


def test_study_summary_highlights_hold_study_highlight_objects():
    s = StudySummary()
    hl = StudyHighlight(metric="lift", value=100.0, row=3, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    s.highlights["lift"] = hl
    assert s.highlights["lift"] is hl
    assert isinstance(s.highlights["lift"], StudyHighlight)


# --------------------------------------------------------------------------- #
# 7. External Aero highlights
# --------------------------------------------------------------------------- #
def test_external_aero_analyze_study_produces_highlights():
    exps = [_make_exp(2), _make_exp(3), _make_exp(4)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 12.0, "Lift_N": 60.0, "Drag_N": 4.0,
            "Iterations": 250, "Converged": "YES"},
        4: {"CL/CD": 8.0, "Lift_N": 40.0, "Drag_N": 6.0,
            "Iterations": 400, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3, 4], template=EXTERNAL_AERODYNAMICS)

    assert len(summary.highlights) > 0
    hl = summary.highlights["l_over_d"]
    assert isinstance(hl, StudyHighlight)
    assert hl.value == pytest.approx(12.0)
    assert hl.row == 3
    assert hl.role == ANALYTICS_BEST_RATIO

    hl = summary.highlights["lift"]
    assert hl.value == pytest.approx(60.0)
    assert hl.row == 3
    assert hl.role == ANALYTICS_HIGHEST

    hl = summary.highlights["drag"]
    assert hl.value == pytest.approx(4.0)
    assert hl.row == 3
    assert hl.role == ANALYTICS_LOWEST


# --------------------------------------------------------------------------- #
# 8. Legacy path (no template)
# --------------------------------------------------------------------------- #
def test_analyze_study_without_template_uses_legacy_path():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"cl_cd": 10.0, "lift": 50.0, "drag": 5.0,
            "iterations": 300, "converged": "YES"},
        3: {"cl_cd": 12.0, "lift": 60.0, "drag": 4.0,
            "iterations": 250, "converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps)
    summary = analyze_study(excel, [2, 3])  # no template

    assert summary.best_l_over_d == pytest.approx(12.0)
    assert summary.best_l_over_d_row == 3
    assert summary.highest_lift_n == pytest.approx(60.0)
    assert summary.highest_lift_row == 3
    assert summary.lowest_drag_n == pytest.approx(4.0)
    assert summary.lowest_drag_row == 3
    assert len(summary.highlights) == 0


# --------------------------------------------------------------------------- #
# 9. External Aero highlights map to legacy fields
# --------------------------------------------------------------------------- #
def test_external_aero_highlights_populate_legacy_fields():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 15.0, "Lift_N": 80.0, "Drag_N": 3.0,
            "Iterations": 200, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)

    assert summary.best_l_over_d == pytest.approx(15.0)
    assert summary.best_l_over_d_row == 3
    assert summary.highest_lift_n == pytest.approx(80.0)
    assert summary.highest_lift_row == 3
    assert summary.lowest_drag_n == pytest.approx(3.0)
    assert summary.lowest_drag_row == 3


# --------------------------------------------------------------------------- #
# 10. Internal Flow highlights (pressure_drop → lowest, friction_factor → lowest)
# --------------------------------------------------------------------------- #
def test_internal_flow_analyze_study_produces_highlights():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"PressureDrop_Pa": 700.0, "ReynoldsNumber": 50000.0,
            "FrictionFactor": 0.02, "Iterations": 120, "Converged": "YES"},
        3: {"PressureDrop_Pa": 500.0, "ReynoldsNumber": 60000.0,
            "FrictionFactor": 0.015, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=INTERNAL_FLOW)
    summary = analyze_study(excel, [2, 3], template=INTERNAL_FLOW)

    # pressure_drop: role=lowest → 500.0 at row 3
    assert "pressure_drop" in summary.highlights
    hl = summary.highlights["pressure_drop"]
    assert isinstance(hl, StudyHighlight)
    assert hl.value == pytest.approx(500.0)
    assert hl.row == 3
    assert hl.role == ANALYTICS_LOWEST
    assert hl.unit == "Pa"
    assert hl.display_name == "Pressure Drop"

    # friction_factor: role=lowest → 0.015 at row 3
    assert "friction_factor" in summary.highlights
    hl = summary.highlights["friction_factor"]
    assert hl.value == pytest.approx(0.015)
    assert hl.row == 3
    assert hl.role == ANALYTICS_LOWEST

    # reynolds_number: no role → no highlight
    assert "reynolds_number" not in summary.highlights

    # Legacy aero fields remain None
    assert summary.best_l_over_d is None
    assert summary.highest_lift_n is None
    assert summary.lowest_drag_n is None


# --------------------------------------------------------------------------- #
# 11. Canary multi-role template
# --------------------------------------------------------------------------- #
def test_canary_template_produces_highlights():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"HeatRate_W": 50.0, "Efficiency": 0.80,
            "Vapor Fraction": 0.02, "Iterations": 100, "Converged": "YES"},
        3: {"HeatRate_W": 40.0, "Efficiency": 0.85,
            "Vapor Fraction": 0.03, "Iterations": 120, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=CANARY_TEMPLATE)
    summary = analyze_study(excel, [2, 3], template=CANARY_TEMPLATE)

    hl = summary.highlights["heat_rate"]
    assert hl.value == pytest.approx(40.0)
    assert hl.row == 3
    assert hl.role == ANALYTICS_LOWEST

    hl = summary.highlights["efficiency"]
    assert hl.value == pytest.approx(0.85)
    assert hl.row == 3
    assert hl.role == ANALYTICS_HIGHEST

    # vapor_fraction: no role → no highlight
    assert "vapor_fraction" not in summary.highlights

    # No aero highlights
    assert "l_over_d" not in summary.highlights
    assert "lift" not in summary.highlights
    assert "drag" not in summary.highlights

    assert summary.best_l_over_d is None
    assert summary.highest_lift_n is None
    assert summary.lowest_drag_n is None


# --------------------------------------------------------------------------- #
# 12. Tie-breaking: first row wins (strict > / <)
# --------------------------------------------------------------------------- #
def test_tie_breaking_first_row_wins():
    exps = [_make_exp(2), _make_exp(3), _make_exp(4)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        4: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3, 4], template=EXTERNAL_AERODYNAMICS)

    assert summary.highlights["l_over_d"].row == 2
    assert summary.highlights["lift"].row == 2
    assert summary.highlights["drag"].row == 2


# --------------------------------------------------------------------------- #
# 13. Non-finite values are skipped
# --------------------------------------------------------------------------- #
def test_non_finite_values_are_skipped():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"CL/CD": float("nan"), "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 12.0, "Lift_N": float("inf"), "Drag_N": 4.0,
            "Iterations": 250, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)

    assert summary.highlights["l_over_d"].value == pytest.approx(12.0)
    assert summary.highlights["l_over_d"].row == 3
    assert summary.highlights["lift"].value == pytest.approx(50.0)
    assert summary.highlights["lift"].row == 2


# --------------------------------------------------------------------------- #
# 14. Empty study
# --------------------------------------------------------------------------- #
def test_empty_study_returns_empty_highlights():
    excel = _mock_excel({}, [], template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [], template=EXTERNAL_AERODYNAMICS)
    assert len(summary.highlights) == 0
    assert summary.total_cases == 0
    assert any(w.code == WarningCode.EMPTY_STUDY for w in summary.warnings)


# --------------------------------------------------------------------------- #
# 15. Failed cases are excluded from highlights
# --------------------------------------------------------------------------- #
def test_failed_cases_excluded_from_highlights():
    exps = [_make_exp(2), _make_exp(3, STATUS_FAILED), _make_exp(4)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 99.0, "Lift_N": 999.0, "Drag_N": 0.01,
            "Iterations": 1, "Converged": "NO"},
        4: {"CL/CD": 8.0, "Lift_N": 40.0, "Drag_N": 6.0,
            "Iterations": 400, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3, 4], template=EXTERNAL_AERODYNAMICS)

    # Row 3 is FAILED — its extreme values must NOT appear in highlights
    assert summary.highlights["l_over_d"].value == pytest.approx(10.0)
    assert summary.highlights["l_over_d"].row == 2
    assert summary.highlights["lift"].value == pytest.approx(50.0)
    assert summary.highlights["lift"].row == 2
    assert summary.highlights["drag"].value == pytest.approx(5.0)
    assert summary.highlights["drag"].row == 2
    assert summary.failed_cases == 1


# --------------------------------------------------------------------------- #
# 16. Unconverged cases tracked
# --------------------------------------------------------------------------- #
def test_unconverged_cases_with_template():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES",
            "iterations": 300, "converged": "YES"},
        3: {"CL/CD": 8.0, "Lift_N": 40.0, "Drag_N": 6.0,
            "Iterations": 500, "Converged": "NO",
            "iterations": 500, "converged": "NO"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)

    assert summary.successful_cases == 2
    assert any(w.code == WarningCode.UNCONVERGED_SUCCESS
               for w in summary.warnings)


# --------------------------------------------------------------------------- #
# 17. Retries tracked
# --------------------------------------------------------------------------- #
def test_retries_tracked_with_template():
    exps = [_make_exp(2)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2], retries=3,
                            template=EXTERNAL_AERODYNAMICS)

    assert summary.retries == 3
    assert any(w.code == WarningCode.RETRIES_OCCURRED
               for w in summary.warnings)


# --------------------------------------------------------------------------- #
# 18. Highlights contain metadata from template
# --------------------------------------------------------------------------- #
def test_highlights_contain_metadata_from_template():
    exps = [_make_exp(2)]
    rows_data = {
        2: {"Lift_N": 50.0, "Drag_N": 5.0, "CL/CD": 10.0,
            "Iterations": 300, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2], template=EXTERNAL_AERODYNAMICS)

    assert summary.highlights["lift"].display_name == "Lift"
    assert summary.highlights["lift"].unit == "N"
    assert summary.highlights["drag"].display_name == "Drag"
    assert summary.highlights["drag"].unit == "N"
    assert summary.highlights["l_over_d"].display_name == "L/D"
    assert summary.highlights["l_over_d"].unit == ""


# --------------------------------------------------------------------------- #
# 19. Fastest convergence still tracked (bookkeeping, not metric role)
# --------------------------------------------------------------------------- #
def test_fastest_convergence_tracked_from_bookkeeping():
    exps = [_make_exp(2), _make_exp(3)]
    # read_row_outputs() returns lowercase canonical keys (iterations,
    # converged); read_row_metrics() uses uppercase Excel column headers.
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 400, "Converged": "YES",
            "iterations": 400, "converged": "YES"},
        3: {"CL/CD": 8.0, "Lift_N": 40.0, "Drag_N": 6.0,
            "Iterations": 200, "Converged": "YES",
            "iterations": 200, "converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)

    # Fastest convergence is bookkeeping-derived, not a metric highlight
    assert summary.fastest_convergence_iterations == 200
    assert summary.fastest_convergence_row == 3


# --------------------------------------------------------------------------- #
# 20. StudyHighlight round-trip via asdict (Phase 9 Report API readiness)
# --------------------------------------------------------------------------- #
def test_study_highlight_round_trip_via_asdict():
    hl = StudyHighlight(metric="pressure_drop", value=500.0, row=3,
                        unit="Pa", role=ANALYTICS_LOWEST,
                        display_name="Pressure Drop")
    d = asdict(hl)
    restored = StudyHighlight(**d)
    assert restored == hl


# --------------------------------------------------------------------------- #
# 21. Duplicate highlight tie-breaking (strict comparison)
# --------------------------------------------------------------------------- #
def test_duplicate_highlight_tie_breaking_strict():
    """When two rows have identical values, the first row wins (strict > / <)."""
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"PressureDrop_Pa": 500.0, "FrictionFactor": 0.02,
            "ReynoldsNumber": 50000.0, "Iterations": 100, "Converged": "YES"},
        3: {"PressureDrop_Pa": 500.0, "FrictionFactor": 0.02,
            "ReynoldsNumber": 50000.0, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=INTERNAL_FLOW)
    summary = analyze_study(excel, [2, 3], template=INTERNAL_FLOW)

    assert summary.highlights["pressure_drop"].row == 2
    assert summary.highlights["friction_factor"].row == 2


# --------------------------------------------------------------------------- #
# 22. Internal Flow highlights have correct units and display names
# --------------------------------------------------------------------------- #
def test_internal_flow_highlights_have_metadata():
    exps = [_make_exp(2)]
    rows_data = {
        2: {"PressureDrop_Pa": 500.0, "ReynoldsNumber": 50000.0,
            "FrictionFactor": 0.02, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=INTERNAL_FLOW)
    summary = analyze_study(excel, [2], template=INTERNAL_FLOW)

    hl = summary.highlights["pressure_drop"]
    assert hl.unit == "Pa"
    assert hl.display_name == "Pressure Drop"

    hl = summary.highlights["friction_factor"]
    assert hl.unit == ""
    assert hl.display_name == "Friction Factor"


# --------------------------------------------------------------------------- #
# 23. Canary with mixed roles: lowest + highest + none
# --------------------------------------------------------------------------- #
def test_canary_multi_role_mixed_directions():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"HeatRate_W": 30.0, "Efficiency": 0.90,
            "Vapor Fraction": 0.01, "Iterations": 100, "Converged": "YES"},
        3: {"HeatRate_W": 60.0, "Efficiency": 0.70,
            "Vapor Fraction": 0.05, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=CANARY_TEMPLATE)
    summary = analyze_study(excel, [2, 3], template=CANARY_TEMPLATE)

    # heat_rate: lowest → 30.0 at row 2
    assert summary.highlights["heat_rate"].value == pytest.approx(30.0)
    assert summary.highlights["heat_rate"].row == 2
    # efficiency: highest → 0.90 at row 2
    assert summary.highlights["efficiency"].value == pytest.approx(0.90)
    assert summary.highlights["efficiency"].row == 2
    # vapor_fraction: no role → not in highlights
    assert "vapor_fraction" not in summary.highlights


# --------------------------------------------------------------------------- #
# 24. Retries warning with template path
# --------------------------------------------------------------------------- #
def test_retries_warning_with_template():
    exps = [_make_exp(2)]
    rows_data = {
        2: {"PressureDrop_Pa": 500.0, "ReynoldsNumber": 50000.0,
            "FrictionFactor": 0.02, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=INTERNAL_FLOW)
    summary = analyze_study(excel, [2], retries=2, template=INTERNAL_FLOW)

    assert summary.retries == 2
    assert any(w.code == WarningCode.RETRIES_OCCURRED
               for w in summary.warnings)


# --------------------------------------------------------------------------- #
# 25. Static — no template-id branching in analytics module
# --------------------------------------------------------------------------- #
def test_analytics_module_has_no_template_branching():
    import cfdauto.study_analytics
    src = inspect.getsource(cfdauto.study_analytics)
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
            f"study_analytics must not contain: {forbidden}"
