"""Project dashboard — the at-a-glance answer to "how is my study doing?".

Dashboard Revolution (v2.2, Milestone 2): the dashboard is rebuilt as a
professional engineering screen. A Hero header pins the project identity
(project, template, status, mock/real badge, solver, quick actions); a
responsive KPI row (status counts + success rate + elapsed time) sits above a
rich Study Overview / Execution Pipeline pair; the results chart becomes the
centerpiece; a premium activity feed and a Quick Actions panel replace the
flat list and toolbar dependence; and the Study Summary closes the page.

The public surface is **unchanged** — every existing caller and test keeps
working exactly as before: ``title``, ``subtitle``, ``cards``, ``progress``,
``pipeline``, ``pipe_lbl``, ``chart``, ``recent``, ``study_overview``,
``study_summary``, ``run_btn``, ``refresh()``, ``handle_event()``,
``push_recent()``, ``set_study_summary()``, ``runAllRequested``,
``openProjectRequested``. The preserved attributes continue to point at the
*same widget objects* — new presentation shells wrap them rather than replace
them. Purely presentational: no backend, no business logic.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                               QProgressBar, QPushButton, QScrollArea,
                               QSizePolicy, QStackedLayout, QVBoxLayout,
                               QWidget)

from cfdauto.events import Event
from cfdauto.study_analytics import StudySummary
from gui import theme
from gui.panels.charts_panel import series_groups
from gui.state import AppState
from gui.widgets import (ActivityFeed, EmptyState, HeroHeader, KpiCard,
                         PipelineWidget, QuickActionsPanel, StudyOverviewTable,
                         StudySummaryPanel)


# The dashboard's flow layout now lives in gui.widgets.flow_layout (Stage 6)
# so the Queue's filter pills and the Charts toolbar share the same wrapping
# layout. `_FlowLayout` remains importable from here for backward compatibility.
from gui.widgets.flow_layout import FlowLayout as _FlowLayout


def _section(title: str, caption: str = ""):
    """A titled dashboard section card; returns (frame, body_layout)."""
    frame = QFrame()
    frame.setProperty("dashSection", True)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                           theme.CARD_MARGIN, theme.CARD_MARGIN)
    lay.setSpacing(theme.SPACE_MD)
    t = QLabel(title)
    t.setProperty("dashSectionTitle", True)
    lay.addWidget(t)
    if caption:
        cap = QLabel(caption)
        cap.setProperty("dashSectionHint", True)
        lay.addWidget(cap)
    return frame, lay


class DashboardPanel(QWidget):
    runAllRequested = Signal()
    openProjectRequested = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._run_started_at: Optional[float] = None

        # -- hero header (pinned above the scroll area) --------------------
        self.hero_header = HeroHeader()
        self.hero_header.runClicked.connect(self.runAllRequested.emit)
        self.hero_header.openProjectClicked.connect(
            self.openProjectRequested.emit)
        self.hero_header.report_btn.setToolTip("Not wired yet — part of the "
                                               "report milestone.")
        # Preserved aliases — the hero owns these widgets now.
        self.title: QLabel = self.hero_header.project_lbl
        self.subtitle: QLabel = self.hero_header.meta_lbl
        self.run_btn: QPushButton = self.hero_header.run_btn

        # -- KPI row --------------------------------------------------------
        self.cards = {
            "PENDING": KpiCard("Pending", theme.STATUS_COLORS["PENDING"],
                               icon="clock"),
            "RUNNING": KpiCard("Running", theme.STATUS_COLORS["RUNNING"],
                               icon="run"),
            "DONE": KpiCard("Done", theme.STATUS_COLORS["DONE"], icon="check"),
            "FAILED": KpiCard("Failed", theme.STATUS_COLORS["FAILED"],
                              icon="alert"),
        }
        self.rate_card = KpiCard("Success Rate", theme.SUCCESS, icon="results")
        self.time_card = KpiCard("Elapsed Time", theme.INFO, icon="clock")
        kpi_flow = _FlowLayout(spacing=theme.SPACE_MD)
        for card in [self.cards["PENDING"], self.cards["RUNNING"],
                     self.cards["DONE"], self.cards["FAILED"],
                     self.rate_card, self.time_card]:
            card.setMinimumWidth(160)
            kpi_flow.addWidget(card)
        kpi_row = QWidget()
        kpi_row.setLayout(kpi_flow)

        # -- pipeline (full width, non-compact — more breathing room) ------
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.pipeline = PipelineWidget(compact=False)
        self.pipe_lbl = QLabel("Pipeline idle")
        self.pipe_lbl.setProperty("hint", True)
        pipeline_frame, pipeline_lay = _section(
            "Execution Pipeline",
            caption=f"Strategy: {state.context.template.execution_strategy_id or '—'}")
        pipeline_lay.addWidget(self.pipe_lbl)
        pipeline_lay.addWidget(self.progress)
        pipeline_lay.addWidget(self.pipeline)
        pipeline_frame.setMinimumWidth(360)

        # -- study overview (computed from AppState.df; already a card) -----
        self.study_overview = StudyOverviewTable(state)
        self.study_overview.setMinimumWidth(400)

        # -- chart (the visual centrepiece of the page) ----------------------
        self.chart = pg.PlotWidget()
        self.chart.showGrid(x=True, y=True, alpha=0.25)
        self.chart.addLegend(offset=(-10, 10))
        self.chart.setLabel("left", "L/D")
        self.chart.setMinimumHeight(theme.CHART_MIN_HEIGHT)
        self.chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apply_chart_axes()
        chart_frame, chart_lay = _section("Results Chart",
                                          caption="Live from the dataset — "
                                                  "updated on every event")
        chart_lay.addWidget(self.chart, 1)

        # -- recent activity (rich feed) -------------------------------------
        self.activity_feed = ActivityFeed()
        self.recent: QListWidget = self.activity_feed.list
        activity_frame, activity_lay = _section("Recent Activity")
        activity_lay.addWidget(self.activity_feed, 1)
        activity_frame.setMinimumWidth(340)

        # -- quick actions (reduce toolbar dependence) -----------------------
        self.quick_actions = QuickActionsPanel()
        self.quick_actions.actionTriggered.connect(self._quick_action)
        self.quick_actions.setMinimumWidth(300)

        # -- study summary (Orchestrator.current_study_summary; unchanged) --
        self.study_summary = StudySummaryPanel()
        summary_frame, summary_lay = _section("Study Summary",
                                              caption="Engine analytics from "
                                                      "the last batch")
        summary_lay.addWidget(self.study_summary)

        # -- assemble content (everything scrolls) ---------------------------
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(theme.SPACE_LG)

        body_lay.addWidget(kpi_row)

        # v2.2 Workspace Revolution: the results chart is the visual anchor —
        # it sits directly under the KPI row, above the overview/pipeline pair.
        body_lay.addWidget(chart_frame, 1)

        pair1 = _FlowLayout(spacing=theme.SPACE_MD)
        pair1.addWidget(self.study_overview)
        pair1.addWidget(pipeline_frame)
        pair1_w = QWidget(); pair1_w.setLayout(pair1)
        body_lay.addWidget(pair1_w)

        pair2 = _FlowLayout(spacing=theme.SPACE_MD)
        pair2.addWidget(activity_frame)
        pair2.addWidget(self.quick_actions)
        pair2_w = QWidget(); pair2_w.setLayout(pair2)
        body_lay.addWidget(pair2_w)

        body_lay.addWidget(summary_frame)

        # -- empty state (no project loaded) ----------------------------------
        self._empty = EmptyState(
            "No Project Loaded",
            "Open or create a project to begin.\nThe dashboard fills in as "
            "cases complete.",
            action_text="Open Project…")
        self._empty.actionClicked.connect(self.openProjectRequested.emit)

        self._stack = QStackedLayout()
        self._stack.addWidget(self._empty)          # index 0
        self._stack.addWidget(body)                 # index 1

        stack_host = QWidget()
        stack_host.setLayout(self._stack)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(stack_host)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                                 theme.SPACE_LG, theme.SPACE_MD)
        outer.setSpacing(theme.SPACE_MD)
        outer.addWidget(self.hero_header)
        outer.addWidget(scroll, 1)

        state.datasetChanged.connect(self.refresh)
        state.projectLoaded.connect(self._project_loaded)
        state.runStateChanged.connect(
            lambda r: self.run_btn.setEnabled(not r))

    # ------------------------------------------------------------------ #
    def _quick_action(self, aid: str) -> None:
        """Route a Quick Actions panel button to the matching signal."""
        if aid == "open":
            self.openProjectRequested.emit()
        elif aid in ("run", "resume"):
            self.runAllRequested.emit()
        # report / export / validate / config are placeholders — their
        # milestones arrive in later iterations.

    def _project_loaded(self) -> None:
        st = self.state
        tpl = st.context.template
        name = st.config_path.stem
        self.hero_header.set_project(name, tpl.name, tpl.description)
        self.hero_header.set_mock(st.effective_mock)
        self.hero_header.set_solver(tpl.default_solver)
        self.hero_header.set_status(st.running, None)
        self._stack.setCurrentIndex(1)
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

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        df = self.state.df
        counts = df["Status"].value_counts() if len(df) else {}
        for key, card in self.cards.items():
            card.set_value(str(int(counts.get(key, 0))))
        total = len(df)
        done = int(counts.get("DONE", 0))
        self.progress.setValue(int(100 * done / total) if total else 0)
        self.progress.setFormat(f"{done}/{total} completed  (%p%)")
        # bonus KPIs
        self.rate_card.set_value(f"{100.0 * done / total:.0f}%" if total else "–")
        if self._run_started_at is not None:
            secs = max(0, int(time.time() - self._run_started_at))
            self.time_card.set_value(f"{secs // 60}m {secs % 60:02d}s")
        else:
            self.time_card.set_value("–")
        # hero status line
        self.hero_header.set_status(self.state.running,
                                    int(100 * done / total) if total else None)
        self._redraw_chart()

    def _redraw_chart(self) -> None:
        for item in list(self.chart.listDataItems()):
            self.chart.removeItem(item)
        df = self.state.df
        if not len(df) or "Status" not in df.columns:
            return                       # nothing to plot yet (empty state)
        px, sx, _ = self._axis_inputs()
        for i, (label, xs, ys, _ids) in enumerate(
                series_groups(df, px, "L/D", sx)):
            col = theme.CHART_SERIES[i % len(theme.CHART_SERIES)]
            self.chart.plot(xs, ys, pen=pg.mkPen(col, width=1.6), symbol="o",
                            symbolSize=6, symbolBrush=col, symbolPen=None,
                            name=label)

    # -- live event feed ---------------------------------------------------
    def handle_event(self, evt: Event) -> None:
        t, d = evt.type, evt.data
        if t == "case.started":
            if self._run_started_at is None:
                self._run_started_at = time.time()
            self.pipeline.reset()
            self.pipe_lbl.setText(
                f'Running {d["case_id"]}  (case {d["index"]}/{d["total"]})')
            self.push_recent(f'{d["case_id"]} started', kind="started")
        elif t == "stage":
            self.pipeline.set_stage(d["stage"], d["state"])
        elif t == "case.done":
            r = d.get("result", {})
            self.push_recent(
                f'{d["case_id"]}  CL={_g(r.get("cl"))} '
                f'CD={_g(r.get("cd"))}', kind="done")
        elif t == "case.failed":
            self.push_recent(f'{d["case_id"]}  {d.get("error", "")[:60]}',
                             kind="failed")
        elif t == "batch.finished":
            self.pipe_lbl.setText("Pipeline idle")
            self.push_recent(
                f'Batch finished — {d.get("ok", 0)} ok, '
                f'{d.get("failed", 0)} failed', kind="info")

    def push_recent(self, text: str, kind: str = "info") -> None:
        """Prepend one activity-feed line. The timestamp is generated here,
        at display time, purely for presentation — no backend logging is
        touched or read."""
        self.activity_feed.push(text, kind=kind)

    # -- Study Summary -------------------------------------------
    def set_study_summary(self, summary: Optional[StudySummary]) -> None:
        """Passthrough to the read-only Study Summary widget — connected to
        EngineWorker.studySummaryReady in main_window.py. Never recomputes
        anything; just forwards whatever the engine already computed."""
        self.study_summary.set_summary(summary)


def _g(v) -> str:
    return "–" if v is None else f"{v:.4f}"
