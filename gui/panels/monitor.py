"""Run monitor — Neo redesign (UX Milestone 1).

A telemetry-style, information-first live view of the running study. Business
logic is untouched: the panel still renders purely from the engine events
delivered to :meth:`handle_event`, and every public attribute the app/tests
rely on (``bar``, ``pipeline``, ``forces``, ``residuals``, ``cl_curve``,
``cd_curve``, ``_tabs``, ``_scroll``, ``handle_event``, ``_append_iteration``,
``_reset_case``) is preserved. Only the *presentation* changed — from five
heavy cards into the brief's quiet engineering-telemetry flow:

* **Current Run** — case headline, details, progress, solver status,
  estimated time remaining.
* **Pipeline** — Mesh → Workbench → Fluent → Post-processing stage strip.
* **Live Telemetry** — iterations, min residual, and the template's force
  metrics as compact monospace readout cells.
* **Convergence** — the Forces / Residuals plots (tabbed), the dominant
  vertical block.
* **Event History** — a newest-first event feed (mesh generated, solver
  started, convergence, results written, finished).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QListWidget, QProgressBar, QScrollArea,
                               QTabWidget, QVBoxLayout, QWidget)

from cfdauto.events import Event
from cfdauto.platform import get_default_template
from gui import theme
from gui.widgets import PipelineWidget, StatusChip

_PRESTAGE_PCT = {"mesh": 12, "fluent_launch": 20, "setup": 23,
                 "initialize": 25}
# Residual channels + their colours (matched to theme.CHART_SERIES).
_RES_CHANNELS = [
    ("continuity", "#5b8cff"),
    ("x_velocity", "#3fbf7f"),
    ("y_velocity", "#e8a33d"),
    ("z_velocity", "#e5534b"),
    ("k",          "#b07fe8"),
    ("omega",      "#2fb3a8"),
]


def _metric_tile(caption: str) -> tuple:
    """A compact (caption over big value) telemetry cell. Returns (frame, value)."""
    frame = QFrame()
    frame.setProperty("telemetry", True)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM,
                           theme.SPACE_MD, theme.SPACE_SM)
    lay.setSpacing(2)
    cap = QLabel(caption)
    cap.setProperty("telemetryCaption", True)
    val = QLabel("–")
    val.setProperty("telemetryValue", True)
    lay.addWidget(cap)
    lay.addWidget(val)
    return frame, val


def _block(title: str, accessory=None):
    """A quiet telemetry block: uppercase label + optional right accessory.
    Returns (frame, body_layout)."""
    frame = QFrame()
    frame.setProperty("telemetry", True)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(theme.SPACE_MD, theme.SPACE_SM,
                           theme.SPACE_MD, theme.SPACE_SM)
    lay.setSpacing(theme.SPACE_SM)
    if accessory is not None:
        head = QHBoxLayout()
        t = QLabel(title)
        t.setProperty("caption", True)
        head.addWidget(t)
        head.addStretch(1)
        head.addWidget(accessory)
        lay.addLayout(head)
    else:
        t = QLabel(title)
        t.setProperty("caption", True)
        lay.addWidget(t)
    return frame, lay


class MonitorPanel(QWidget):
    def __init__(self, context=None, parent=None):
        super().__init__(parent)
        template = context.template if context is not None else get_default_template()
        cl_metric = template.metric("cl")
        cd_metric = template.metric("cd")
        cl_name = cl_metric.display_name if cl_metric else "CL"
        cd_name = cd_metric.display_name if cd_metric else "CD"

        # ---- shared/preserved widgets ---------------------------------- #
        self.case_lbl = QLabel("No case running")
        self.case_lbl.setProperty("h1", True)
        self.case_lbl.setWordWrap(True)
        self.info_lbl = QLabel("Waiting for a run to start…")
        self.info_lbl.setProperty("hint", True)
        self.info_lbl.setWordWrap(True)
        self.status_chip = StatusChip("Idle", "idle")
        self.eta_lbl = QLabel("—")
        self.eta_lbl.setProperty("metric", True)

        # Neo (v2.1): a taller pipeline strip reads better in the Monitor than
        # the dashboard default of 46px; the PipelineWidget API is unchanged.
        self.pipeline = PipelineWidget(height=60)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setMinimumHeight(theme.MIN_CONTROL_HEIGHT)

        # ---- Forces plot (CL/CD per iteration) ------------------------- #
        self.forces = pg.PlotWidget(title="Force-coefficient convergence")
        self.forces.showGrid(x=True, y=True, alpha=0.2)
        self.forces.setLabel("bottom", "iteration")
        self.forces.addLegend(offset=(-10, 10))
        self.cl_curve = self.forces.plot(
            [], [], pen=pg.mkPen(theme.ACCENT, width=2), name=cl_name)
        self.cd_curve = self.forces.plot(
            [], [], pen=pg.mkPen(theme.WARNING, width=2), name=cd_name)

        # ---- Residuals plot (log-y) ------------------------------------ #
        self.residuals = pg.PlotWidget(title="Scaled residuals")
        self.residuals.showGrid(x=True, y=True, alpha=0.2)
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

        self._tabs = QTabWidget()
        self._tabs.addTab(self.forces, "Forces")
        self._tabs.addTab(self.residuals, "Residuals")
        self._tabs.setMinimumHeight(theme.MIN_PLOT_HEIGHT)

        self._its: List[int] = []
        self._cl: List[float] = []
        self._cd: List[float] = []
        self._case_start: datetime | None = None
        self._metric_names = (cl_name, cd_name)

        # ================================================================ #
        # WORKSPACE LAYOUT (v2.2)
        # ================================================================ #
        # The brief's flow: CURRENT RUN → PIPELINE → LIVE TELEMETRY →
        # CONVERGENCE → EVENT HISTORY. Quiet telemetry blocks (hairline
        # hairline frames, uppercase captions) instead of heavy cards; the
        # plots own the vertical stretch. Presentation only.

        # -- Current run block ------------------------------------------- #
        run_block, run_lay = _block("Current Run", accessory=self.status_chip)
        run_lay.addWidget(self.case_lbl)
        run_lay.addWidget(self.info_lbl)
        run_lay.addWidget(self.bar)
        prog_row = QHBoxLayout()
        eta_cap = QLabel("Est. remaining")
        eta_cap.setProperty("caption", True)
        prog_row.addWidget(eta_cap)
        prog_row.addWidget(self.eta_lbl)
        prog_row.addStretch(1)
        run_lay.addLayout(prog_row)

        # -- Pipeline block ---------------------------------------------- #
        pipe_block, pipe_lay = _block("Pipeline")
        pipe_lay.addWidget(self.pipeline)

        # -- Live Telemetry block ---------------------------------------- #
        metrics_block, metrics_lay = _block("Live Telemetry")
        grid = QGridLayout()
        grid.setSpacing(theme.SPACE_SM)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self._metric_vals: Dict[str, QLabel] = {}
        tiles = [("iterations", "Iterations"), ("residual", "Min residual"),
                 ("cl", cl_name), ("cd", cd_name)]
        for i, (key, cap) in enumerate(tiles):
            frame, val = _metric_tile(cap)
            self._metric_vals[key] = val
            grid.addWidget(frame, i // 2, i % 2)
        metrics_lay.addLayout(grid)

        # -- Convergence block (plots, dominant) ------------------------- #
        conv_block, conv_lay = _block("Convergence")
        conv_lay.addWidget(self._tabs, 1)

        # -- Event History block ----------------------------------------- #
        hist_block, hist_lay = _block("Event History")
        self.timeline = QListWidget()
        self.timeline.setMinimumHeight(128)
        self.timeline.setFrameShape(QFrame.NoFrame)
        hist_lay.addWidget(self.timeline, 1)

        # ---- assemble (scrollable so nothing clips in a short dock) ---- #
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                              theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        cv.setSpacing(theme.SPACE_SM)
        cv.addWidget(run_block)
        cv.addWidget(pipe_block)
        cv.addWidget(metrics_block)
        cv.addWidget(conv_block, 1)
        cv.addWidget(hist_block)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)
        self.setMinimumWidth(theme.MIN_PANEL_WIDTH)

    # ------------------------------------------------------------------ #
    # Event handling (unchanged logic; presentation-only additions)
    # ------------------------------------------------------------------ #
    def handle_event(self, evt: Event) -> None:
        t, d = evt.type, evt.data
        if t == "case.started":
            self._reset_case(d)
            self.status_chip.set_state("Running", "RUNNING")
            self._timeline(f'▶ Case started — {d.get("case_id", "")}')
        elif t == "stage":
            self.pipeline.set_stage(d["stage"], d["state"])
            pct = _PRESTAGE_PCT.get(d["stage"])
            if pct and d["state"] in ("done", "cached", "skip"):
                self.bar.setValue(max(self.bar.value(), pct))
            if d["stage"] == "mesh" and d["state"] in ("done", "cached"):
                self._timeline("◆ Mesh generated")
            elif d["stage"] == "fluent_launch" and d["state"] == "done":
                self._timeline("◆ Solver started")
        elif t == "fluent.iteration":
            self._append_iteration(d)
        elif t == "solve.progress":
            if not self._its or d["it"] > self._its[-1]:
                self._append_iteration(d)
        elif t in ("solve.converged", "solve.maxiter"):
            self.bar.setValue(95)
            self.status_chip.set_state(
                "Converged" if t == "solve.converged" else "Max iter",
                "DONE" if t == "solve.converged" else theme.WARNING)
            self._timeline("◆ Convergence reached" if t == "solve.converged"
                           else "◆ Max iterations reached")
        elif t == "case.done":
            self.pipeline.set_stage("extract", "done")
            self.bar.setValue(100)
            self.eta_lbl.setText("done")
            self.status_chip.set_state("Done", "DONE")
            self._timeline("✓ Results written")
        elif t == "case.failed":
            self.pipeline.mark_active_failed()
            self.status_chip.set_state("Failed", "FAILED")
            self.info_lbl.setText(f'FAILED: {d.get("error", "")[:120]}')
            self._timeline(f'✗ Case failed — {d.get("error", "")[:60]}')
        elif t == "batch.finished":
            self.status_chip.set_state("Idle", "idle")
            self.eta_lbl.setText("—")
            self._timeline("■ Batch finished")

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
        min_res = None
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
                min_res = v if min_res is None else min(min_res, v)

        max_it = int(d.get("max_it") or 1)
        frac = it / max(1, max_it)
        self.bar.setValue(int(25 + 70 * min(1.0, frac)))
        self.info_lbl.setText(
            f"iter {it}   {self._metric_names[0]}={cl:.4f}   "
            f"{self._metric_names[1]}={cd:.5f}"
            + ("   [residuals live]" if residuals else ""))

        # -- live-metric tiles + ETA (presentation math only) ------------ #
        self._metric_vals["iterations"].setText(str(it))
        self._metric_vals["cl"].setText(f"{cl:.4f}")
        self._metric_vals["cd"].setText(f"{cd:.5f}")
        if min_res is not None:
            self._metric_vals["residual"].setText(f"{min_res:.1e}")
        self._update_eta(frac)

    def _update_eta(self, frac: float) -> None:
        if self._case_start is None or frac <= 0:
            return
        elapsed = (datetime.now() - self._case_start).total_seconds()
        remaining = elapsed * (1.0 - frac) / frac
        m, s = divmod(int(max(0, remaining)), 60)
        self.eta_lbl.setText(f"{m:d}m {s:02d}s" if m else f"{s:d}s")

    def _reset_case(self, d: dict) -> None:
        extra = "  ".join(f"{k}={v:g}" for k, v in d.get("extra", {}).items())
        self.case_lbl.setText(
            f'Case {d["index"]}/{d["total"]} — {d["case_id"]}')
        # Live case readout mirrors the engine's case.started payload (still the
        # aero aoa/velocity schema — a runtime concern out of scope). Read
        # defensively so a future generic payload can't crash the panel.
        bits = []
        if d.get("aoa") is not None:
            bits.append(f'AOA {d["aoa"]:g}°')
        if d.get("velocity") is not None:
            bits.append(f'V {d["velocity"]:g} m/s')
        if extra:
            bits.append(extra)
        self.info_lbl.setText("   ".join(bits) or "running…")
        self.pipeline.reset()
        self.bar.setValue(0)
        self.eta_lbl.setText("—")
        self._case_start = datetime.now()
        for key in self._metric_vals:
            self._metric_vals[key].setText("–")
        self._its.clear(); self._cl.clear(); self._cd.clear()
        self.cl_curve.setData([], [])
        self.cd_curve.setData([], [])
        for name, _c in _RES_CHANNELS:
            self._res_data[name].clear()
            self._res_its[name].clear()
            self._res_curves[name].setData([], [])
        self._residuals_seen = False

    def _timeline(self, text: str) -> None:
        """Prepend a newest-first timeline entry (kept short)."""
        stamped = f"{datetime.now().strftime('%H:%M:%S')}   {text}"
        self.timeline.insertItem(0, stamped)
        while self.timeline.count() > 40:
            self.timeline.takeItem(self.timeline.count() - 1)
