"""Capability 2 — Dynamic Template UI.

The desktop UI is now a *renderer of platform metadata*: parameter forms,
queue columns, validation, units, tooltips, and defaults are all generated
from a template's StudyDefinition / ParameterDefinition, with no hardcoded
parameter names. These tests prove the same UI code renders External
Aerodynamics (AOA, Velocity) and Internal Flow (inlet velocity, pipe
diameter, …) correctly, purely by swapping the active template — the
engineering rule "new template = 1 metadata file + 1 strategy + 0 UI code".
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd                                        # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402

from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.platform import (EXTERNAL_AERODYNAMICS,       # noqa: E402
                              INTERNAL_FLOW)
from cfdauto.simulation_context import SimulationContext   # noqa: E402
from gui import param_render                               # noqa: E402
from gui.state import OUTPUT_COLS, AppState                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _state_for(template) -> AppState:
    """An AppState whose active template is `template` (no workbook needed —
    the panels render from metadata alone)."""
    st = AppState()
    st.context = SimulationContext(template=template)
    st.experiment_definition = ExperimentDefinition.from_context(st.context)
    return st


# --------------------------------------------------------------------- #
# param_render — the metadata → widget pipeline (pure, no window)
# --------------------------------------------------------------------- #
def test_label_includes_unit_from_metadata():
    aoa = EXTERNAL_AERODYNAMICS.parameter("aoa")
    assert param_render.label_for(aoa) == "AOA [deg]"
    dia = INTERNAL_FLOW.parameter("pipe_diameter")
    assert param_render.label_for(dia) == "Pipe Diameter [m]"


def test_tooltip_carries_description_unit_default_range():
    aoa = EXTERNAL_AERODYNAMICS.parameter("aoa")
    tip = param_render.tooltip_for(aoa)
    assert "Angle of attack" in tip
    assert "Unit: deg" in tip
    assert "Default: 0" in tip
    assert "Range: -90 to 90 deg" in tip


def test_range_text_handles_unbounded_side():
    vel = EXTERNAL_AERODYNAMICS.parameter("velocity")   # maximum is None
    assert param_render.range_text(vel) == "Range: ≥ 0.01 m/s"


def test_decimals_floor_two_but_expand_for_tiny_values():
    # AOA/Velocity keep the established 2-dp look …
    assert param_render.decimals_for(EXTERNAL_AERODYNAMICS.parameter("aoa")) == 2
    assert param_render.decimals_for(EXTERNAL_AERODYNAMICS.parameter("velocity")) == 2
    # … while a tiny viscosity gets the precision it needs.
    visc = INTERNAL_FLOW.parameter("fluid_viscosity")
    assert param_render.decimals_for(visc) == 6


def test_make_spin_uses_metadata_range_and_default(qapp):
    dia = INTERNAL_FLOW.parameter("pipe_diameter")
    spin = param_render.make_spin(dia)
    assert spin.minimum() == pytest.approx(0.001)
    assert spin.maximum() == pytest.approx(10.0)
    assert spin.value() == pytest.approx(0.05)          # template default
    # An unbounded-above parameter gets the finite editing cap, not a crash.
    vel = param_render.make_spin(EXTERNAL_AERODYNAMICS.parameter("velocity"))
    assert vel.maximum() == pytest.approx(param_render.GUI_MAX_UNBOUNDED)


# --------------------------------------------------------------------- #
# Validation — reuse the ParameterDefinition limits, no UI copy
# --------------------------------------------------------------------- #
def test_validation_reuses_metadata_limits():
    ed = ExperimentDefinition.from_context(
        SimulationContext(template=EXTERNAL_AERODYNAMICS))
    assert param_render.validate_row(ed, {"aoa": 4.0, "velocity": 20.0}) == []
    problems = param_render.validate_row(ed, {"aoa": 200.0, "velocity": 20.0})
    assert any("above the maximum of 90" in p for p in problems)


# --------------------------------------------------------------------- #
# Form generation — one editor per study parameter, from metadata
# --------------------------------------------------------------------- #
def test_params_form_generated_for_external_aero(qapp):
    from gui.panels.params_panel import ParamsPanel
    panel = ParamsPanel(_state_for(EXTERNAL_AERODYNAMICS))
    assert [sp.name for sp, _ in panel._sel_rows] == ["aoa", "velocity"]
    # Defaults on the "add" form come straight from the template (objective 6).
    add_defaults = {sp.name: spin.value() for sp, spin in panel._add_rows}
    assert add_defaults == pytest.approx({"aoa": 0.0, "velocity": 20.0})
    # No airfoil-specific attributes remain on the panel.
    assert not hasattr(panel, "aoa") and not hasattr(panel, "vel")


def test_params_form_generated_for_internal_flow(qapp):
    from gui.panels.params_panel import ParamsPanel
    panel = ParamsPanel(_state_for(INTERNAL_FLOW))
    assert [sp.name for sp, _ in panel._sel_rows] == [
        "inlet_velocity", "fluid_density", "fluid_viscosity",
        "pipe_diameter", "pipe_length"]
    add_defaults = {sp.name: spin.value() for sp, spin in panel._add_rows}
    assert add_defaults["pipe_diameter"] == pytest.approx(0.05)
    assert add_defaults["inlet_velocity"] == pytest.approx(2.0)
    # A geometry parameter's spin honours its metadata bounds.
    dia_spin = dict((sp.name, spin) for sp, spin in panel._add_rows)["pipe_diameter"]
    assert dia_spin.maximum() == pytest.approx(10.0)


# --------------------------------------------------------------------- #
# Queue columns — generated from metadata, ordered, unit-tooltip'd
# --------------------------------------------------------------------- #
def test_queue_columns_from_metadata_external_aero(qapp):
    from gui.panels.queue_panel import QueuePanel
    panel = QueuePanel(_state_for(EXTERNAL_AERODYNAMICS))
    cols = panel.columns()
    assert cols[:3] == ["Row", "AOA", "Velocity"]
    assert cols[3:] == ["Status", "CL", "CD", "L/D", "It", "Conv"]


def test_queue_columns_and_render_for_internal_flow(qapp):
    from gui.panels.queue_panel import QueuePanel
    state = _state_for(INTERNAL_FLOW)
    panel = QueuePanel(state)
    cols = panel.columns()
    assert cols[1:6] == ["Inlet Velocity", "Fluid Density", "Fluid Viscosity",
                         "Pipe Diameter", "Pipe Length"]

    # A dataset with the internal-flow input columns renders with no KeyError
    # and no AOA assumption.
    row = {"Row": 2, "Inlet Velocity": 2.0, "Fluid Density": 998.2,
           "Fluid Viscosity": 1.002e-3, "Pipe Diameter": 0.05,
           "Pipe Length": 1.0, "Status": "PENDING", "Iterations": None,
           "Converged": "", "CL": None, "CD": None, "L/D": None}
    for c in OUTPUT_COLS:
        row.setdefault(c, None)
    state.df = pd.DataFrame([row])
    panel.refresh()
    assert panel.table.rowCount() == 1
    header = [panel.table.horizontalHeaderItem(i).text()
              for i in range(panel.table.columnCount())]
    assert "Pipe Diameter" in header
    # The metadata unit is surfaced on the column header tooltip.
    dia_col = header.index("Pipe Diameter")
    assert "Unit: m" in panel.table.horizontalHeaderItem(dia_col).toolTip()


# --------------------------------------------------------------------- #
# Charts — the parameter selectors are metadata-driven (objective 7)
# --------------------------------------------------------------------- #
def test_chart_axes_populated_from_metadata_internal_flow(qapp):
    from gui.panels.charts_panel import ChartsPanel
    state = _state_for(INTERNAL_FLOW)
    state.df = pd.DataFrame(columns=["Status"])      # real dataset always has one
    panel = ChartsPanel(state)
    panel._rebuild_axes()
    xs = [panel.x_box.itemText(i) for i in range(panel.x_box.count())]
    assert xs[:2] == ["Inlet Velocity", "Fluid Density"]
    assert "AOA" not in xs


def test_state_primary_secondary_inputs_are_metadata():
    ext = _state_for(EXTERNAL_AERODYNAMICS)
    assert ext.primary_input().display_name == "AOA"
    assert ext.secondary_input().display_name == "Velocity"
    intf = _state_for(INTERNAL_FLOW)
    assert intf.primary_input().name == "inlet_velocity"
