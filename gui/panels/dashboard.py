"""Project dashboard — the at-a-glance answer to "how is my study doing?".

GUI Modernization (v1.0.0-rc2): redesigned into clearly separated,
generously spaced sections (status cards → pipeline → chart → activity/
overview → study summary), each in its own card, scrolling as a whole
rather than compressing at smaller window sizes. The public surface
(``cards``, ``progress``, ``pipeline``, ``pipe_lbl``, ``chart``,
``recent``, ``study_summary``, ``refresh()``, ``handle_event()``,
``push_recent()``, ``set_study_summary()``) is unchanged — every existing
caller and test keeps working exactly as before.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                               QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from cfdauto.events import Event
from cfdauto.study_analytics import StudySummary
from gui import theme
from gui.panels.charts_panel import series_groups
from gui.state import AppState
from gui.widgets import (PipelineWidget, SectionHeader, StatCard,
                         StudyOverviewTable, StudySummaryPanel)


def _card(inner: QWidget) -> QFrame:
    """A section container: card background, standard radius/margin."""
    frame = QFrame()
    frame.setProperty("card", True)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                           theme.CARD_MARGIN, theme.CARD_MARGIN)
    lay.setSpacing(theme.SPACE_SM)
    lay.addWidget(inner)
    return frame


class DashboardPanel(QWidget):
    runAllRequested = Signal()
    openProjectRequested = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        # -- header (pinned above the scroll area) -------------------------
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
        head.setSpacing(theme.SPACE_SM)
        hv = QVBoxLayout(); hv.addWidget(self.title); hv.addWidget(self.subtitle)
        head.addLayout(hv, 1)
        head.addWidget(open_btn)
        head.addWidget(self.run_btn)

        # -- status cards ---------------------------------------------------
        self.cards = {
            "PENDING": StatCard("Pending", theme.STATUS_COLORS["PENDING"]),
            "RUNNING": StatCard("Running", theme.STATUS_COLORS["RUNNING"]),
            "DONE": StatCard("Done", theme.STATUS_COLORS["DONE"]),
            "FAILED": StatCard("Failed", theme.STATUS_COLORS["FAILED"]),
        }
        cards_row = QHBoxLayout()
        cards_row.setSpacing(theme.SPACE_MD)
        for c in self.cards.values():
            cards_row.addWidget(c)
        cards_widget = QWidget(); cards_widget.setLayout(cards_row)

        # -- pipeline (full width, non-compact — more breathing room) ------
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        self.pipeline = PipelineWidget(compact=False)
        self.pipe_lbl = QLabel("Pipeline idle")
        self.pipe_lbl.setProperty("hint", True)
        pipeline_body = QWidget()
        pv = QVBoxLayout(pipeline_body)
        pv.setContentsMargins(0, 0, 0, 0)
        pv.setSpacing(theme.SPACE_SM)
        pv.addWidget(self.pipe_lbl)
        pv.addWidget(self.progress)
        pv.addWidget(self.pipeline)
        pipeline_section = QVBoxLayout()
        pipeline_section.setSpacing(theme.SPACE_SM)
        pipeline_section.addWidget(SectionHeader("Pipeline", icon="⚙"))
        pipeline_section.addWidget(pipeline_body)
        pipeline_widget = QWidget(); pipeline_widget.setLayout(pipeline_section)

        # -- chart (the largest section on the page) ------------------------
        # Axes are labelled from the active study's input metadata — no
        # hardcoded AOA/Velocity — so the dashboard chart reads correctly for
        # any template (identical to before for External Aerodynamics).
        self.chart = pg.PlotWidget()
        self.chart.showGrid(x=True, y=True, alpha=0.25)
        self.chart.addLegend(offset=(-10, 10))
        self.chart.setLabel("left", "L/D")
        self._apply_chart_axes()
        self.chart.setMinimumHeight(360)
        self.chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        chart_section = QVBoxLayout()
        chart_section.setSpacing(theme.SPACE_SM)
        chart_section.addWidget(SectionHeader("Results Chart", icon="📈"))
        chart_section.addWidget(self.chart, 1)
        chart_widget = QWidget(); chart_widget.setLayout(chart_section)

        # -- recent activity --------------------------------------------------
        self.recent = QListWidget()
        self.recent.setAlternatingRowColors(True)
        self.recent.setMinimumHeight(160)
        activity_section = QVBoxLayout()
        activity_section.setSpacing(theme.SPACE_SM)
        activity_section.addWidget(SectionHeader("Recent Activity", icon="🕘"))
        activity_section.addWidget(self.recent, 1)
        activity_widget = QWidget(); activity_widget.setLayout(activity_section)

        # -- study overview (Option A: computed from AppState.df) -----------
        self.study_overview = StudyOverviewTable(state)

        activity_row = QHBoxLayout()
        activity_row.setSpacing(theme.SPACE_MD)
        activity_row.addWidget(_card(activity_widget), 2)
        activity_row.addWidget(self.study_overview, 3)
        activity_row_widget = QWidget(); activity_row_widget.setLayout(activity_row)

        # -- study summary (Orchestrator.current_study_summary; unchanged) --
        self.study_summary = StudySummaryPanel()

        # -- assemble: header pinned, everything else scrolls --------------
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(theme.SPACE_LG)
        body_lay.addWidget(_card(cards_widget))
        body_lay.addWidget(_card(pipeline_widget))
        body_lay.addWidget(_card(chart_widget), 1)
        body_lay.addWidget(activity_row_widget)
        body_lay.addWidget(_card(self.study_summary))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                                 theme.SPACE_LG, theme.SPACE_MD)
        outer.setSpacing(theme.SPACE_MD)
        outer.addLayout(head)
        outer.addWidget(scroll, 1)

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
        self._apply_chart_axes()
        self.refresh()

    def _axis_inputs(self):
        """(primary, secondary) study-input display labels for the chart, from
        template metadata (defaults to sensible strings if none declared)."""
        prim = self.state.primary_input()
        sec = self.state.secondary_input()
        px = prim.display_name if prim is not None else "X"
        sx = sec.display_name if sec is not None else px
        unit = f" [{prim.unit}]" if prim is not None and prim.unit else ""
        return px, sx, f"{px}{unit}"

    def _apply_chart_axes(self) -> None:
        px, sx, px_label = self._axis_inputs()
        self.chart.setTitle(f"L/D vs {px} (by {sx})")
        self.chart.setLabel("bottom", px_label)

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
        px, sx, _ = self._axis_inputs()
        for i, (label, xs, ys, _ids) in enumerate(
                series_groups(self.state.df, px, "L/D", sx)):
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
        """Prepend one activity-feed line. The timestamp is generated here,
        at display time, purely for presentation — no backend logging is
        touched or read."""
        stamped = f"{datetime.now().strftime('%H:%M:%S')}   {text}"
        self.recent.insertItem(0, stamped)
        while self.recent.count() > 8:
            self.recent.takeItem(self.recent.count() - 1)

    # -- Study Summary -------------------------------------------
    def set_study_summary(self, summary: Optional[StudySummary]) -> None:
        """Passthrough to the read-only Study Summary widget — connected to
        EngineWorker.studySummaryReady in main_window.py. Never recomputes
        anything; just forwards whatever the engine already computed."""
        self.study_summary.set_summary(summary)


def _g(v) -> str:
    return "–" if v is None else f"{v:.4f}"
