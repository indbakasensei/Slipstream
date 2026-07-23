"""Generic simulation-parameter metadata (Universal Platform, Phase 1).

A :class:`ParameterDefinition` describes one *input variable* of a CFD
study — angle of attack, inlet velocity, RPM, pressure, temperature,
a geometric dimension — without knowing or caring what physical domain
it belongs to. The airfoil workflow's "AOA" and "Velocity" are just two
instances of this model (see ``templates.py``), not special cases.

Deliberately metadata-only: nothing here reads Excel, drives Workbench,
or touches the GUI. The one piece of behavior — :meth:`validate_value` —
is a pure function of the definition itself, so a future dynamic
parameter editor or schedule validator can share a single source of
truth for "is this value acceptable."
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class ParameterType(str, Enum):
    """Value domain of a parameter. String-valued so it serializes
    naturally to JSON/YAML without custom encoders."""

    FLOAT = "float"
    INTEGER = "integer"
    STRING = "string"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class ParameterDefinition:
    """One input variable of a simulation template.

    Attributes
    ----------
    id:
        Stable machine identifier, kebab-case (``"angle-of-attack"``).
        Never displayed; safe to persist and compare across versions.
    name:
        Short programmatic name (``"aoa"``) — what code and column
        mappings refer to.
    display_name:
        Human-facing label (``"Angle of Attack"``).
    unit:
        Display unit string (``"deg"``, ``"m/s"``, ``"rpm"``); empty for
        dimensionless parameters.
    type:
        The value domain (:class:`ParameterType`).
    default_value:
        Pre-filled value for new studies; ``None`` = no default.
    minimum / maximum:
        Inclusive numeric bounds; ``None`` = unbounded on that side.
        Ignored for non-numeric types.
    step:
        Suggested increment for editors/sweep generators; ``None`` = free.
    required:
        Whether every experiment must supply a value.
    category:
        Free-form grouping key for future editors (``"flow"``,
        ``"geometry"``, ``"boundary-conditions"``).
    workbench_parameter:
        Name of the ANSYS Workbench parameter this drives (``"P1"``),
        or ``None`` for parameters not bound to Workbench (e.g. a pure
        solver setting).
    description:
        One or two sentences for tooltips/docs.
    """

    id: str
    name: str
    display_name: str
    unit: str = ""
    type: ParameterType = ParameterType.FLOAT
    default_value: Optional[object] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    required: bool = True
    category: str = ""
    workbench_parameter: Optional[str] = None
    description: str = ""

    # ------------------------------------------------------------------ #
    def validate_value(self, value: object) -> List[str]:
        """Return every problem with ``value`` against this definition
        (empty list = acceptable). Never raises — mirrors the codebase's
        established validator convention (``Config.validate_static``,
        ``validate_project_structure``): collect all problems, don't stop
        at the first.
        """
        problems: List[str] = []
        label = self.display_name or self.name

        if value is None:
            if self.required:
                problems.append(f"{label}: a value is required.")
            return problems

        if self.type in (ParameterType.FLOAT, ParameterType.INTEGER):
            try:
                num = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                problems.append(f"{label}: '{value}' is not a number.")
                return problems
            if not math.isfinite(num):
                problems.append(f"{label}: value must be finite.")
                return problems
            if self.type is ParameterType.INTEGER and num != int(num):
                problems.append(f"{label}: '{value}' is not a whole number.")
            if self.minimum is not None and num < self.minimum:
                problems.append(
                    f"{label}: {num:g} is below the minimum of {self.minimum:g}.")
            if self.maximum is not None and num > self.maximum:
                problems.append(
                    f"{label}: {num:g} is above the maximum of {self.maximum:g}.")
        elif self.type is ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                problems.append(f"{label}: '{value}' is not true/false.")
        elif self.type is ParameterType.STRING:
            if not isinstance(value, str):
                problems.append(f"{label}: '{value}' is not text.")

        return problems
