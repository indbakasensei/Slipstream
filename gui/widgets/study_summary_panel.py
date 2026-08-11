"""Study Summary panel — Sprint 4: a read-only Dashboard view of the
engine's post-batch analytics (``Orchestrator.current_study_summary``).

This widget never computes anything itself. ``set_summary()`` only formats
whatever :class:`~cfdauto.study_analytics.StudySummary` it is given (or
``None``) — the "no study yet" / "empty study" / "partial study" /
"completed study" states all fall directly out of the data already carried
by that object (``total_cases == 0``, the presence of ``ROW_STILL_PENDING``/
``ROW_STILL_RUNNING`` warnings, etc.) rather than needing separate branches
here.

The warning *display order* below (failed → unconverged → retries → still
running → still pending → empty) is a GUI-only presentation choice — it
does not require, and does not receive, any change to
``cfdauto/study_analytics.py``, which makes no ordering guarantee on the
list it returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional, Tuple

from PySide6.QtWidgets import (QGridLayout, QGroupBox, QLabel, QListWidget,
                               QVBoxLayout, QWidget)

from cfdauto.study_analytics import StudySummary, WarningCode
from gui.widgets.cards import StatCard
from gui.widgets.collapsible_section import CollapsibleSection

_EMPTY_STATE_TEXT = "Run a study to view summary statistics."

# Display-only severity order (see module docstring) — never used by
# study_analytics.py itself.
_WARNING_ORDER = {
    WarningCode.CASE_FAILED: 0,
    WarningCode.UNCONVERGED_SUCCESS: 1,
    WarningCode.RETRIES_OCCURRED: 2,
    WarningCode.ROW_STILL_RUNNING: 3,
    WarningCode.ROW_STILL_PENDING: 4,
    WarningCode.EMPTY_STUDY: 5,
}


def _sorted_warnings(warnings):
    return sorted(warnings, key=lambda w: _WARNING_ORDER.get(w.code, 99))


def _fmt(value, row: Optional[int] = None, fmt: str = "{:.3f}") -> Tuple[str, str]:
    """(display text, tooltip) for one optional numeric metric + its row."""
    if value is None:
        return "–", ""
    return fmt.format(value), (f"Row {row}" if row is not None else "")


class StudySummaryPanel(QWidget):
    """Dashboard widget: 8 metric tiles (reusing the existing ``StatCard``)
    plus a warnings list and a "last updated" timestamp — all populated
    solely from whatever is passed to :meth:`set_summary`."""

    # (internal key, card caption) — captions use the same single-glyph
    # icon convention already established elsewhere in the app (✓/✗/⚠/▶).
    _METRICS = (
        ("total", "Σ Total Cases"),
        ("successful", "✓ Successful"),
        ("failed", "✗ Failed"),
        ("retries", "↻ Retries"),
        ("best_ld", "★ Best L/D"),
        ("highest_lift", "↑ Highest Lift"),
        ("lowest_drag", "↓ Lowest Drag"),
        ("fastest_conv", "⚡ Fastest Convergence"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        box = QGroupBox("Study Summary")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(box)

        v = QVBoxLayout(box)
        grid = QGridLayout()
        self.cards: Dict[str, StatCard] = {}
        for i, (key, title) in enumerate(self._METRICS):
            card = StatCard(title)
            self.cards[key] = card
            grid.addWidget(card, i // 4, i % 4)
        v.addLayout(grid)

        self.updated_lbl = QLabel("")
        self.updated_lbl.setProperty("hint", True)
        v.addWidget(self.updated_lbl)

        # Neo v2.2: warnings live inside a collapsible
        # section so they don't permanently occupy space when there's
        # nothing to show. self.warnings_list itself is unchanged — same
        # QListWidget, same .count()/.item() behavior, regardless of
        # whether the section is currently expanded or collapsed.
        self.warnings_list = QListWidget()
        self.warnings_list.setMaximumHeight(110)
        self.warnings_section = CollapsibleSection("Warnings", self.warnings_list)
        v.addWidget(self.warnings_section)

        self.set_summary(None)     # initial "no study yet" state

    # ------------------------------------------------------------------ #
    def set_summary(self, summary: Optional[StudySummary]) -> None:
        """Fully replace everything displayed — never appends/merges with
        whatever was shown before. Read-only: never mutates ``summary``."""
        self.warnings_list.clear()

        if summary is None:
            for card in self.cards.values():
                card.set_value("–")
                card.setToolTip("")
            self.warnings_list.addItem(_EMPTY_STATE_TEXT)
            self.updated_lbl.setText("")
            return

        self.cards["total"].set_value(str(summary.total_cases))
        self.cards["successful"].set_value(str(summary.successful_cases))
        self.cards["failed"].set_value(str(summary.failed_cases))
        self.cards["retries"].set_value(str(summary.retries))
        for key in ("total", "successful", "failed", "retries"):
            self.cards[key].setToolTip("")

        text, tip = _fmt(summary.best_l_over_d, summary.best_l_over_d_row)
        self.cards["best_ld"].set_value(text)
        self.cards["best_ld"].setToolTip(tip)

        text, tip = _fmt(summary.highest_lift_n, summary.highest_lift_row, "{:.2f} N")
        self.cards["highest_lift"].set_value(text)
        self.cards["highest_lift"].setToolTip(tip)

        text, tip = _fmt(summary.lowest_drag_n, summary.lowest_drag_row, "{:.2f} N")
        self.cards["lowest_drag"].set_value(text)
        self.cards["lowest_drag"].setToolTip(tip)

        text, tip = _fmt(summary.fastest_convergence_iterations,
                         summary.fastest_convergence_row, "{:.0f} it")
        self.cards["fastest_conv"].set_value(text)
        self.cards["fastest_conv"].setToolTip(tip)

        if summary.warnings:
            for w in _sorted_warnings(summary.warnings):
                self.warnings_list.addItem(f"[{w.code.value}] {w.message}")
        else:
            self.warnings_list.addItem("No warnings.")

        # GUI-side timestamp only — reflects when *this widget* received
        # the summary, not anything computed by the backend.
        self.updated_lbl.setText(
            f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
