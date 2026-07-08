"""Project dashboard — the at-a-glance answer to "how is my study doing?".

Status cards, overall progress, the pipeline strip mirroring the active case,
a headline L/D-vs-AOA chart, and a recent-events feed. All rendered from the
same AppState/dataset every other panel uses."""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QListWidget,
                               QProgressBar, QPushButton, QVBoxLayout,
                               QWidget)

from cfdauto.events import Event
from gui import theme
from gui.panels.charts_panel import series_groups
from gui.state import AppState
from gui.widgets import PipelineWidget, StatCard


class DashboardPanel(QWidget):
    runAllRequested = Signal()
    openProjectRequested = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        self.title = QLabel("No project loaded")
        self.title.setProperty("h1", True)
        self.subtitle = QLabel("File ▸ Open Project…  to load a config.yaml")
        self.subtitle.setProperty("hint", True)

        open_btn = QPushButton("Open Project…")
        open_btn.clicked.connect(self.openProjectRequested.emit)
        self.run_btn = QPushButton("▶ Run All")
        self.run_btn.setProperty("accent", True)
        self.run_btn.clicked.connect(self.runAllRequested.emit)
        head = QHBoxLayout()
        hv = QVBoxLayout(); hv.addWidget(self.title); hv.addWidget(self.subtitle)
        head.addLayout(hv, 1)
        head.addWidget(open_btn)
        head.addWidget(self.run_btn)

        self.cards = {
            "PENDING": StatCard("Pending", theme.STATUS_COLORS["PENDING"]),
            "RUNNING": StatCard("Running", theme.STATUS_COLORS["RUNNING"]),
            "DONE": StatCard("Done", theme.STATUS_COLORS["DONE"]),
            "FAILED": StatCard("Failed", theme.STATUS_COLORS["FAILED"]),
        }
        cards = QHBoxLayout()
        for c in self.cards.values():
            cards.addWidget(c)

        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.pipeline = PipelineWidget(compact=True)
        self.pipe_lbl = QLabel("Pipeline idle")
        self.pipe_lbl.setProperty("hint", True)

        self.chart = pg.PlotWidget(title="L/D vs AOA (by velocity)")
        self.chart.showGrid(x=True, y=True, alpha=0.25)
        self.chart.addLegend(offset=(-10, 10))
        self.chart.setLabel("bottom", "AOA [deg]")
        self.chart.setLabel("left", "L/D")

        self.recent = QListWidget()
        self.recent.setMaximumHeight(120)

        grid = QGridLayout(self)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setVerticalSpacing(10)
        grid.addLayout(head, 0, 0, 1, 2)
        grid.addLayout(cards, 1, 0, 1, 2)
        grid.addWidget(self.progress, 2, 0, 1, 2)
        grid.addWidget(self.pipe_lbl, 3, 0, 1, 2)
        grid.addWidget(self.pipeline, 4, 0, 1, 2)
        grid.addWidget(self.chart, 5, 0)
        rv = QVBoxLayout()
        lbl = QLabel("Recent events"); lbl.setProperty("h2", True)
        rv.addWidget(lbl); rv.addWidget(self.recent); rv.addStretch(1)
        grid.addLayout(rv, 5, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setRowStretch(5, 1)

        state.datasetChanged.connect(self.refresh)
        state.projectLoaded.connect(self._project_loaded)
        state.runStateChanged.connect(
            lambda r: self.run_btn.setEnabled(not r))

    # ------------------------------------------------------------------ #
    def _project_loaded(self) -> None:
        st = self.state
        self.title.setText(st.config_path.stem)
        mode = st.cfg.fluent.aoa_method
        self.subtitle.setText(
            f"{st.config_path}   ·   AOA method: {mode}   ·   "
            f"schedule: {st.cfg.excel.file}")
        self.refresh()

    def refresh(self) -> None:
        df = self.state.df
        counts = df["Status"].value_counts() if len(df) else {}
        for key, card in self.cards.items():
            card.set_value(str(int(counts.get(key, 0))))
        total = len(df)
        done = int(counts.get("DONE", 0))
        self.progress.setValue(int(100 * done / total) if total else 0)
        self.progress.setFormat(f"{done}/{total} completed  (%p%)")
        self._redraw_chart()

    def _redraw_chart(self) -> None:
        for item in list(self.chart.listDataItems()):
            self.chart.removeItem(item)
        for i, (label, xs, ys, _ids) in enumerate(
                series_groups(self.state.df, "AOA", "L/D", "Velocity")):
            col = theme.CHART_SERIES[i % len(theme.CHART_SERIES)]
            self.chart.plot(xs, ys, pen=pg.mkPen(col, width=1.6), symbol="o",
                            symbolSize=6, symbolBrush=col, symbolPen=None,
                            name=label)

    # -- live event feed ---------------------------------------------------
    def handle_event(self, evt: Event) -> None:
        t, d = evt.type, evt.data
        if t == "case.started":
            self.pipeline.reset()
            self.pipe_lbl.setText(
                f'Running {d["case_id"]}  (case {d["index"]}/{d["total"]})')
            self.push_recent(f'▶ {d["case_id"]} started')
        elif t == "stage":
            self.pipeline.set_stage(d["stage"], d["state"])
        elif t == "case.done":
            r = d.get("result", {})
            self.push_recent(
                f'✓ {d["case_id"]}  CL={_g(r.get("cl"))} CD={_g(r.get("cd"))}')
        elif t == "case.failed":
            self.push_recent(f'✗ {d["case_id"]}  {d.get("error", "")[:60]}')
        elif t == "batch.finished":
            self.pipe_lbl.setText("Pipeline idle")
            self.push_recent(
                f'Batch finished — {d.get("ok", 0)} ok, {d.get("failed", 0)} failed')

    def push_recent(self, text: str) -> None:
        self.recent.insertItem(0, text)
        while self.recent.count() > 8:
            self.recent.takeItem(self.recent.count() - 1)


def _g(v) -> str:
    return "–" if v is None else f"{v:.4f}"
