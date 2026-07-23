"""Simulation templates (Universal Platform, Phase 1).

A :class:`SimulationTemplate` bundles everything that defines one *kind*
of CFD study — its input parameters, its output metrics, and its solver/
reporting defaults — as pure metadata. Slipstream's long-term direction
(see ``docs/PLATFORM_ARCHITECTURE.md``) is that the core engine knows
nothing about airfoils: the current AOA/velocity wing workflow becomes
just one template among many.

Phase 1 ships exactly one template, :data:`EXTERNAL_AERODYNAMICS`, whose
contents *describe* — not drive — the existing application: its two
parameters are the schedule's AOA/Velocity columns, its metrics are the
CL/CD/L-D/Lift/Drag outputs every panel already shows, and its defaults
mirror ``config.py``'s. No runtime code consumes this yet; it exists so
future phases can migrate the engine onto the abstraction incrementally
while this metadata is already proven to round-trip through the registry
and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .metrics import SOURCE_DERIVED, MetricDefinition
from .parameters import ParameterDefinition, ParameterType


@dataclass(frozen=True)
class SimulationTemplate:
    """Metadata describing one kind of CFD study.

    Attributes
    ----------
    id:
        Stable machine identifier, kebab-case (``"external-aerodynamics"``).
    name:
        Human-facing template name.
    description:
        What studies of this kind are for.
    supported_parameters / supported_metrics:
        The template's input/output vocabulary, in display order.
    default_solver:
        Identifier of the solver backend this template targets
        (``"ansys-fluent"`` today; a future OpenFOAM backend would be a
        different string, not a different model).
    default_boundary_conditions:
        Template-level BC defaults (treat as read-only). Keys mirror the
        existing ``fluent:`` config vocabulary so migration is a rename,
        not a translation.
    report_type:
        Which report/summary family results feed into.
    validation_profile:
        Which validation methodology applies (``docs/validation/``).
    """

    id: str
    name: str
    description: str = ""
    supported_parameters: Tuple[ParameterDefinition, ...] = ()
    supported_metrics: Tuple[MetricDefinition, ...] = ()
    default_solver: str = "ansys-fluent"
    default_boundary_conditions: Dict[str, str] = field(default_factory=dict)
    report_type: str = "study-summary"
    validation_profile: str = ""

    # ------------------------------------------------------------------ #
    def parameter(self, name_or_id: str) -> Optional[ParameterDefinition]:
        """Look up a parameter by ``name`` or ``id``; None if absent."""
        for p in self.supported_parameters:
            if name_or_id in (p.name, p.id):
                return p
        return None

    def metric(self, name_or_id: str) -> Optional[MetricDefinition]:
        """Look up a metric by ``name`` or ``id``; None if absent."""
        for m in self.supported_metrics:
            if name_or_id in (m.name, m.id):
                return m
        return None


# --------------------------------------------------------------------------- #
# The one Phase 1 template: a faithful description of today's application.
# Values below mirror the existing defaults in cfdauto/config.py
# (aoa_parameter="P1", inlet_type="velocity_inlet", aoa range per the
# ParamsPanel/linter conventions) — descriptive, never authoritative yet.
# --------------------------------------------------------------------------- #
EXTERNAL_AERODYNAMICS = SimulationTemplate(
    id="external-aerodynamics",
    name="External Aerodynamics",
    description=(
        "Parametric external-flow study of a lifting body: sweep angle of "
        "attack and freestream velocity, extract force coefficients. This "
        "template describes Slipstream's original wing/airfoil workflow."),
    supported_parameters=(
        # display_name holds the *short label the UI shows* (Phase 2
        # reconciliation — the runtime GUI reads these verbatim); the
        # verbose human explanation lives in `description`.
        ParameterDefinition(
            id="angle-of-attack", name="aoa", display_name="AOA",
            unit="deg", type=ParameterType.FLOAT, default_value=0.0,
            minimum=-90.0, maximum=90.0, step=1.0, required=True,
            category="flow", workbench_parameter="P1",
            description="Angle of attack: incidence angle of the body "
                        "relative to the freestream, driven via the "
                        "Workbench geometry rotation parameter."),
        ParameterDefinition(
            id="freestream-velocity", name="velocity",
            display_name="Velocity", unit="m/s",
            type=ParameterType.FLOAT, default_value=20.0,
            minimum=0.01, maximum=None, step=5.0, required=True,
            category="flow", workbench_parameter=None,
            description="Freestream velocity magnitude, applied at the "
                        "Fluent velocity inlet (not a Workbench parameter)."),
    ),
    supported_metrics=(
        MetricDefinition(
            id="lift-coefficient", name="cl", display_name="CL",
            description="Lift coefficient from the solver's lift report "
                        "definition, normalized by the configured "
                        "reference values."),
        MetricDefinition(
            id="drag-coefficient", name="cd", display_name="CD",
            description="Drag coefficient from the solver's drag report "
                        "definition."),
        MetricDefinition(
            id="lift-to-drag-ratio", name="l_over_d", display_name="L/D",
            source=SOURCE_DERIVED,
            description="Aerodynamic efficiency, CL divided by CD."),
        MetricDefinition(
            id="lift-force", name="lift", display_name="Lift", unit="N",
            description="Wind-axis lift force on the configured wall zones."),
        MetricDefinition(
            id="drag-force", name="drag", display_name="Drag", unit="N",
            description="Wind-axis drag force on the configured wall zones."),
    ),
    default_solver="ansys-fluent",
    default_boundary_conditions={
        "inlet_type": "velocity_inlet",
        "aoa_method": "geometry",
    },
    report_type="study-summary",
    validation_profile="benchmark-comparison",
)
