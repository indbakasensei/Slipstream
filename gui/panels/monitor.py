"""Run monitor — what the terminal never showed you (v0.9 M2 upgrade).

Header + pipeline strip + weighted progress bar remain. The plot area is now
a **tabbed** widget:

* **Forces** — CL and CD per *iteration* (was per chunk pre-M2). Fed by
  ``fluent.iteration`` events from the new telemetry tap; falls back to the
  coarser ``solve.progress`` events on old engines.
* **Residuals** — continuity + momentum + turbulence residuals on a log-y
  axis. Only visible when the engine reports residuals (mock + real Fluent).

Data volume is bounded — the underlying arrays keep every point for the
current case, but only the visible curves are redrawn each frame, so tens of
thousands of iterations are cheap.
"""

from __future__ import annotations

from typing import Dict, List

import pyqtgraph as pg
from PySide6.QtWidgets import (QFrame, QLabel, QProgressBar, QScrollArea,
                               QTabWidget, QVBoxLayout, QWidget)

from cfdauto.events import Event
from cfdauto.platform import get_default_template
from gui import theme
from gui.widgets import PipelineWidget

_PRESTAGE_PCT = {"mesh": 12, "fluent_launch": 20, "setup": 23,
                 "initialize": 25}
# Residual channels + their colours (matched to theme.CHART_SERIES).
_RES_CHANNELS = [
    ("continuity", "#4f8cff"),
    ("x_velocity", "#3fbf7f"),
    ("y_velocity", "#e8a33d"),
    ("z_velocity", "#e5534b"),
    ("k",          "#b07fe8"),
    ("omega",      "#2fb3a8"),
]


class MonitorPanel(QWidget):
    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        # Phase 2: the force-plot legend labels come from the template's
        # metric metadata rather than duplicated literals. ``context`` is a
        # SimulationContext when the main window supplies one; a bare
        # MonitorPanel() (e.g. in tests) falls back to the registry default.
        template = context.template if context is not None else get_default_template()
        cl_metric = template.metric("cl")
        cd_metric = template.metric("cd")
        cl_name = cl_metric.display_name if cl_metric else "CL"
        cd_name = cd_metric.display_name if cd_metric else "CD"

        self.case_lbl = QLabel("No case running")
        self.case_lbl.setProperty("h1", True)
        self.info_lbl = QLabel("")
        self.info_lbl.setProperty("hint", True)

        self.pipeline = PipelineWidget()
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)

        # --- Forces plot (CL/CD per iteration) --------------------------- #
        self.forces = pg.PlotWidget(title="Force-coefficient convergence")
        self.forces.showGrid(x=True, y=True, alpha=0.25)
        self.forces.setLabel("bottom", "iteration")
        self.forces.addLegend(offset=(-10, 10))
        self.cl_curve = self.forces.plot(
            [], [], pen=pg.mkPen(theme.ACCENT, width=2), name=cl_name)
        self.cd_curve = self.forces.plot(
            [], [], pen=pg.mkPen("#e8a33d", width=2), name=cd_name)

        # --- Residuals plot (log-y) -------------------------------------- #
        self.residuals = pg.PlotWidget(title="Scaled residuals")
        self.residuals.showGrid(x=True, y=True, alpha=0.25)
        self.residuals.setLabel("bottom", "iteration")
        self.residuals.setLogMode(x=False, y=True)
        self.residuals.addLegend(offset=(-10, 10))
        self._res_curves: Dict[str, pg.PlotDataItem] = {}
        self._res_data: Dict[str, List[float]] = {}
        self._res_its: Dict[str, List[int]] = {}
        for name, colour in _RES_CHANNELS:
            self._res_curves[name] = self.residuals.plot(
                [], [], pen=pg.mkPen(colour, width=1.6), name=name)
            self._res_data[name] = []
            self._res_its[name] = []
        self._residuals_seen = False

        tabs = QTabWidget()
        tabs.addTab(self.forces, "Forces")
        tabs.addTab(self.residuals, "Residuals")
        self._tabs = tabs

        self._its: List[int] = []
        self._cl: List[float] = []
        self._cd: List[float] = []

        # -- Layout (Capability 3 UI foundation) -------------------------- #
        # Presentation-only restructure to prepare for the Neo redesign: clear
        # header hierarchy (title over details, not cramped side-by-side), a
        # labelled/aligned progress block, plots with a minimum height, and the
        # whole panel inside a scroll area so a short dock scrolls instead of
        # clipping. No monitoring logic changed.
        self.case_lbl.setWordWrap(True)
        self.info_lbl.setWordWrap(True)
        header = QVBoxLayout()
        header.setSpacing(theme.SPACE_XS)
        header.addWidget(self.case_lbl)
        header.addWidget(self.info_lbl)

        prog_title = QLabel("Solver Pipeline")
        prog_title.setProperty("h2", True)
        self.bar.setMinimumHeight(theme.MIN_CONTROL_HEIGHT)
        prog = QVBoxLayout()
        prog.setSpacing(theme.SPACE_SM)
        prog.addWidget(prog_title)
        prog.addWidget(self.pipeline)
        prog.addWidget(self.bar)

        self._tabs.setMinimumHeight(theme.MIN_PLOT_HEIGHT)

        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                              theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        cv.setSpacing(theme.SECTION_SPACING)
        cv.addLayout(header)
        cv.addLayout(prog)
        cv.addWidget(self._tabs, 1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)
        self.setMinimumWidth(theme.MIN_PANEL_WIDTH)

    # ------------------------------------------------------------------ #
    def handle_event(self, evt: Event) -> None:
        t, d = evt.type, evt.data
        if t == "case.started":
            self._reset_case(d)
        elif t == "stage":
            self.pipeline.set_stage(d["stage"], d["state"])
            pct = _PRESTAGE_PCT.get(d["stage"])
            if pct and d["state"] in ("done", "cached", "skip"):
                self.bar.setValue(max(self.bar.value(), pct))
        elif t == "fluent.iteration":
            self._append_iteration(d)
        elif t == "solve.progress":
            # Fallback for pre-M2 engines / older event streams. Never
            # duplicates points that already came in via fluent.iteration.
            if not self._its or d["it"] > self._its[-1]:
                self._append_iteration(d)
        elif t in ("solve.converged", "solve.maxiter"):
            self.bar.setValue(95)
        elif t == "case.done":
            self.pipeline.set_stage("extract", "done")
            self.bar.setValue(100)
        elif t == "case.failed":
            self.pipeline.mark_active_failed()
            self.info_lbl.setText(f'FAILED: {d.get("error", "")[:120]}')

    # ------------------------------------------------------------------ #
    def _append_iteration(self, d: dict) -> None:
        it = int(d["it"])
        cl = float(d["cl"])
        cd = float(d["cd"])
        self._its.append(it)
        self._cl.append(cl)
        self._cd.append(cd)
        self.cl_curve.setData(self._its, self._cl)
        self.cd_curve.setData(self._its, self._cd)

        residuals = d.get("residuals")
        if residuals:
            self._residuals_seen = True
            for name, _colour in _RES_CHANNELS:
                v = residuals.get(name)
                if v is None or v <= 0:
                    continue
                self._res_its[name].append(it)
                self._res_data[name].append(v)
                self._res_curves[name].setData(
                    self._res_its[name], self._res_data[name])

        max_it = int(d.get("max_it") or 1)
        frac = it / max(1, max_it)
        self.bar.setValue(int(25 + 70 * min(1.0, frac)))
        self.info_lbl.setText(
            f"iter {it}   CL={cl:.4f}   CD={cd:.5f}"
            + ("   [residuals live]" if residuals else ""))

    def _reset_case(self, d: dict) -> None:
        extra = "  ".join(f"{k}={v:g}" for k, v in d.get("extra", {}).items())
        self.case_lbl.setText(
            f'Case {d["index"]}/{d["total"]} — {d["case_id"]}')
        # The live case readout mirrors the engine's case.started payload
        # (still the aero aoa/velocity schema — a runtime concern out of this
        # sprint's scope). Read defensively so a future generic payload can't
        # crash the panel.
        bits = []
        if d.get("aoa") is not None:
            bits.append(f'AOA {d["aoa"]:g}°')
        if d.get("velocity") is not None:
            bits.append(f'V {d["velocity"]:g} m/s')
        if extra:
            bits.append(extra)
        self.info_lbl.setText("   ".join(bits))
        self.pipeline.reset()
        self.bar.setValue(0)
        self._its.clear(); self._cl.clear(); self._cd.clear()
        self.cl_curve.setData([], [])
        self.cd_curve.setData([], [])
        for name, _c in _RES_CHANNELS:
            self._res_data[name].clear()
            self._res_its[name].clear()
            self._res_curves[name].setData([], [])
        self._residuals_seen = False
