"""Sprint 4 — behavioral tests for gui.widgets.StudySummaryPanel.

The panel is deliberately dumb: it only formats whatever StudySummary it is
handed (or None) — it never recomputes analytics itself (that's
cfdauto.study_analytics's job, already tested separately). These tests
protect the panel's own contract: every one of the four states from the
spec ("no study yet", empty study, partial study, completed study") renders
correctly, warnings display in the agreed deterministic severity order, the
"last updated" timestamp is GUI-side only, and — the one behavior most
likely to regress silently — calling set_summary() twice never leaves stale
data from the first call visible alongside the second.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication                       # noqa: E402

from cfdauto.study_analytics import (                              # noqa: E402
    StudySummary,
    StudyWarning,
    WarningCode,
)
from gui.widgets.study_summary_panel import (                      # noqa: E402
    _EMPTY_STATE_TEXT,
    StudySummaryPanel,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _warning_lines(panel: StudySummaryPanel) -> list[str]:
    return [panel.warnings_list.item(i).text()
           for i in range(panel.warnings_list.count())]


# --------------------------------------------------------------------- #
# Group: "no study yet"
# --------------------------------------------------------------------- #
def test_initial_state_shows_placeholder_and_no_timestamp(qapp):
    panel = StudySummaryPanel()
    for card in panel.cards.values():
        assert card.value_lbl.text() == "–"
    assert _warning_lines(panel) == [_EMPTY_STATE_TEXT]
    assert panel.updated_lbl.text() == ""


def test_set_summary_none_resets_cleanly_after_a_real_summary(qapp):
    panel = StudySummaryPanel()
    panel.set_summary(StudySummary(total_cases=3, successful_cases=3))
    assert panel.cards["total"].value_lbl.text() == "3"

    panel.set_summary(None)
    for card in panel.cards.values():
        assert card.value_lbl.text() == "–"
        assert card.toolTip() == ""
    assert _warning_lines(panel) == [_EMPTY_STATE_TEXT]
    assert panel.updated_lbl.text() == ""


# --------------------------------------------------------------------- #
# Group: empty study
# --------------------------------------------------------------------- #
def test_empty_study_summary_renders_zeros_and_its_warning(qapp):
    panel = StudySummaryPanel()
    summary = StudySummary(total_cases=0, warnings=[
        StudyWarning(WarningCode.EMPTY_STUDY, "The study had no experiment rows to run."),
    ])
    panel.set_summary(summary)
    assert panel.cards["total"].value_lbl.text() == "0"
    assert panel.cards["successful"].value_lbl.text() == "0"
    assert panel.cards["best_ld"].value_lbl.text() == "–"
    assert _warning_lines(panel) == ["[EMPTY_STUDY] The study had no experiment rows to run."]
    assert panel.updated_lbl.text().startswith("Last updated:")


# --------------------------------------------------------------------- #
# Group: partial study (stopped early / crashed mid-batch)
# --------------------------------------------------------------------- #
def test_partial_study_shows_running_and_pending_warnings(qapp):
    panel = StudySummaryPanel()
    summary = StudySummary(total_cases=3, successful_cases=1, warnings=[
        StudyWarning(WarningCode.ROW_STILL_RUNNING, "Row 3 was still RUNNING at analysis time."),
        StudyWarning(WarningCode.ROW_STILL_PENDING, "Row 4 was still PENDING at analysis time (status=PENDING)."),
    ])
    panel.set_summary(summary)
    lines = _warning_lines(panel)
    assert any("ROW_STILL_RUNNING" in l for l in lines)
    assert any("ROW_STILL_PENDING" in l for l in lines)
    assert len(lines) == 2


# --------------------------------------------------------------------- #
# Group: completed study — all metrics + row tooltips
# --------------------------------------------------------------------- #
def test_completed_summary_renders_all_metrics_with_tooltips(qapp):
    panel = StudySummaryPanel()
    summary = StudySummary(
        total_cases=4, successful_cases=4, failed_cases=0, retries=1,
        best_l_over_d=15.234, best_l_over_d_row=3,
        highest_lift_n=88.5, highest_lift_row=2,
        lowest_drag_n=3.21, lowest_drag_row=4,
        fastest_convergence_iterations=280, fastest_convergence_row=1,
        warnings=[StudyWarning(WarningCode.RETRIES_OCCURRED,
                              "1 retry attempt(s) were needed across this batch.")],
    )
    panel.set_summary(summary)
    assert panel.cards["total"].value_lbl.text() == "4"
    assert panel.cards["successful"].value_lbl.text() == "4"
    assert panel.cards["failed"].value_lbl.text() == "0"
    assert panel.cards["retries"].value_lbl.text() == "1"
    assert panel.cards["best_ld"].value_lbl.text() == "15.234"
    assert panel.cards["best_ld"].toolTip() == "Row 3"
    assert panel.cards["highest_lift"].value_lbl.text() == "88.50 N"
    assert panel.cards["highest_lift"].toolTip() == "Row 2"
    assert panel.cards["lowest_drag"].value_lbl.text() == "3.21 N"
    assert panel.cards["lowest_drag"].toolTip() == "Row 4"
    assert panel.cards["fastest_conv"].value_lbl.text() == "280 it"
    assert panel.cards["fastest_conv"].toolTip() == "Row 1"
    assert _warning_lines(panel) == ["[RETRIES_OCCURRED] 1 retry attempt(s) were needed across this batch."]


def test_no_warnings_shows_the_no_warnings_line(qapp):
    panel = StudySummaryPanel()
    panel.set_summary(StudySummary(total_cases=2, successful_cases=2))
    assert _warning_lines(panel) == ["No warnings."]


# --------------------------------------------------------------------- #
# Group: deterministic warning display order (GUI-side only)
# --------------------------------------------------------------------- #
def test_warnings_are_displayed_in_fixed_severity_order_regardless_of_input_order(qapp):
    panel = StudySummaryPanel()
    # Deliberately scrambled input order — the panel must still display
    # them: failed, unconverged, retries, still-running, still-pending.
    scrambled = [
        StudyWarning(WarningCode.ROW_STILL_PENDING, "Row 9 pending"),
        StudyWarning(WarningCode.RETRIES_OCCURRED, "2 retries"),
        StudyWarning(WarningCode.ROW_STILL_RUNNING, "Row 5 running"),
        StudyWarning(WarningCode.CASE_FAILED, "1 case(s) failed."),
        StudyWarning(WarningCode.UNCONVERGED_SUCCESS, "1 unconverged"),
    ]
    panel.set_summary(StudySummary(total_cases=5, warnings=scrambled))
    lines = _warning_lines(panel)
    codes_in_display_order = [l.split("]")[0][1:] for l in lines]
    assert codes_in_display_order == [
        "CASE_FAILED", "UNCONVERGED_SUCCESS", "RETRIES_OCCURRED",
        "ROW_STILL_RUNNING", "ROW_STILL_PENDING",
    ]


# --------------------------------------------------------------------- #
# Group: repeated calls never leave stale state (explicit Sprint 4 ask)
# --------------------------------------------------------------------- #
def test_calling_set_summary_twice_replaces_all_values_with_no_stale_state(qapp):
    panel = StudySummaryPanel()
    first = StudySummary(
        total_cases=10, successful_cases=8, failed_cases=2, retries=3,
        best_l_over_d=9.0, best_l_over_d_row=1,
        warnings=[StudyWarning(WarningCode.CASE_FAILED, "2 case(s) failed."),
                 StudyWarning(WarningCode.RETRIES_OCCURRED, "3 retry attempt(s)...")],
    )
    panel.set_summary(first)
    assert panel.cards["failed"].value_lbl.text() == "2"
    assert len(_warning_lines(panel)) == 2

    second = StudySummary(total_cases=1, successful_cases=1, failed_cases=0, retries=0)
    panel.set_summary(second)

    # Every numeric field must reflect ONLY the second summary.
    assert panel.cards["total"].value_lbl.text() == "1"
    assert panel.cards["successful"].value_lbl.text() == "1"
    assert panel.cards["failed"].value_lbl.text() == "0"
    assert panel.cards["retries"].value_lbl.text() == "0"
    assert panel.cards["best_ld"].value_lbl.text() == "–"
    assert panel.cards["best_ld"].toolTip() == ""
    # The warnings list must show exactly the second summary's warnings
    # (here: none), not the first call's two warnings still lingering.
    assert _warning_lines(panel) == ["No warnings."]
