"""Statistical summary of the completed dataset (v0.8 scope: descriptive
stats + status counts + headline best case). Deeper analytics arrive in v2.0
per the blueprint; this panel already reads the same DataFrame they will."""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from gui.state import AppState

_METRICS = ["CL", "CD", "L/D", "Lift_N", "Drag_N", "Iterations"]
_STATS = ["count", "mean", "std", "min", "max"]


class StatsPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.head = QLabel("")
        self.head.setProperty("h2", True)
        self.best = QLabel("")
        self.table = QTableWidget(len(_METRICS), len(_STATS))
        self.table.setHorizontalHeaderLabels(_STATS)
        self.table.setVerticalHeaderLabels(_METRICS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.head)
        lay.addWidget(self.best)
        lay.addWidget(self.table)
        state.datasetChanged.connect(self.refresh)

    def refresh(self) -> None:
        df = self.state.df
        counts = df["Status"].value_counts() if len(df) else {}
        self.head.setText("   ".join(
            f"{k}: {counts.get(k, 0)}"
            for k in ("PENDING", "RUNNING", "DONE", "FAILED", "SKIP")))
        done = df[df["Status"] == "DONE"] if len(df) else pd.DataFrame()
        for r, m in enumerate(_METRICS):
            series = pd.to_numeric(done[m], errors="coerce").dropna() \
                if m in done else pd.Series(dtype=float)
            vals = ([f"{int(series.count())}", f"{series.mean():.4f}",
                     f"{series.std():.4f}", f"{series.min():.4f}",
                     f"{series.max():.4f}"] if len(series)
                    else ["0", "–", "–", "–", "–"])
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(v))
        if len(done) and done["L/D"].notna().any():
            i = pd.to_numeric(done["L/D"], errors="coerce").idxmax()
            b = done.loc[i]
            self.best.setText(
                f'Best L/D = {b["L/D"]:.2f}  →  {b["CaseID"]}   '
                f'({self._input_summary(b)})')
        else:
            self.best.setText("Best L/D: – (no completed cases yet)")

    def _input_summary(self, rec) -> str:
        """A parenthetical of the winning case's inputs, labelled + unit'd from
        template metadata (no hardcoded AOA/Velocity)."""
        parts = []
        for sp in self.state.input_parameters():
            v = rec.get(sp.display_name)
            if v is None:
                continue
            unit = f" {sp.unit}" if sp.unit else ""
            parts.append(f"{sp.display_name} {float(v):g}{unit}")
        return ", ".join(parts)
