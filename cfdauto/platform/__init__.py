"""Universal CFD Platform foundation (v2.0.0-dev, Phase 1).

Pure-metadata abstractions that let Slipstream describe *any* CFD study —
not just the airfoil AOA/velocity workflow it grew up with:

* :class:`~cfdauto.platform.parameters.ParameterDefinition` — a generic
  input variable (AOA, velocity, RPM, pressure, …).
* :class:`~cfdauto.platform.metrics.MetricDefinition` — a generic output
  quantity (CL, drag, torque, mass flow, …).
* :class:`~cfdauto.platform.templates.SimulationTemplate` — a named bundle
  of parameters + metrics + solver defaults describing one *kind* of study.
* :class:`~cfdauto.platform.registry.TemplateRegistry` — discovery/lookup
  of available templates.

Phase 1 contract: **nothing at runtime consumes these yet.** The existing
engine, GUI, Excel schedule, and analytics are untouched; the single
registered template (External Aerodynamics) simply *describes* the current
workflow so future phases can migrate onto it incrementally. See
``docs/PLATFORM_ARCHITECTURE.md`` for the full rationale and roadmap.

This package must never import from ``gui/``, the solver controllers, or
anything Qt — it is data models only.
"""

from .metrics import MetricDefinition                      # noqa: F401
from .parameters import ParameterDefinition, ParameterType  # noqa: F401
from .registry import (                                     # noqa: F401
    DEFAULT_TEMPLATE_ID,
    TemplateRegistry,
    get_default_registry,
    get_default_template,
)
from .study_definition import StudyDefinition, StudyParameter  # noqa: F401
from .templates import EXTERNAL_AERODYNAMICS, SimulationTemplate  # noqa: F401
