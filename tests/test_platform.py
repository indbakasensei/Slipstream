"""Universal CFD Platform foundation (v2.0.0-dev, Phase 1) — unit tests.

These cover the four new pure-metadata models in cfdauto/platform/:
ParameterDefinition, MetricDefinition, SimulationTemplate, and the
TemplateRegistry. They deliberately assert *generality* (the models carry
no airfoil-specific structure) and that the single Phase 1 template
faithfully describes today's workflow — while NOT asserting anything about
runtime wiring, because Phase 1 explicitly does not migrate runtime
behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.platform import (                              # noqa: E402
    DEFAULT_TEMPLATE_ID,
    EXTERNAL_AERODYNAMICS,
    MetricDefinition,
    ParameterDefinition,
    ParameterType,
    SimulationTemplate,
    TemplateRegistry,
    get_default_registry,
    get_default_template,
)


# --------------------------------------------------------------------- #
# Group: ParameterDefinition — generic input variable
# --------------------------------------------------------------------- #
def test_parameter_definition_holds_generic_metadata():
    rpm = ParameterDefinition(
        id="rotor-speed", name="rpm", display_name="Rotor Speed",
        unit="rpm", type=ParameterType.FLOAT, default_value=1000.0,
        minimum=0.0, maximum=20000.0, step=100.0, category="rotation")
    # Nothing airfoil-specific: a rotational parameter is expressed with
    # the exact same model as AOA — that's the whole point of Phase 1.
    assert rpm.name == "rpm"
    assert rpm.unit == "rpm"
    assert rpm.workbench_parameter is None
    assert rpm.type is ParameterType.FLOAT


def test_parameter_validate_value_collects_all_problems_without_raising():
    p = ParameterDefinition(
        id="p", name="p", display_name="P", type=ParameterType.FLOAT,
        minimum=0.0, maximum=10.0, required=True)
    assert p.validate_value(5.0) == []                 # in range
    assert p.validate_value(10.0) == []                # inclusive max
    assert p.validate_value(0.0) == []                 # inclusive min
    assert len(p.validate_value(-1.0)) == 1            # below min
    assert len(p.validate_value(11.0)) == 1            # above max
    assert len(p.validate_value("abc")) == 1           # not a number
    assert len(p.validate_value(None)) == 1            # required, missing


def test_parameter_optional_value_may_be_absent():
    p = ParameterDefinition(id="p", name="p", display_name="P",
                           required=False, minimum=0.0)
    assert p.validate_value(None) == []                # not required → ok


def test_integer_parameter_rejects_fractional_values():
    p = ParameterDefinition(id="n", name="n", display_name="N",
                           type=ParameterType.INTEGER)
    assert p.validate_value(3) == []
    assert len(p.validate_value(3.5)) == 1


def test_parameter_definition_is_immutable():
    p = ParameterDefinition(id="p", name="p", display_name="P")
    with pytest.raises(Exception):
        p.name = "changed"          # frozen dataclass


# --------------------------------------------------------------------- #
# Group: MetricDefinition — generic output quantity
# --------------------------------------------------------------------- #
def test_metric_definition_holds_generic_metadata():
    torque = MetricDefinition(
        id="shaft-torque", name="torque", display_name="Shaft Torque",
        unit="N·m", description="Torque on the rotating shaft.")
    # A turbomachinery metric uses the same model as a lift coefficient.
    assert torque.name == "torque"
    assert torque.unit == "N·m"


def test_metric_definition_is_immutable():
    m = MetricDefinition(id="m", name="m", display_name="M")
    with pytest.raises(Exception):
        m.unit = "changed"


# --------------------------------------------------------------------- #
# Group: SimulationTemplate — the External Aerodynamics Phase 1 template
# --------------------------------------------------------------------- #
def test_external_aerodynamics_describes_todays_workflow():
    t = EXTERNAL_AERODYNAMICS
    assert t.id == "external-aerodynamics"
    # Its parameters ARE the schedule's AOA/Velocity inputs.
    assert {p.name for p in t.supported_parameters} == {"aoa", "velocity"}
    # Its metrics ARE the outputs every GUI panel already shows.
    assert {m.name for m in t.supported_metrics} == {
        "cl", "cd", "l_over_d", "lift", "drag"}
    assert t.default_solver == "ansys-fluent"


def test_template_metadata_mirrors_existing_config_defaults():
    t = EXTERNAL_AERODYNAMICS
    # AOA is the Workbench-driven parameter (config default aoa_parameter="P1");
    # velocity is applied at the inlet, not via Workbench.
    assert t.parameter("aoa").workbench_parameter == "P1"
    assert t.parameter("velocity").workbench_parameter is None
    assert t.default_boundary_conditions["inlet_type"] == "velocity_inlet"
    assert t.default_boundary_conditions["aoa_method"] == "geometry"


def test_template_lookup_by_name_or_id():
    t = EXTERNAL_AERODYNAMICS
    assert t.parameter("aoa") is t.parameter("angle-of-attack")
    assert t.metric("cl") is t.metric("lift-coefficient")
    assert t.parameter("nonexistent") is None
    assert t.metric("nonexistent") is None


# --------------------------------------------------------------------- #
# Group: TemplateRegistry
# --------------------------------------------------------------------- #
def test_default_registry_contains_only_external_aerodynamics():
    reg = get_default_registry()
    assert reg.ids() == ["external-aerodynamics"]
    assert "external-aerodynamics" in reg
    assert len(reg) == 1


def test_get_default_template_returns_external_aerodynamics():
    t = get_default_template()
    assert t.id == DEFAULT_TEMPLATE_ID == "external-aerodynamics"
    assert t is EXTERNAL_AERODYNAMICS


def test_registry_get_unknown_raises_with_actionable_message():
    reg = get_default_registry()
    with pytest.raises(LookupError, match="external-aerodynamics"):
        reg.get("heat-transfer")     # names what IS available


def test_registry_supports_future_templates_without_modification():
    """The seam future phases build on: registering a brand-new template
    (here a fabricated one, not shipped) just works — nothing about the
    registry needs to change to add heat transfer, turbomachinery, etc."""
    reg = TemplateRegistry()
    reg.register(EXTERNAL_AERODYNAMICS)
    future = SimulationTemplate(
        id="internal-flow", name="Internal Flow",
        supported_parameters=(ParameterDefinition(
            id="mass-flow-rate", name="mdot", display_name="Mass Flow Rate",
            unit="kg/s"),),
        supported_metrics=(MetricDefinition(
            id="pressure-drop", name="dp", display_name="Pressure Drop",
            unit="Pa"),))
    reg.register(future)
    assert reg.ids() == ["external-aerodynamics", "internal-flow"]
    assert reg.get("internal-flow").parameter("mdot").unit == "kg/s"


def test_registry_rejects_duplicate_id():
    reg = TemplateRegistry()
    reg.register(EXTERNAL_AERODYNAMICS)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(EXTERNAL_AERODYNAMICS)


def test_platform_package_has_no_gui_or_solver_imports():
    """Phase 1 invariant: the platform package is pure data models — it
    must not drag in Qt, the solver controllers, or anything runtime."""
    import cfdauto.platform as platform_pkg
    import cfdauto.platform.metrics as metrics_mod
    import cfdauto.platform.parameters as params_mod
    import cfdauto.platform.registry as registry_mod
    import cfdauto.platform.templates as templates_mod
    for mod in (platform_pkg, metrics_mod, params_mod, registry_mod,
               templates_mod):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert "PySide6" not in src, f"{mod.__name__} imports Qt"
        assert "fluent_controller" not in src
        assert "workbench_controller" not in src
