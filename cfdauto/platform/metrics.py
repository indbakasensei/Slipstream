"""Generic simulation-metric metadata (Universal Platform, Phase 1).

A :class:`MetricDefinition` describes one *output quantity* of a CFD
study — lift, drag, CL, pressure drop, torque, mass flow, efficiency —
without assuming any physical domain. The airfoil workflow's CL/CD/L-D
are instances of this model (see ``templates.py``), not the model itself.

Metadata only: nothing here extracts values from Fluent, computes
derived quantities, or renders anything. Existing analytics
(``cfdauto/study_analytics.py``, the GUI charts/stats) are untouched by
this abstraction in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Conventional values for MetricDefinition.source — a plain string rather
# than an enum because future templates/solvers will legitimately invent
# new sources; these constants just keep the built-ins consistent.
SOURCE_SOLVER_REPORT = "solver-report"     # read from a solver report definition
SOURCE_DERIVED = "derived"                 # computed from other metrics (e.g. L/D)


@dataclass(frozen=True)
class MetricDefinition:
    """One output quantity of a simulation template.

    Attributes
    ----------
    id:
        Stable machine identifier, kebab-case (``"lift-coefficient"``).
    name:
        Short programmatic name (``"cl"``) — what code, columns, and
        analytics refer to.
    display_name:
        Human-facing label (``"Lift Coefficient"``).
    unit:
        Display unit string (``"N"``, ``"Pa"``, ``"kg/s"``); empty for
        dimensionless coefficients and ratios.
    source:
        Where the value comes from — one of the ``SOURCE_*`` constants
        above, or a template-specific string for future solvers.
    description:
        One or two sentences for tooltips/docs.
    output_column:
        Phase 8B — the spreadsheet/analytics column header this metric maps
        to (the generic output-column contract:
        template → declared metrics → output columns). ``None`` means
        "fall back to ``display_name``".
    """

    id: str
    name: str
    display_name: str
    unit: str = ""
    source: str = SOURCE_SOLVER_REPORT
    description: str = ""
    output_column: Optional[str] = None
