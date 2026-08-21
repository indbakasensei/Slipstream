"""Statistical summary of the completed dataset (v0.8 scope: descriptive
stats + status counts + headline best case). Deeper analytics arrive in v2.0
per the blueprint; this panel already reads the same DataFrame they will.

Phase 8F QA: metric columns are now derived from the active template
(template.output_columns()) instead of hardcoded External Aero names.
The best-case headline uses the template's "best-ratio" highlight when
available, falling back to the first available metric.
"""

from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import (QHeaderView, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from gui.state import AppState

_STATS = ["count", "mean", "std", "min", "max"]


class StatsPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.head = QLabel("")
        self.head.setProperty("h2", True)
        self.best = QLabel("")
        self.table = QTableWidget(0, len(_STATS))
        self.table.setHorizontalHeaderLabels(_STATS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self.head)
        lay.addWidget(self.best)
        lay.addWidget(self.table)
        state.datasetChanged.connect(self.refresh)

    def _metric_columns(self) -> list:
        """Return the template-specific metric column names present in the
        DataFrame, plus the universal bookkeeping column "Iterations".
        """
        cols = self.state.template_metrics()
        df_cols = set(self.state.df.columns) if len(self.state.df) else set()
        return [c for c in cols if c in df_cols] + ["Iterations"]

    def refresh(self) -> None:
        df = self.state.df
        counts = df["Status"].value_counts() if len(df) else {}
        self.head.setText("   ".join(
            f"{k}: {counts.get(k, 0)}"
            for k in ("PENDING", "RUNNING", "DONE", "FAILED", "SKIP")))
        done = df[df["Status"] == "DONE"] if len(df) else pd.DataFrame()
        metrics = self._metric_columns()
        # Rebuild the table rows to match the current template's metrics.
        self.table.setRowCount(len(metrics))
        self.table.setVerticalHeaderLabels(metrics)
        for r, m in enumerate(metrics):
            series = pd.to_numeric(done[m], errors="coerce").dropna() \
                if m in done else pd.Series(dtype=float)
            vals = ([f"{int(series.count())}", f"{series.mean():.4f}",
                     f"{series.std():.4f}", f"{series.min():.4f}",
                     f"{series.max():.4f}"] if len(series)
                    else ["0", "–", "–", "–", "–"])
            for c, v in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(v))
        # Best-case headline: prefer the template's "best-ratio" highlight
        # (L/D for External Aero, Pressure Drop for Internal Flow); fall
        # back to the first available metric column.
        summary = self.state.study_summary
        if summary is not None and summary.highlights:
            hl = None
            for h in summary.highlights.values():
                if h.role == "best-ratio":
                    hl = h
                    break
            if hl is None:
                hl = next(iter(summary.highlights.values()), None)
            if hl is not None:
                unit_sfx = f" {hl.unit}" if hl.unit else ""
                self.best.setText(
                    f'Best {hl.display_name} = {hl.value:.2f}{unit_sfx}  →  '
                    f'row {hl.row}   ({self._input_summary_row(hl.row, done)})')
                return
        # Fallback: first metric column's max value.
        if len(done) and metrics:
            first = metrics[0]
            if first in done and done[first].notna().any():
                i = pd.to_numeric(done[first], errors="coerce").idxmax()
                b = done.loc[i]
                self.best.setText(
                    f'Best {first} = {b[first]:.2f}  →  {b["CaseID"]}   '
                    f'({self._input_summary(b)})')
            else:
                self.best.setText(f"Best {first}: – (no completed cases yet)")
        else:
            self.best.setText("Best: – (no completed cases yet)")

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

    def _input_summary_row(self, row: int, df) -> str:
        """Input summary for a specific row number from the DataFrame."""
        rec = df[df["Row"] == row]
        if rec.empty:
            return f"row {row}"
        return self._input_summary(rec.iloc[0])
