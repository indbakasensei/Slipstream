"""Study Analytics — a lightweight, read-only summary of one finished batch.

Computed once, after a batch's cases have already been written to the Excel
workbook, by re-reading exactly the rows the orchestrator queued for that
``run()`` call. This module is **purely computational**:

* it never writes to Excel, the ledger, or any artifact file;
* it never touches a solver/Workbench controller;
* it never logs anything itself.

Logging the result is the caller's (``Orchestrator``'s) responsibility —
keeping this module silent means it stays trivially unit-testable and safe
to reuse from a future GUI panel or CLI command without dragging along any
particular logging configuration.

Tie-breaking
------------
Where a metric (best L/D, highest lift, lowest drag, fastest convergence)
has multiple rows with the exact same value, the **first row encountered**
(rows are visited in ascending row-number order) wins and is never
displaced by a later, equally-good row. This is a strict ``>`` / ``<``
comparison — never ``>=`` / ``<=`` — applied identically to all four
metrics, so the choice is deterministic across repeated runs of the same
data.

Warning rules
-------------
Every :class:`StudyWarning` is produced by one fixed, explicit rule —
never a subjective judgment call:

* ``EMPTY_STUDY`` — the study had zero rows. Fires once.
* ``CASE_FAILED`` — fires once, carrying the total count, if
  ``failed_cases > 0``.
* ``RETRIES_OCCURRED`` — fires once, carrying the total count, if
  ``retries > 0``.
* ``UNCONVERGED_SUCCESS`` — fires once, carrying the count of
  successful-but-unconverged cases, if that count is > 0.
* ``ROW_STILL_RUNNING`` — fires once *per row* whose status is RUNNING at
  analysis time (e.g. a batch that stopped early or crashed mid-case).
* ``ROW_STILL_PENDING`` — fires once *per row* whose status is PENDING (or
  blank, or anything else not DONE/FAILED/RUNNING) at analysis time (a
  queued row that was never reached).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .excel_manager import ExcelManager
from .models import STATUS_DONE, STATUS_FAILED, STATUS_RUNNING
from .platform.metrics import (
    ANALYTICS_BEST_RATIO, ANALYTICS_HIGHEST,
    ANALYTICS_LOWEST, MetricDefinition,
)


class WarningCode(str, Enum):
    """Stable, filterable identifiers for :class:`StudyWarning` — intended
    to make future GUI filtering/grouping straightforward without parsing
    message text."""

    EMPTY_STUDY = "EMPTY_STUDY"
    CASE_FAILED = "CASE_FAILED"
    RETRIES_OCCURRED = "RETRIES_OCCURRED"
    UNCONVERGED_SUCCESS = "UNCONVERGED_SUCCESS"
    ROW_STILL_RUNNING = "ROW_STILL_RUNNING"
    ROW_STILL_PENDING = "ROW_STILL_PENDING"


@dataclass(frozen=True)
class StudyWarning:
    """One deterministic, rule-based observation about the study."""

    code: WarningCode
    message: str


@dataclass(frozen=True)
class StudyHighlight:
    """One per-metric optimization result produced by the generic analytics
    engine (Phase 8D).

    Structured as a frozen dataclass so it serialises cleanly and becomes
    part of the Phase 9 Report Generator API.

    Attributes
    ----------
    metric:
        Template metric name (``"l_over_d"``, ``"pressure_drop"``, …).
    value:
        The best value found across all analysed rows.
    row:
        The Excel row number that produced this value.
    unit:
        Display unit from the metric definition.
    role:
        The analytics role that triggered this highlight
        (``"best-ratio"``, ``"highest"``, ``"lowest"``).
    display_name:
        Human-facing label from the metric definition.
    """

    metric: str
    value: float
    row: int
    unit: str
    role: str
    display_name: str

    # -- serialisation (Phase 8E) -------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe dict for persistence."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StudyHighlight":
        """Rehydrate from a persisted dict."""
        return cls(**d)


@dataclass
class StudySummary:
    """Read-only snapshot of one finished (or partially finished) batch.

    Phase 8D adds ``highlights`` — a dict of :class:`StudyHighlight` objects
    keyed by metric name. The generic analytics engine populates this from
    the template's declared metrics and their ``analytics_role``; the legacy
    fields (``best_l_over_d``, ``highest_lift_n``, etc.) are kept for
    backward compatibility and are only populated when the template's metric
    names happen to match (e.g. External Aerodynamics).

    The ``average_*`` fields below are reserved for a future sprint —
    intentionally always ``None`` in this version.
    """

    total_cases: int = 0
    successful_cases: int = 0
    failed_cases: int = 0

    best_l_over_d: Optional[float] = None
    best_l_over_d_row: Optional[int] = None
    highest_lift_n: Optional[float] = None
    highest_lift_row: Optional[int] = None
    lowest_drag_n: Optional[float] = None
    lowest_drag_row: Optional[int] = None
    fastest_convergence_iterations: Optional[int] = None
    fastest_convergence_row: Optional[int] = None

    retries: int = 0
    warnings: List[StudyWarning] = field(default_factory=list)

    # Phase 8D: generic highlights — per-role optimization results keyed
    # by metric name. Populated by the template-driven analytics engine.
    # Each value is a :class:`StudyHighlight` (frozen dataclass).
    highlights: Dict[str, StudyHighlight] = field(default_factory=dict)

    # --- Reserved for a future sprint — never populated in v1 --------- #
    average_l_over_d: Optional[float] = None
    average_cl: Optional[float] = None
    average_cd: Optional[float] = None
    average_iterations: Optional[float] = None

    # -- serialisation (Phase 8E) -------------------------------------- #
    def to_json(self) -> str:
        """Serialise the entire summary to a JSON string."""
        d = asdict(self)
        # StudyHighlight objects serialise via their own to_dict.
        d["highlights"] = {k: v.to_dict() if hasattr(v, "to_dict") else v
                            for k, v in self.highlights.items()}
        return json.dumps(d, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "StudySummary":
        """Rehydrate a summary from :meth:`to_json` output.

        Handles both old (dict-based) and new (StudyHighlight-based)
        highlight formats for backward compatibility.
        """
        d = json.loads(text)
        hl_raw = d.pop("highlights", {})
        hl: Dict[str, StudyHighlight] = {}
        for k, v in hl_raw.items():
            if isinstance(v, dict) and "metric" in v:
                hl[k] = StudyHighlight.from_dict(v)
            elif isinstance(v, dict):
                # Legacy dict-based format (Phase 8D initial).
                hl[k] = StudyHighlight(
                    metric=v.get("metric", k),
                    value=v.get("value", 0.0),
                    row=v.get("row", 0),
                    unit=v.get("unit", ""),
                    role=v.get("role", ""),
                    display_name=v.get("display_name", k))
        # StudyWarning objects need reconstruction.
        warnings_raw = d.pop("warnings", [])
        warnings = [StudyWarning(code=WarningCode(w["code"]),
                                 message=w["message"])
                    for w in warnings_raw]
        return cls(highlights=hl, warnings=warnings, **d)

    def save_json(self, path: Path) -> None:
        """Persist the summary to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> Optional["StudySummary"]:
        """Load a persisted summary. Returns None if the file is missing
        or corrupt.
        """
        if not path.exists():
            return None
        try:
            return cls.from_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None


def _finite(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def _update_highlight(highlights: Dict[str, StudyHighlight],
                      metric_name: str, role: str, value: float, row: int,
                      unit: str, display_name: str) -> None:
    """Update a highlight entry for ``metric_name`` if ``value`` is better
    than the current best (or if no entry exists yet).

    ``role`` determines the comparison direction:

    * ``best-ratio`` / ``highest`` — strict ``>`` (first-wins tie-breaking)
    * ``lowest`` — strict ``<``
    """
    prev = highlights.get(metric_name)
    better = False
    if role in (ANALYTICS_BEST_RATIO, ANALYTICS_HIGHEST):
        better = prev is None or value > prev.value
    elif role == ANALYTICS_LOWEST:
        better = prev is None or value < prev.value
    if better:
        highlights[metric_name] = StudyHighlight(
            metric=metric_name, value=value, row=row,
            unit=unit, role=role, display_name=display_name)


def _metric_value_for_role(role: str, mv: Any) -> Optional[float]:
    """Extract a comparable float from a MetricValue or raw value for the
    given analytics role. Returns None when the value is absent or not
    finite (the caller simply skips that row for that metric).
    """
    if mv is None:
        return None
    val = mv.value if hasattr(mv, "value") else mv
    return float(val) if _finite(val) else None


def analyze_study(excel: ExcelManager, rows: Iterable[int],
                  retries: int = 0,
                  template: Optional[Any] = None) -> StudySummary:
    """Compute a :class:`StudySummary` for exactly ``rows`` — the row
    numbers the caller queued for one batch — by re-reading their current
    state from ``excel``. Never raises; a row whose data can't be read
    cleanly is simply skipped for that metric, not fatal to the summary.

    Phase 8D: when ``template`` is provided (a
    :class:`~cfdauto.platform.SimulationTemplate`), the analytics engine
    reads the template's declared metrics and their ``analytics_role`` to
    compute generic ``highlights`` — no hard-coded metric names. The legacy
    fields (``best_l_over_d``, ``highest_lift_n``, etc.) are still
    populated when the template's metric names match, preserving backward
    compatibility for External Aerodynamics.

    When ``template`` is ``None``, the legacy hard-coded analytics path
    runs unchanged (pre-Phase-8B callers).
    """
    row_set = sorted(set(rows))
    summary = StudySummary(total_cases=len(row_set), retries=max(0, retries))

    if not row_set:
        summary.warnings.append(StudyWarning(
            WarningCode.EMPTY_STUDY, "The study had no experiment rows to run."))
        return summary

    status_by_row = {e.row: (e.status or "").strip().upper()
                     for e in excel.read_experiments() if e.row in row_set}

    # Phase 8D: build a role map from the template's declared metrics.
    # metric_name → (analytics_role, display_name, unit)
    role_map: Dict[str, Tuple[str, str, str]] = {}
    if template is not None:
        for md in template.supported_metrics:
            if md.analytics_role:
                role_map[md.name] = (md.analytics_role, md.display_name, md.unit)

    unconverged_success = 0
    for row in row_set:
        status = status_by_row.get(row, "")

        if status == STATUS_DONE:
            summary.successful_cases += 1

            if template is not None:
                # Phase 8D: generic path — read template metrics from Excel.
                metrics = excel.read_row_metrics(row)
                for metric_name, (role, display_name, unit) in role_map.items():
                    mv = metrics.get(metric_name)
                    val = _metric_value_for_role(role, mv)
                    if val is not None:
                        _update_highlight(summary.highlights, metric_name,
                                          role, val, row, unit, display_name)

                # Bookkeeping-derived: fastest convergence is NOT a metric
                # analytics role — it is always tracked from iterations/
                # converged bookkeeping, regardless of template.
                outputs = excel.read_row_outputs(row)
                converged = (str(outputs.get("converged") or "")
                             .strip().upper() == "YES")
                iterations = outputs.get("iterations")
                if converged and _finite(iterations):
                    it = int(iterations)
                    if (summary.fastest_convergence_iterations is None
                            or it < summary.fastest_convergence_iterations):
                        summary.fastest_convergence_iterations = it
                        summary.fastest_convergence_row = row
                if not converged:
                    unconverged_success += 1
            else:
                # Legacy path — hardcoded External Aero metric names.
                outputs = excel.read_row_outputs(row)

                cl_cd = outputs.get("cl_cd")
                if _finite(cl_cd) and (summary.best_l_over_d is None
                                       or cl_cd > summary.best_l_over_d):
                    summary.best_l_over_d = float(cl_cd)
                    summary.best_l_over_d_row = row

                lift = outputs.get("lift")
                if _finite(lift) and (summary.highest_lift_n is None
                                      or lift > summary.highest_lift_n):
                    summary.highest_lift_n = float(lift)
                    summary.highest_lift_row = row

                drag = outputs.get("drag")
                if _finite(drag) and (summary.lowest_drag_n is None
                                      or drag < summary.lowest_drag_n):
                    summary.lowest_drag_n = float(drag)
                    summary.lowest_drag_row = row

                converged = (str(outputs.get("converged") or "")
                             .strip().upper() == "YES")
                iterations = outputs.get("iterations")
                if converged and _finite(iterations):
                    if (summary.fastest_convergence_iterations is None
                            or iterations < summary.fastest_convergence_iterations):
                        summary.fastest_convergence_iterations = int(iterations)
                        summary.fastest_convergence_row = row
                if not converged:
                    unconverged_success += 1

            # Phase 8D: also populate legacy fields from highlights for
            # External Aero (when the template declares matching metric names).
            if template is not None:
                hl = summary.highlights
                if "l_over_d" in hl and hl["l_over_d"].role == ANALYTICS_BEST_RATIO:
                    summary.best_l_over_d = hl["l_over_d"].value
                    summary.best_l_over_d_row = hl["l_over_d"].row
                if "lift" in hl and hl["lift"].role == ANALYTICS_HIGHEST:
                    summary.highest_lift_n = hl["lift"].value
                    summary.highest_lift_row = hl["lift"].row
                if "drag" in hl and hl["drag"].role == ANALYTICS_LOWEST:
                    summary.lowest_drag_n = hl["drag"].value
                    summary.lowest_drag_row = hl["drag"].row

        elif status == STATUS_FAILED:
            summary.failed_cases += 1
        elif status == STATUS_RUNNING:
            summary.warnings.append(StudyWarning(
                WarningCode.ROW_STILL_RUNNING,
                f"Row {row} was still RUNNING at analysis time."))
        else:
            summary.warnings.append(StudyWarning(
                WarningCode.ROW_STILL_PENDING,
                f"Row {row} was still PENDING at analysis time "
                f"(status={status or 'PENDING'})."))

    if summary.failed_cases > 0:
        summary.warnings.append(StudyWarning(
            WarningCode.CASE_FAILED, f"{summary.failed_cases} case(s) failed."))
    if unconverged_success > 0:
        summary.warnings.append(StudyWarning(
            WarningCode.UNCONVERGED_SUCCESS,
            f"{unconverged_success} case(s) completed without meeting the "
            f"convergence tolerance."))
    if summary.retries > 0:
        summary.warnings.append(StudyWarning(
            WarningCode.RETRIES_OCCURRED,
            f"{summary.retries} retry attempt(s) were needed across this batch."))

    return summary
