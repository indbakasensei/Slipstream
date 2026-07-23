"""StudyOverviewTable — GUI Modernization (v1.0.0-rc2): a dashboard section
showing Project / AOA range / Velocity range / case counts / average
CL·CD·L-D / execution time / status, computed directly from
``AppState.df`` — exactly the way ``StatsPanel`` already computes its own
mean/std/min/max today. No ``cfdauto`` import, no new backend logic.

This is intentionally a *separate* widget from the existing
``StudySummaryPanel`` (``Orchestrator.current_study_summary`` — total/
successful/failed/retries/best-L-D/warnings), which keeps its own
attributes and behavior completely unchanged for test compatibility. The
two together cover, respectively, "what does this dataset look like"
(this widget) and "what did the engine's own analytics say about the
last batch" (StudySummaryPanel).
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (QFrame, QHeaderView, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState
from gui.widgets.section_header import SectionHeader

_FIELDS = ["Project", "AOA Range", "Velocity Range", "Cases", "Completed",
          "Failed", "Average CL", "Average CD", "Average L/D",
          "Execution Time", "Status"]


class StudyOverviewTable(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        card = QFrame()
        card.setProperty("card", True)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                                    theme.CARD_MARGIN, theme.CARD_MARGIN)
        card_lay.setSpacing(theme.SPACE_SM)
        card_lay.addWidget(SectionHeader("Study Overview", icon="📋"))

        self.table = QTableWidget(len(_FIELDS), 2)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        card_lay.addWidget(self.table)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        state.datasetChanged.connect(self.refresh)
        state.projectLoaded.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        values = self._compute_values()
        for r, field in enumerate(_FIELDS):
            self.table.setItem(r, 0, QTableWidgetItem(field))
            self.table.setItem(r, 1, QTableWidgetItem(str(values.get(field, "–"))))
        self.table.resizeRowsToContents()

    def _compute_values(self) -> dict:
        df = self.state.df
        values = {"Project": self.state.config_path.stem
                 if self.state.config_path else "–"}
        if not len(df):
            for f in _FIELDS[1:]:
                values[f] = "–"
            values["Status"] = "No project loaded"
            return values

        aoa = pd.to_numeric(df["AOA"], errors="coerce").dropna()
        vel = pd.to_numeric(df["Velocity"], errors="coerce").dropna()
        values["AOA Range"] = (f"{aoa.min():g}° to {aoa.max():g}°"
                               if len(aoa) else "–")
        values["Velocity Range"] = (f"{vel.min():g} to {vel.max():g} m/s"
                                    if len(vel) else "–")

        counts = df["Status"].value_counts()
        total = len(df)
        completed = int(counts.get("DONE", 0))
        failed = int(counts.get("FAILED", 0))
        running = int(counts.get("RUNNING", 0))
        values["Cases"] = str(total)
        values["Completed"] = str(completed)
        values["Failed"] = str(failed)

        done = df[df["Status"] == "DONE"]
        for label, col in (("Average CL", "CL"), ("Average CD", "CD"),
                          ("Average L/D", "L/D")):
            s = (pd.to_numeric(done[col], errors="coerce").dropna()
                if col in done else pd.Series(dtype=float))
            values[label] = f"{s.mean():.4f}" if len(s) else "–"

        dur = (pd.to_numeric(done["Duration_min"], errors="coerce").dropna()
              if "Duration_min" in done else pd.Series(dtype=float))
        values["Execution Time"] = f"{dur.sum():.1f} min" if len(dur) else "–"

        if completed + failed == total:
            values["Status"] = "Complete" if failed == 0 else f"Complete ({failed} failed)"
        elif running > 0:
            values["Status"] = "Running"
        else:
            values["Status"] = "Pending"
        return values
