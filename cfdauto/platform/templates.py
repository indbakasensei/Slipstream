"""Simulation templates (Universal Platform, Phases 1–3A).

A :class:`SimulationTemplate` bundles everything that defines one *kind*
of CFD study — its input parameters, its output metrics, its ordered
:class:`~cfdauto.platform.study_definition.StudyDefinition`, and its
solver/reporting defaults — as pure metadata. Slipstream's long-term
direction (see ``docs/PLATFORM_ARCHITECTURE.md``) is that the core engine
knows nothing about airfoils: the current AOA/velocity wing workflow
becomes just one template among many.

The single template, :data:`EXTERNAL_AERODYNAMICS`, *describes* the
existing application. Phase 3A adds its :class:`StudyDefinition`, which
declares the input ordering and spreadsheet-column mapping (AOA →
``AOA_deg``, Velocity → ``Velocity_m_s``) that the runtime previously
hardcoded. The parameter/metric objects are defined once as module
constants and shared between ``supported_parameters`` and the study
definition, so there is a single source of truth for each.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .metrics import SOURCE_DERIVED, MetricDefinition
from .parameters import ParameterDefinition, ParameterType
from .study_definition import StudyDefinition, StudyParameter


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
    study_definition:
        The ordered, spreadsheet-aware input specification
        (:class:`StudyDefinition`). ``None`` means "not declared"; callers
        should fall back to ``supported_parameters`` order in that case.
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
    execution_strategy_id:
        Phase 7 — the id of the ``ExecutionStrategy`` that runs this
        template's studies (resolved by the runtime's execution registry).
        A plain string so the platform layer stays free of any runtime/
        execution import; the template *owns* its execution by naming it.
    identity_parameters:
        Phase 8A — which input parameters compose a case's *identity*
        (``case_id``), as ordered ``(parameter_name, label)`` pairs. The
        label is the compact token rendered next to the value (External
        Aerodynamics renders ``aoa8`` / ``v30``). Empty means "default":
        every input parameter of the study definition, in study order,
        labelled by its own name. Any non-identity parameters the runtime
        marks as workbench extras are appended, sorted.
    geometry_parameters:
        Phase 8A — which input parameters determine a case's *geometry/
        mesh* identity (``geometry_key``), in order. Empty means "default":
        every parameter whose ``category`` is ``"geometry"`` or that maps a
        ``workbench_parameter`` (in template order) — the parameters that
        actually shape a mesh. Workbench extras not declared are appended,
        sorted.
    """

    id: str
    name: str
    description: str = ""
    supported_parameters: Tuple[ParameterDefinition, ...] = ()
    supported_metrics: Tuple[MetricDefinition, ...] = ()
    study_definition: Optional[StudyDefinition] = None
    default_solver: str = "ansys-fluent"
    default_boundary_conditions: Dict[str, str] = field(default_factory=dict)
    report_type: str = "study-summary"
    validation_profile: str = ""
    execution_strategy_id: str = ""
    identity_parameters: Tuple[Tuple[str, str], ...] = ()
    geometry_parameters: Tuple[str, ...] = ()

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

    # ------------------------------------------------------------------ #
    # Phase 8A contract: identity / geometry / validation semantics. The
    # generic core never hardcodes a domain rule — it asks the template.
    # ------------------------------------------------------------------ #
    def identity_parameter_names(self) -> Tuple[str, ...]:
        """Ordered names of the parameters that compose a case's identity.

        The declared ``identity_parameters`` when present; otherwise every
        input parameter of the study definition (in study order), so a
        template that declares nothing still gets a stable, unique identity
        from its own inputs.
        """
        if self.identity_parameters:
            return tuple(name for name, _ in self.identity_parameters)
        if self.study_definition is not None:
            return tuple(p.name for p in self.study_definition.ordered())
        return tuple(p.name for p in self.supported_parameters)

    def identity_label(self, name: str) -> str:
        """The compact label ``name`` renders under in a case id (its own
        name when the template declares no override)."""
        for n, label in self.identity_parameters:
            if n == name:
                return label
        return name

    def geometry_parameter_names(self) -> Tuple[str, ...]:
        """Ordered names of the parameters that determine geometry/mesh
        identity.

        The declared ``geometry_parameters`` when present; otherwise every
        parameter that shapes a mesh — ``category == "geometry"`` or a
        mapped ``workbench_parameter`` — in template order.
        """
        if self.geometry_parameters:
            return tuple(self.geometry_parameters)
        return tuple(p.name for p in self.supported_parameters
                     if p.category == "geometry" or p.workbench_parameter)

    def experiment_validation_problems(self, exp: Any) -> List[str]:
        """Every experiment-level validation problem for ``exp`` under this
        template's declared validation policy.

        The policy *is* the template's parameters: each present parameter is
        validated against its own :class:`ParameterDefinition` (finite /
        minimum / maximum / required) via :meth:`ParameterDefinition.validate_value`.
        The generic core never hardcodes a domain rule. ``exp`` is
        duck-typed (must expose ``.parameters``) so the platform layer stays
        free of any runtime import.
        """
        problems: List[str] = []
        if self.study_definition is not None:
            defs = [sp.parameter for sp in self.study_definition.ordered()]
        else:
            defs = list(self.supported_parameters)
        for pdef in defs:
            pv = (exp.parameters or {}).get(pdef.name)
            if pv is None:
                continue                     # only the params it carries
            for prob in pdef.validate_value(pv.value):
                problems.append(f"{pdef.name}: {prob}")
        return problems


# --------------------------------------------------------------------------- #
# External Aerodynamics — a faithful description of today's application.
# Parameter/metric objects are defined once here and shared between
# supported_parameters and the study definition (single source of truth).
# Values mirror cfdauto/config.py defaults (aoa_parameter="P1",
# inlet_type="velocity_inlet") and the ColumnMap defaults (AOA_deg /
# Velocity_m_s) — descriptive; config remains authoritative at runtime.
# --------------------------------------------------------------------------- #
_AOA = ParameterDefinition(
    # display_name holds the short label the UI shows (Phase 2); the verbose
    # explanation lives in `description`.
    id="angle-of-attack", name="aoa", display_name="AOA",
    unit="deg", type=ParameterType.FLOAT, default_value=0.0,
    minimum=-90.0, maximum=90.0, step=1.0, required=True,
    category="flow", workbench_parameter="P1",
    description="Angle of attack: incidence angle of the body relative to "
                "the freestream, driven via the Workbench geometry rotation "
                "parameter.")

_VELOCITY = ParameterDefinition(
    id="freestream-velocity", name="velocity", display_name="Velocity",
    unit="m/s", type=ParameterType.FLOAT, default_value=20.0,
    minimum=0.01, maximum=None, step=5.0, required=True,
    category="flow", workbench_parameter=None,
    description="Freestream velocity magnitude, applied at the Fluent "
                "velocity inlet (not a Workbench parameter).")

_EXT_AERO_METRICS: Tuple[MetricDefinition, ...] = (
    MetricDefinition(
        id="lift-coefficient", name="cl", display_name="CL",
        description="Lift coefficient from the solver's lift report "
                    "definition, normalized by the configured reference "
                    "values."),
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
)

# The study definition binds those shared parameters to their spreadsheet
# columns and ordering — the ordering the runtime previously hardcoded as
# "AOA first, Velocity second". Column names mirror config.ColumnMap
# defaults.
_EXT_AERO_STUDY = StudyDefinition(parameters=(
    # example_values are the default sweep a fresh schedule is seeded with —
    # previously the EXAMPLE_AOA / EXAMPLE_VEL literals in
    # tools/make_experiment_template.py, now owned by the template.
    StudyParameter(parameter=_AOA, column_name="AOA_deg", order=0,
                   example_values=(0.0, 4.0, 8.0, 12.0)),
    StudyParameter(parameter=_VELOCITY, column_name="Velocity_m_s", order=1,
                   example_values=(20.0, 30.0)),
))

EXTERNAL_AERODYNAMICS = SimulationTemplate(
    id="external-aerodynamics",
    name="External Aerodynamics",
    description=(
        "Parametric external-flow study of a lifting body: sweep angle of "
        "attack and freestream velocity, extract force coefficients. This "
        "template describes Slipstream's original wing/airfoil workflow."),
    supported_parameters=(_AOA, _VELOCITY),
    supported_metrics=_EXT_AERO_METRICS,
    study_definition=_EXT_AERO_STUDY,
    # Phase 8A identity contract: AOA + velocity, with the labels that
    # reproduce the legacy case-id exactly (``r003_aoa8_v30``). Geometry is
    # AOA + any runtime Workbench extras — the legacy mesh-cache key.
    identity_parameters=(("aoa", "aoa"), ("velocity", "v")),
    geometry_parameters=("aoa",),
    default_solver="ansys-fluent",
    default_boundary_conditions={
        "inlet_type": "velocity_inlet",
        "aoa_method": "geometry",
    },
    report_type="study-summary",
    validation_profile="benchmark-comparison",
    execution_strategy_id="external-aerodynamics",
)
