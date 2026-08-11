"""Internal Flow reference template (Universal Platform, Phase 6).

A second, fundamentally different CFD workflow — pipe / duct internal flow —
defined **entirely** with the existing platform models. Its presence is the
architecture's proof: adding a new domain required no change to
``ParameterDefinition``, ``MetricDefinition``, ``StudyDefinition``,
``SimulationTemplate``, ``ExperimentDefinition``, ``StudyIO``,
``SimulationContext``, or the ``Experiment``/``CaseResult`` runtime model —
only this data file plus a one-line registry registration.

Study: sweep inlet velocity and pipe diameter of a fluid flowing through a
pipe; the outputs of interest are the pressure drop, the Reynolds number,
and the Darcy friction factor. Defaults are for water at ~20 °C. **No solver
is implemented for this template in Phase 6** — the sprint validates the
metadata/IO path, not a new Fluent setup.
"""

from __future__ import annotations

from typing import Tuple

from .metrics import SOURCE_DERIVED, SOURCE_SOLVER_REPORT, MetricDefinition
from .parameters import ParameterDefinition, ParameterType
from .study_definition import StudyDefinition, StudyParameter
from .templates import SimulationTemplate

# --------------------------------------------------------------------------- #
# Parameters — shared instances used by both supported_parameters and the
# study definition (single source of truth, like External Aerodynamics).
# --------------------------------------------------------------------------- #
_INLET_VELOCITY = ParameterDefinition(
    id="inlet-velocity", name="inlet_velocity", display_name="Inlet Velocity",
    unit="m/s", type=ParameterType.FLOAT, default_value=2.0,
    minimum=0.001, maximum=100.0, step=0.5, required=True,
    category="flow", workbench_parameter=None,
    description="Mean fluid velocity at the pipe inlet, applied at the "
                "Fluent velocity inlet.")

_FLUID_DENSITY = ParameterDefinition(
    id="fluid-density", name="fluid_density", display_name="Fluid Density",
    unit="kg/m3", type=ParameterType.FLOAT, default_value=998.2,
    minimum=0.1, maximum=20000.0, step=1.0, required=True,
    category="fluid", workbench_parameter=None,
    description="Working-fluid density (default: water at ~20 C).")

_FLUID_VISCOSITY = ParameterDefinition(
    id="fluid-viscosity", name="fluid_viscosity", display_name="Fluid Viscosity",
    unit="Pa.s", type=ParameterType.FLOAT, default_value=1.002e-3,
    minimum=1.0e-6, maximum=10.0, step=1.0e-4, required=True,
    category="fluid", workbench_parameter=None,
    description="Dynamic viscosity of the working fluid (default: water at "
                "~20 C).")

_PIPE_DIAMETER = ParameterDefinition(
    id="pipe-diameter", name="pipe_diameter", display_name="Pipe Diameter",
    unit="m", type=ParameterType.FLOAT, default_value=0.05,
    minimum=0.001, maximum=10.0, step=0.01, required=True,
    category="geometry", workbench_parameter="P1",
    description="Internal pipe diameter, driven via a Workbench geometry "
                "parameter.")

_PIPE_LENGTH = ParameterDefinition(
    id="pipe-length", name="pipe_length", display_name="Pipe Length",
    unit="m", type=ParameterType.FLOAT, default_value=1.0,
    minimum=0.01, maximum=1000.0, step=0.1, required=True,
    category="geometry", workbench_parameter="P2",
    description="Straight pipe length over which the pressure drop is "
                "measured, driven via a Workbench geometry parameter.")

# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
_INTERNAL_FLOW_METRICS: Tuple[MetricDefinition, ...] = (
    MetricDefinition(
        id="pressure-drop", name="pressure_drop", display_name="Pressure Drop",
        unit="Pa", source=SOURCE_SOLVER_REPORT,
        description="Static pressure drop between the pipe inlet and outlet."),
    MetricDefinition(
        id="reynolds-number", name="reynolds_number",
        display_name="Reynolds Number", unit="", source=SOURCE_DERIVED,
        description="Re = rho * V * D / mu — dimensionless flow regime "
                    "indicator (laminar < ~2300, turbulent > ~4000)."),
    MetricDefinition(
        id="friction-factor", name="friction_factor",
        display_name="Friction Factor", unit="", source=SOURCE_DERIVED,
        description="Darcy friction factor, from the pressure drop or "
                    "correlated against the Reynolds number (Moody chart)."),
)

# --------------------------------------------------------------------------- #
# Study definition — sweep inlet velocity x pipe diameter, fluid properties
# and pipe length fixed at their defaults (8 example rows).
# --------------------------------------------------------------------------- #
_INTERNAL_FLOW_STUDY = StudyDefinition(parameters=(
    StudyParameter(parameter=_INLET_VELOCITY, column_name="InletVelocity_m_s",
                   order=0, example_values=(1.0, 2.0, 5.0, 10.0)),
    StudyParameter(parameter=_FLUID_DENSITY, column_name="FluidDensity_kg_m3",
                   order=1),                          # fixed at default
    StudyParameter(parameter=_FLUID_VISCOSITY, column_name="FluidViscosity_Pa_s",
                   order=2),                          # fixed at default
    StudyParameter(parameter=_PIPE_DIAMETER, column_name="PipeDiameter_m",
                   order=3, example_values=(0.05, 0.1)),
    StudyParameter(parameter=_PIPE_LENGTH, column_name="PipeLength_m",
                   order=4),                          # fixed at default
))

INTERNAL_FLOW = SimulationTemplate(
    id="internal-flow",
    name="Internal Flow",
    description=(
        "Parametric internal-flow study of fluid through a pipe: sweep inlet "
        "velocity and pipe diameter, extract pressure drop, Reynolds number, "
        "and friction factor. A second reference template proving the "
        "platform is domain-agnostic."),
    supported_parameters=(_INLET_VELOCITY, _FLUID_DENSITY, _FLUID_VISCOSITY,
                          _PIPE_DIAMETER, _PIPE_LENGTH),
    supported_metrics=_INTERNAL_FLOW_METRICS,
    study_definition=_INTERNAL_FLOW_STUDY,
    # Phase 8A identity contract: identity defaults to every study input
    # (all five — two cases differing in any physical input are distinct
    # cases); geometry is the pipe dimensions, which is what a mesh depends
    # on — the velocity/fluid sweeps reuse one pipe mesh.
    geometry_parameters=("pipe_diameter", "pipe_length"),
    default_solver="ansys-fluent",
    default_boundary_conditions={
        "inlet_type": "velocity_inlet",
        "outlet_type": "pressure_outlet",
    },
    report_type="study-summary",
    validation_profile="moody-chart",
    execution_strategy_id="internal-flow",
)
