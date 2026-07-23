"""Study definition metadata (Universal Platform, Phase 3A).

A :class:`StudyDefinition` describes the *inputs* of a study — which
parameters it sweeps, in what order, how they map to spreadsheet columns,
and which are visible/editable. It is the layer that turns a template's
generic :class:`~cfdauto.platform.parameters.ParameterDefinition` list
into a concrete, ordered, spreadsheet-aware study specification.

Crucially, it **describes** a study; it never executes one. No Qt, no
solver, no runtime logic, no Excel generation — pure metadata. The runtime
(and, later, an Excel generator) reads ordering and column metadata from
here instead of hardcoding "AOA first, Velocity second."

Each :class:`StudyParameter` *references* a shared ParameterDefinition
rather than copying its fields, so display name / unit / bounds / defaults
have exactly one source of truth; the study layer adds only the
study-specific binding (spreadsheet column, order, visibility).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .parameters import ParameterDefinition


@dataclass(frozen=True)
class StudyParameter:
    """One input of a study: a ParameterDefinition bound to its place in
    the schedule.

    Attributes
    ----------
    parameter:
        The shared :class:`ParameterDefinition` (single source of truth for
        name/display_name/unit/bounds/default/required).
    column_name:
        The spreadsheet column header this parameter occupies
        (``"AOA_deg"``). Mirrors the template's default; the authoritative
        runtime column vocabulary still lives in ``config.ColumnMap`` until
        a later phase unifies them.
    order:
        Position in the schedule / editor (0-based, ascending).
    visible:
        Whether the parameter is shown in study views.
    editable:
        Whether users may edit this input in the schedule.
    group:
        Free-form grouping key for a future grouped editor ("" = ungrouped).
    """

    parameter: ParameterDefinition
    column_name: str
    order: int
    visible: bool = True
    editable: bool = True
    group: str = ""

    # -- delegate identity/display metadata to the ParameterDefinition -- #
    @property
    def id(self) -> str:
        return self.parameter.id

    @property
    def name(self) -> str:
        return self.parameter.name

    @property
    def display_name(self) -> str:
        return self.parameter.display_name

    @property
    def unit(self) -> str:
        return self.parameter.unit

    @property
    def required(self) -> bool:
        return self.parameter.required

    @property
    def default_value(self):
        return self.parameter.default_value


@dataclass(frozen=True)
class StudyDefinition:
    """The ordered input specification of a study — pure metadata.

    ``parameters`` may be given in any order; every accessor below returns
    them sorted by ``StudyParameter.order`` so callers never depend on
    construction order.
    """

    parameters: Tuple[StudyParameter, ...] = ()

    # ------------------------------------------------------------------ #
    def ordered(self) -> List[StudyParameter]:
        """All study parameters, sorted by ``order``."""
        return sorted(self.parameters, key=lambda p: p.order)

    def visible(self) -> List[StudyParameter]:
        """Ordered parameters flagged visible."""
        return [p for p in self.ordered() if p.visible]

    def editable(self) -> List[StudyParameter]:
        """Ordered parameters flagged editable."""
        return [p for p in self.ordered() if p.editable]

    def parameter(self, key: str) -> Optional[StudyParameter]:
        """Look up a study parameter by ``name``, ``id``, or ``column_name``
        (None if absent)."""
        for p in self.parameters:
            if key in (p.name, p.id, p.column_name):
                return p
        return None

    # -- spreadsheet-facing views (descriptive; nothing generates Excel) -- #
    def column_names(self) -> List[str]:
        """Ordered spreadsheet column headers for the study's inputs."""
        return [p.column_name for p in self.ordered()]

    def display_names(self) -> List[str]:
        """Ordered short display labels for the study's inputs — these are
        the keys the GUI dataset currently uses for input columns."""
        return [p.display_name for p in self.ordered()]

    def spreadsheet_columns(self) -> List[Dict[str, object]]:
        """Ordered per-column metadata a future Excel generator can iterate
        over instead of hardcoded headers. Descriptive only — Phase 3A does
        not generate any workbook from this.
        """
        return [
            {
                "column_name": p.column_name,
                "display_name": p.display_name,
                "unit": p.unit,
                "editable": p.editable,
                "required": p.required,
                "order": p.order,
            }
            for p in self.ordered()
        ]
