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

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, List, Optional

from .excel_manager import ExcelManager
from .models import STATUS_DONE, STATUS_FAILED, STATUS_RUNNING


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


@dataclass
class StudySummary:
    """Read-only snapshot of one finished (or partially finished) batch.

    The ``average_*`` fields below are reserved for a future sprint —
    intentionally always ``None`` in this version. They exist now so the
    dataclass's shape doesn't need to change (breaking any code already
    consuming it) once those aggregate metrics are implemented.
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

    # --- Reserved for a future sprint — never populated in v1 --------- #
    average_l_over_d: Optional[float] = None
    average_cl: Optional[float] = None
    average_cd: Optional[float] = None
    average_iterations: Optional[float] = None


def _finite(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x)


def analyze_study(excel: ExcelManager, rows: Iterable[int],
                  retries: int = 0) -> StudySummary:
    """Compute a :class:`StudySummary` for exactly ``rows`` — the row
    numbers the caller queued for one batch — by re-reading their current
    state from ``excel``. Never raises; a row whose data can't be read
    cleanly is simply skipped for that metric, not fatal to the summary.
    """
    row_set = sorted(set(rows))
    summary = StudySummary(total_cases=len(row_set), retries=max(0, retries))

    if not row_set:
        summary.warnings.append(StudyWarning(
            WarningCode.EMPTY_STUDY, "The study had no experiment rows to run."))
        return summary

    status_by_row = {e.row: (e.status or "").strip().upper()
                     for e in excel.read_experiments() if e.row in row_set}

    unconverged_success = 0
    for row in row_set:
        status = status_by_row.get(row, "")

        if status == STATUS_DONE:
            summary.successful_cases += 1
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

            converged = str(outputs.get("converged") or "").strip().upper() == "YES"
            iterations = outputs.get("iterations")
            if converged and _finite(iterations):
                if (summary.fastest_convergence_iterations is None
                        or iterations < summary.fastest_convergence_iterations):
                    summary.fastest_convergence_iterations = int(iterations)
                    summary.fastest_convergence_row = row
            if not converged:
                unconverged_success += 1

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
