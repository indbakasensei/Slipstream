"""ExperimentDefinition — the runtime materialization of a study's input
schema (Universal Platform, Phase 3B).

Where :class:`~cfdauto.platform.study_definition.StudyDefinition` is *pure
platform metadata* ("this study has these parameters, in this order, mapped
to these columns"), :class:`ExperimentDefinition` is the *runtime object*
that consumes it: it materializes concrete default experiment rows, exposes
the spreadsheet/editable/validation views the runtime needs, and validates
concrete values against the parameter metadata.

The distinction the architecture insists on (see
``docs/PLATFORM_ARCHITECTURE.md``): StudyDefinition = platform metadata,
ExperimentDefinition = runtime state. This object **references** a
StudyDefinition; it never copies its fields. Dependency direction stays
one-way: this runtime module imports from ``cfdauto.platform``; the
platform layer never imports this.

Phase 3B always materializes the External Aerodynamics study, so behavior
is byte-identical to v1.0; a future phase resolves per-project.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .platform import ParameterDefinition, StudyDefinition
from .simulation_context import SimulationContext


@dataclass(frozen=True)
class ExperimentDefinition:
    """Runtime view of a study's input schema, built from a StudyDefinition."""

    study: StudyDefinition

    # ------------------------------------------------------------------ #
    @classmethod
    def from_context(cls, ctx: SimulationContext) -> "ExperimentDefinition":
        """Build from a :class:`SimulationContext` (uses its template's study
        definition; an empty one if the template declares none)."""
        return cls(study=ctx.study_definition or StudyDefinition())

    @classmethod
    def default(cls) -> "ExperimentDefinition":
        """The runtime schema for today's default study (External
        Aerodynamics), resolved through the registry."""
        return cls.from_context(SimulationContext.default())

    # -- schema views (delegate to the StudyDefinition) ----------------- #
    def spreadsheet_columns(self) -> List[Dict[str, object]]:
        """Ordered per-input-column metadata for workbook generation."""
        return self.study.spreadsheet_columns()

    def column_names(self) -> List[str]:
        """Ordered spreadsheet column headers for the study's inputs."""
        return self.study.column_names()

    def input_columns(self) -> List[str]:
        """Ordered dataset/UI column keys for the study's inputs (the keys
        the GUI dataset and queue use as input-column headers)."""
        return self.study.display_names()

    def editable_columns(self) -> List[str]:
        """Column names of the inputs users may edit."""
        return [p.column_name for p in self.study.editable()]

    def default_values(self) -> Dict[str, object]:
        """Per-input default value, keyed by column name."""
        return {p.column_name: p.default_value for p in self.study.ordered()}

    # -- runtime materialization ---------------------------------------- #
    def default_experiment_rows(self) -> List[Tuple[float, ...]]:
        """Concrete default rows for a fresh schedule: the cartesian product
        of each input's ``example_values`` (in input order). A parameter
        with no ``example_values`` contributes its single ``default_value``,
        so the product is always well-defined.

        For External Aerodynamics this yields the same 8 rows the legacy
        template hardcoded — AOA (0,4,8,12) × Velocity (20,30), AOA
        varying slowest.
        """
        params = self.study.ordered()
        if not params:
            return []
        axes = []
        for p in params:
            vals = p.example_values if p.example_values else (
                (p.default_value,) if p.default_value is not None else ())
            axes.append([float(v) for v in vals])
        return [tuple(combo) for combo in itertools.product(*axes)]

    # -- validation (template-driven; delegates to ParameterDefinition) - #
    def parameter_for_column(self, column_name: str) -> Optional[ParameterDefinition]:
        sp = self.study.parameter(column_name)
        return sp.parameter if sp is not None else None

    def validate_value(self, column_name: str, value: object) -> List[str]:
        """Validate one input value against its ParameterDefinition
        (min/max/required/type). Returns every problem, never raises —
        the template-driven validation surface. Unknown columns validate
        clean (they aren't this study's inputs)."""
        pdef = self.parameter_for_column(column_name)
        return pdef.validate_value(value) if pdef is not None else []

    def validate_row(self, values: Dict[str, object]) -> List[str]:
        """Validate a full input row (column_name -> value) against every
        input parameter's metadata; returns all problems across the row."""
        problems: List[str] = []
        for p in self.study.ordered():
            problems.extend(p.parameter.validate_value(values.get(p.column_name)))
        return problems
