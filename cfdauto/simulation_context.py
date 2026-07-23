"""SimulationContext — the runtime's source of truth for study metadata
(Universal Platform, Phase 2).

Phase 1 introduced pure metadata models under ``cfdauto.platform``. Phase 2
gives the *runtime* a single object to read that metadata from, instead of
scattering hardcoded parameter/metric labels, units, and bounds across the
GUI and engine.

Dependency direction (strictly one-way): this module lives on the runtime
side and imports from ``cfdauto.platform``; the platform layer never
imports this. A ``SimulationContext`` is a lightweight, immutable snapshot —
"which template is this study, and what are its parameters and metrics."

Phase 2 always resolves to the **External Aerodynamics** template, obtained
through the registry (never by hardcoding the template id at call sites) —
so behavior is identical to v1.0. Future phases resolve the template
per-project instead of always defaulting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from .platform import (
    MetricDefinition,
    ParameterDefinition,
    SimulationTemplate,
    StudyDefinition,
    get_default_template,
)


@dataclass(frozen=True)
class SimulationContext:
    """Runtime metadata context for one study.

    Attributes
    ----------
    template:
        The :class:`~cfdauto.platform.SimulationTemplate` this study uses.
    project:
        Optional project identifier (name or root) for provenance/display;
        deliberately an opaque string, not a ProjectMetadata object, so the
        platform/runtime metadata layer stays decoupled from project
        management.
    """

    template: SimulationTemplate
    project: Optional[str] = None

    # ------------------------------------------------------------------ #
    @classmethod
    def default(cls, project: Optional[str] = None) -> "SimulationContext":
        """The context today's application always uses — External
        Aerodynamics, resolved through the registry."""
        return cls(template=get_default_template(), project=project)

    # -- metadata accessors (delegate to the template) ------------------ #
    @property
    def parameter_definitions(self) -> Tuple[ParameterDefinition, ...]:
        return self.template.supported_parameters

    @property
    def metric_definitions(self) -> Tuple[MetricDefinition, ...]:
        return self.template.supported_metrics

    def parameter(self, name_or_id: str) -> Optional[ParameterDefinition]:
        """Parameter definition by ``name`` or ``id`` (None if absent)."""
        return self.template.parameter(name_or_id)

    def metric(self, name_or_id: str) -> Optional[MetricDefinition]:
        """Metric definition by ``name`` or ``id`` (None if absent)."""
        return self.template.metric(name_or_id)

    # -- study definition (Phase 3A: template-driven input ordering) ---- #
    @property
    def study_definition(self) -> Optional[StudyDefinition]:
        return self.template.study_definition

    def input_columns(self) -> List[str]:
        """Ordered dataset/UI column keys for this study's *input*
        parameters — the labels the GUI dataset uses as its input-column
        headers (e.g. ``["AOA", "Velocity"]``), sourced from the template's
        StudyDefinition ordering rather than hardcoded at each call site.

        Falls back to ``supported_parameters`` order if the template
        declares no study definition, so every template resolves cleanly.
        """
        sd = self.template.study_definition
        if sd is not None and sd.parameters:
            return sd.display_names()
        return [p.display_name for p in self.template.supported_parameters]
