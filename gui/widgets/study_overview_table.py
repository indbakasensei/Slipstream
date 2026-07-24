"""StudyOverviewTable — GUI Modernization (v1.0.0-rc2): a dashboard section
showing Project / one input-range row *per study parameter* / case counts /
average CL·CD·L-D / execution time / status, computed directly from
``AppState.df`` — exactly the way ``StatsPanel`` already computes its own
mean/std/min/max today. No ``cfdauto`` import, no new backend logic.

Dynamic Template UI (Capability 2): the per-input range rows are generated
from the active template's input metadata (label + unit) rather than a
hardcoded AOA/Velocity pair, so the overview adapts to any template.

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

# The per-input range rows are inserted between the head and tail at refresh
# time (one "<Input> Range" row per study parameter, from metadata).
_HEAD = ["Project"]
_TAIL = ["Cases", "Completed", "Failed", "Average CL", "Average CD",
         "Average L/D", "Execution Time", "Status"]


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

        self.table = QTableWidget(len(self._fields()), 2)
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
    def _fields(self) -> list:
        """All row labels: Project, one range row per study input (from
        metadata), then the fixed count/average/status rows."""
        ranges = [f"{sp.display_name} Range"
                  for sp in self.state.input_parameters()]
        return _HEAD + ranges + _TAIL

    def refresh(self) -> None:
        fields = self._fields()
        values = self._compute_values()
        self.table.setRowCount(len(fields))
        for r, field in enumerate(fields):
            self.table.setItem(r, 0, QTableWidgetItem(field))
            self.table.setItem(r, 1, QTableWidgetItem(str(values.get(field, "–"))))
        self.table.resizeRowsToContents()

    def _compute_values(self) -> dict:
        df = self.state.df
        values = {"Project": self.state.config_path.stem
                 if self.state.config_path else "–"}
        if not len(df):
            for f in self._fields()[1:]:
                values[f] = "–"
            values["Status"] = "No project loaded"
            return values

        # One range row per study input parameter, labelled + unit'd from
        # metadata (no hardcoded parameter names).
        for sp in self.state.input_parameters():
            col = sp.display_name
            series = (pd.to_numeric(df[col], errors="coerce").dropna()
                      if col in df else pd.Series(dtype=float))
            unit = f" {sp.unit}" if sp.unit else ""
            values[f"{col} Range"] = (
                f"{series.min():g} to {series.max():g}{unit}"
                if len(series) else "–")

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
