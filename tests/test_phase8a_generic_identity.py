"""Phase 8A — Template Contract + Generic Identity & Validation.

These tests lock in the Phase 8A contract: the generic ``Experiment`` no
longer assumes AOA / velocity / airfoil geometry. Identity (``case_id``),
geometry identity (``geometry_key``), validation policy, serialization, and
``repr`` are all *derived from the template's declarations*, and the generic
core contains no ``if template == ...`` branching.

They cover the spec's test plan (A–K):

    A. External Aero identity compatibility   — case_id byte-identical to legacy
    B. External Aero geometry compatibility   — geometry_key byte-identical
    C. External Aero validation compatibility — valid passes / invalid raises
    D. Internal Flow generic construction     — no fake AOA, valid identity
    E. Internal Flow invalid inputs           — template-declared policy catches
    F. Third-template canary                  — a non-aero template builds
    G. Serialization                          — generic, no aero fields
    H. repr                                   — self-describing, generic
    I. Mesh identity                          — per declared geometry parameters
    J. Bridge removal                         — old airfoil bridge is gone
    K. No generic template branching          — nothing compares template ids
"""

from __future__ import annotations

import inspect
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.models import Experiment                          # noqa: E402
from cfdauto.platform import (                                  # noqa: E402
    EXTERNAL_AERODYNAMICS,
    INTERNAL_FLOW,
    ParameterDefinition,
    ParameterType,
    SimulationTemplate,
    StudyDefinition,
    StudyParameter,
    TemplateRegistry,
    get_default_registry,
)
from cfdauto.simulation_context import SimulationContext        # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers — build experiments through the generic path, template attached.
# --------------------------------------------------------------------------- #
def _aero_exp(row: int, aoa: float, vel: float,
              extra_wb_params=None) -> Experiment:
    return ExperimentDefinition.default().build_experiment(
        row=row, values={"aoa": aoa, "velocity": vel},
        extra_wb_params=extra_wb_params)


def _int_exp(row: int, **values) -> Experiment:
    return ExperimentDefinition.from_context(
        SimulationContext(template=INTERNAL_FLOW)).build_experiment(
        row=row, values=values)


# --------------------------------------------------------------------------- #
# Third-template canary (test-only, NOT a production template). Declares
# neither identity_parameters nor geometry_parameters, so the generic layer's
# *defaults* are exercised: identity = every study input, geometry =
# geometry-category / Workbench-bound parameters. No AOA/velocity/CL/CD.
# --------------------------------------------------------------------------- #
_TANK_RADIUS = ParameterDefinition(
    id="tank-radius", name="tank_radius", display_name="Tank Radius",
    unit="m", type=ParameterType.FLOAT, default_value=0.5,
    minimum=0.05, maximum=5.0, step=0.05, required=True,
    category="geometry", workbench_parameter="P1",
    description="Tank wall radius — the geometric dimension a mesh depends on.")

_INLET_TEMPERATURE = ParameterDefinition(
    id="inlet-temperature", name="inlet_temperature",
    display_name="Inlet Temperature", unit="K", type=ParameterType.FLOAT,
    default_value=300.0, minimum=250.0, maximum=400.0, step=5.0,
    required=True, category="flow", workbench_parameter=None,
    description="Working-fluid inlet temperature.")

_CANARY_STUDY = StudyDefinition(parameters=(
    StudyParameter(parameter=_TANK_RADIUS, column_name="TankRadius_m", order=0,
                   example_values=(0.5, 1.0)),
    StudyParameter(parameter=_INLET_TEMPERATURE, column_name="InletTemp_K",
                   order=1, example_values=(300.0, 350.0)),
))

CANARY_TEMPLATE = SimulationTemplate(
    id="mixing-tank-canary",
    name="Mixing Tank (Phase 8A canary)",
    description=("Test-only third template proving the generic Experiment "
                 "layer derives identity, geometry, and validation from "
                 "template metadata — with no airfoil vocabulary anywhere. "
                 "Not a production template; no strategy is registered."),
    supported_parameters=(_TANK_RADIUS, _INLET_TEMPERATURE),
    supported_metrics=(),
    study_definition=_CANARY_STUDY,
    execution_strategy_id="mixing-tank-canary",
)


# --------------------------------------------------------------------------- #
# A. External Aero identity compatibility — case_id byte-identical to legacy
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("row,aoa,vel", [
    (1, 0.0, 20.0), (5, 8.0, 30.0), (12, 12.0, 20.0), (3, 4.0, 20.0)])
def test_external_aero_case_id_matches_legacy(row, aoa, vel):
    attached = _aero_exp(row, aoa, vel).case_id
    legacy = Experiment(row=row, aoa_deg=aoa, velocity=vel).case_id
    assert attached == legacy
    assert attached == f"r{row:03d}_aoa{aoa:g}_v{vel:g}"


def test_external_aero_case_id_with_wbp_extras_matches_legacy():
    attached = _aero_exp(5, 8.0, 30.0,
                         extra_wb_params={"P1": 12.0, "P2": 6.0}).case_id
    legacy = Experiment(row=5, aoa_deg=8.0, velocity=30.0,
                        extra_wb_params={"P1": 12.0, "P2": 6.0}).case_id
    assert attached == legacy == "r005_aoa8_v30_P112_P26"


# --------------------------------------------------------------------------- #
# B. External Aero geometry compatibility — geometry_key byte-identical
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("row,aoa,vel", [
    (1, 0.0, 20.0), (5, 8.0, 30.0), (12, 12.0, 20.0)])
def test_external_aero_geometry_key_matches_legacy(row, aoa, vel):
    attached = _aero_exp(row, aoa, vel).geometry_key
    legacy = Experiment(row=row, aoa_deg=aoa, velocity=vel).geometry_key
    assert attached == legacy
    assert attached == f"aoa={aoa:.6f}"


def test_external_aero_geometry_key_with_wbp_extras_matches_legacy():
    attached = _aero_exp(5, 8.0, 30.0,
                         extra_wb_params={"P1": 12.0, "P2": 6.0}).geometry_key
    legacy = Experiment(row=5, aoa_deg=8.0, velocity=30.0,
                        extra_wb_params={"P1": 12.0, "P2": 6.0}).geometry_key
    assert attached == legacy == "aoa=8.000000|P1=12.000000|P2=6.000000"


# --------------------------------------------------------------------------- #
# C. External Aero validation compatibility
# --------------------------------------------------------------------------- #
def test_external_aero_valid_rows_pass_under_template_policy():
    _aero_exp(3, 4.0, 20.0).validate()      # must not raise
    _aero_exp(3, -90.0, 0.01).validate()    # inclusive bounds are acceptable
    _aero_exp(3, 90.0, 20.0).validate()


def test_external_aero_invalid_rows_raise_under_template_policy():
    with pytest.raises(ValueError, match="aoa"):
        _aero_exp(3, math.nan, 20.0).validate()      # non-finite
    with pytest.raises(ValueError, match="velocity"):
        _aero_exp(3, 4.0, -5.0).validate()           # below declared minimum
    with pytest.raises(ValueError, match="aoa"):
        _aero_exp(3, 200.0, 20.0).validate()         # above declared maximum


def test_legacy_validate_messages_are_unchanged():
    # The template-less path keeps its byte-identical contract.
    with pytest.raises(ValueError, match="AOA is not a finite number"):
        Experiment(row=1, aoa_deg=math.nan, velocity=20.0).validate()
    with pytest.raises(ValueError, match="velocity must be a positive number"):
        Experiment(row=1, aoa_deg=4.0, velocity=-5.0).validate()


# --------------------------------------------------------------------------- #
# D. Internal Flow generic construction — no fake AOA, valid identity
# --------------------------------------------------------------------------- #
def test_internal_flow_constructs_generically_without_fake_aoa():
    exp = _int_exp(row=2, inlet_velocity=5.0, fluid_density=998.2,
                   fluid_viscosity=0.001002, pipe_diameter=0.1,
                   pipe_length=2.0)
    # Every input under its own parameter name — no airfoil slots.
    assert "aoa" not in exp.parameters
    assert "velocity" not in exp.parameters
    assert exp.parameter("inlet_velocity").value == 5.0
    exp.validate()                              # template policy passes
    # Valid, template-derived identity and geometry.
    assert exp.case_id.startswith("r002_")
    assert "inlet_velocity5" in exp.case_id
    assert exp.geometry_key == "pipe_diameter=0.100000|pipe_length=2.000000"


# --------------------------------------------------------------------------- #
# E. Internal Flow invalid inputs — template-declared policy catches them
# --------------------------------------------------------------------------- #
def test_internal_flow_invalid_inputs_are_rejected_by_template_policy():
    fluid = dict(fluid_density=998.2, fluid_viscosity=0.001002,
                 pipe_length=1.0)
    with pytest.raises(ValueError, match="Pipe Diameter"):
        _int_exp(row=1, inlet_velocity=2.0, pipe_diameter=99.0,
                 **fluid).validate()                              # above max 10
    with pytest.raises(ValueError, match="Inlet Velocity"):
        _int_exp(row=1, inlet_velocity=-5.0, pipe_diameter=0.05,
                 **fluid).validate()                              # below min
    with pytest.raises(ValueError, match="Fluid Density"):
        _int_exp(row=1, inlet_velocity=2.0, fluid_density=0.0,
                 fluid_viscosity=0.001002, pipe_diameter=0.05,
                 pipe_length=1.0).validate()                      # below min


# --------------------------------------------------------------------------- #
# F. Third-template canary — a non-aero template builds via generic metadata
# --------------------------------------------------------------------------- #
def test_canary_registers_without_touching_core_registry():
    reg = TemplateRegistry()
    reg.register(CANARY_TEMPLATE)
    assert reg.get("mixing-tank-canary") is CANARY_TEMPLATE
    # Test-local only — the process-wide built-in registry is untouched.
    assert "mixing-tank-canary" not in get_default_registry()


def test_canary_builds_a_generic_experiment_with_no_aero_fields():
    ed = ExperimentDefinition.from_context(
        SimulationContext(template=CANARY_TEMPLATE))
    exp = ed.build_experiment(
        row=3, values={"tank_radius": 0.5, "inlet_temperature": 300.0})
    assert set(exp.parameters) == {"tank_radius", "inlet_temperature"}
    assert "aoa" not in exp.parameters and "velocity" not in exp.parameters
    exp.validate()                                # template policy passes
    # Defaults: identity = every study input; geometry = geometry/WB params.
    assert exp.case_id == "r003_tank_radius0.5_inlet_temperature300"
    assert exp.geometry_key == "tank_radius=0.500000"


def test_canary_invalid_values_are_rejected():
    ed = ExperimentDefinition.from_context(
        SimulationContext(template=CANARY_TEMPLATE))
    with pytest.raises(ValueError, match="Inlet Temperature"):
        ed.build_experiment(
            row=3, values={"tank_radius": 0.5,
                           "inlet_temperature": 900.0}).validate()


# --------------------------------------------------------------------------- #
# G. Serialization — generic structure, no aero fields required
# --------------------------------------------------------------------------- #
def test_generic_serialization_requires_no_aero_fields():
    exp = _int_exp(row=4, inlet_velocity=2.0, fluid_density=998.2,
                   fluid_viscosity=0.001002, pipe_diameter=0.05,
                   pipe_length=1.0)
    d = exp.to_json_dict()
    assert set(d) == {"row", "status", "template", "parameters", "metadata"}
    assert d["template"] == "internal-flow"
    assert set(d["parameters"]) == {
        "inlet_velocity", "fluid_density", "fluid_viscosity",
        "pipe_diameter", "pipe_length"}
    assert "aoa_deg" not in d and "velocity" not in d


def test_legacy_serialization_is_byte_identical():
    exp = Experiment(row=2, aoa_deg=4.0, velocity=20.0)
    assert exp.to_json_dict() == {
        "row": 2, "aoa_deg": 4.0, "velocity": 20.0,
        "status": "", "extra_wb_params": {}}


# --------------------------------------------------------------------------- #
# H. repr — generic and self-describing (no implied aoa_deg/velocity)
# --------------------------------------------------------------------------- #
def test_repr_is_generic_and_self_describing():
    exp = _int_exp(row=4, inlet_velocity=2.0, fluid_density=998.2,
                   fluid_viscosity=0.001002, pipe_diameter=0.05,
                   pipe_length=1.0)
    r = repr(exp)
    assert r.startswith("Experiment(row=4")
    assert "template='internal-flow'" in r
    assert "parameters={fluid_density=998.2" in r       # sorted parameter set
    assert "inlet_velocity=2" in r and "pipe_diameter=0.05" in r
    # No legacy airfoil *fields* implied — the legacy repr renders the bare
    # fields `, aoa_deg=` / `, velocity=`; the parameter "inlet_velocity=2"
    # is not that field.
    assert "aoa_deg=" not in r and ", velocity=" not in r


def test_external_aero_repr_routes_through_the_template():
    r = repr(_aero_exp(4, 8.0, 30.0))
    assert "template='external-aerodynamics'" in r
    assert "parameters={aoa=8, velocity=30}" in r
    assert "aoa_deg" not in r


# --------------------------------------------------------------------------- #
# I. Mesh identity — geometry_key follows each template's declared geometry
# --------------------------------------------------------------------------- #
def test_internal_flow_mesh_identity_follows_declared_geometry_params():
    base = dict(inlet_velocity=2.0, fluid_density=998.2,
                fluid_viscosity=0.001002)
    geom_a = _int_exp(row=1, **base, pipe_diameter=0.05, pipe_length=1.0)
    geom_b = _int_exp(row=2, **base, pipe_diameter=0.05, pipe_length=1.0)
    assert geom_a.geometry_key == geom_b.geometry_key
    # A different flow condition still reuses the same pipe mesh.
    diff_flow = _int_exp(row=3, inlet_velocity=5.0, fluid_density=998.2,
                         fluid_viscosity=0.001002, pipe_diameter=0.05,
                         pipe_length=1.0)
    assert diff_flow.geometry_key == geom_a.geometry_key
    # A different pipe diameter is a different geometry.
    diff_geom = _int_exp(row=4, **base, pipe_diameter=0.1, pipe_length=1.0)
    assert diff_geom.geometry_key != geom_a.geometry_key


def test_external_aero_mesh_identity_is_preserved():
    a = _aero_exp(1, 4.0, 20.0)
    b = _aero_exp(2, 4.0, 30.0)     # same AOA, different velocity → same mesh
    c = _aero_exp(3, 8.0, 20.0)     # different AOA → different mesh
    assert a.geometry_key == b.geometry_key
    assert a.geometry_key != c.geometry_key
    assert a.geometry_key == "aoa=4.000000"


# --------------------------------------------------------------------------- #
# J. Bridge removal — the old airfoil-shaped internal-flow bridge is gone
# --------------------------------------------------------------------------- #
def test_bridge_is_no_longer_importable():
    with pytest.raises(ImportError):
        from cfdauto.execution import build_internal_flow_experiment  # noqa: F401


def test_generic_constructor_requires_no_aero_keywords():
    # Experiment.__init__ never requires aoa_deg/velocity — the template is
    # the identity source.
    exp = Experiment(row=7, status="PENDING", template=INTERNAL_FLOW)
    assert exp.parameters == {}
    assert exp.template is INTERNAL_FLOW


# --------------------------------------------------------------------------- #
# K. No generic template branching — the generic core compares no template ids
# --------------------------------------------------------------------------- #
def test_generic_core_has_no_template_branching():
    import cfdauto.experiment_definition
    import cfdauto.models
    import cfdauto.simulation_context
    src = ("\n".join([
        inspect.getsource(cfdauto.models),
        inspect.getsource(cfdauto.experiment_definition),
        inspect.getsource(cfdauto.simulation_context),
    ]))
    for forbidden in (
            'if template == "external-aerodynamics"',
            'if template == "internal-flow"',
            'template.id == "external-aerodynamics"',
            'template.id == "internal-flow"',
            'self.template == "external-aerodynamics"',
            'self.template == "internal-flow"'):
        assert forbidden not in src, f"generic core must not contain: {forbidden}"
