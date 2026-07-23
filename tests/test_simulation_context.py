"""Universal CFD Platform, Phase 2 — unit tests for SimulationContext.

SimulationContext is the runtime's single source of truth for study
metadata. These tests verify it resolves the External Aerodynamics
template through the registry (not a hardcoded literal), exposes the
template's parameters/metrics, and keeps the one-way dependency on the
platform layer. They do NOT assert any runtime wiring beyond the context
object itself — the byte-identical GUI behavior is covered by the existing
(unmodified) GUI smoke tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.platform import get_default_template          # noqa: E402
from cfdauto.simulation_context import SimulationContext    # noqa: E402


def test_default_context_uses_external_aerodynamics_via_registry():
    ctx = SimulationContext.default()
    # The template is the registry's default — not constructed ad hoc.
    assert ctx.template is get_default_template()
    assert ctx.template.id == "external-aerodynamics"
    assert ctx.project is None


def test_context_carries_optional_project_identity():
    ctx = SimulationContext.default(project="wing_v2")
    assert ctx.project == "wing_v2"
    assert ctx.template.id == "external-aerodynamics"


def test_context_exposes_parameter_definitions():
    ctx = SimulationContext.default()
    names = {p.name for p in ctx.parameter_definitions}
    assert names == {"aoa", "velocity"}
    aoa = ctx.parameter("aoa")
    # The exact metadata the GUI now reads instead of hardcoding.
    assert aoa.display_name == "AOA"
    assert aoa.unit == "deg"
    assert (aoa.minimum, aoa.maximum) == (-90.0, 90.0)
    assert aoa.default_value == 0.0
    vel = ctx.parameter("velocity")
    assert vel.display_name == "Velocity"
    assert vel.unit == "m/s"
    assert vel.minimum == 0.01
    assert vel.maximum is None            # unbounded in the domain model
    assert vel.default_value == 20.0


def test_context_exposes_metric_definitions():
    ctx = SimulationContext.default()
    names = {m.name for m in ctx.metric_definitions}
    assert names == {"cl", "cd", "l_over_d", "lift", "drag"}
    # The exact legend labels the Monitor now reads instead of hardcoding.
    assert ctx.metric("cl").display_name == "CL"
    assert ctx.metric("cd").display_name == "CD"
    assert ctx.metric("lift").unit == "N"


def test_context_lookup_returns_none_for_unknown():
    ctx = SimulationContext.default()
    assert ctx.parameter("mach") is None
    assert ctx.metric("torque") is None


def test_context_is_immutable():
    import pytest
    ctx = SimulationContext.default()
    with pytest.raises(Exception):
        ctx.project = "changed"           # frozen dataclass


def test_display_names_match_todays_gui_labels_exactly():
    """The reconciliation this phase depends on: reading display_name +
    unit must reproduce the labels the GUI showed in v1.0, byte for byte."""
    ctx = SimulationContext.default()
    assert (f"{ctx.parameter('aoa').display_name} "
            f"[{ctx.parameter('aoa').unit}]") == "AOA [deg]"
    assert (f"{ctx.parameter('velocity').display_name} "
            f"[{ctx.parameter('velocity').unit}]") == "Velocity [m/s]"
