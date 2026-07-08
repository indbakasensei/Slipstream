"""Run monitor — what the terminal never showed you.

Current case header, the pipeline strip, a weighted progress bar, and a live
CL/CD convergence plot fed by ``solve.progress`` events (per chunk today;
per iteration once the v0.9 telemetry tap lands — same widget either way).
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtWidgets import (QGridLayout, QLabel, QProgressBar, QVBoxLayout,
                               QWidget)

from cfdauto.events import Event
from gui import theme
from gui.widgets import PipelineWidget

# Progress weighting: pre-solve stages are quick but visible; solving owns
# the bar. (mesh 12, launch 8, setup+init 5 → 25%, solve → 95%, extract → 100)
_PRESTAGE_PCT = {"mesh": 12, "fluent_launch": 20, "setup": 23,
                 "initialize": 25}


class MonitorPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.case_lbl = QLabel("No case running")
        self.case_lbl.setProperty("h1", True)
        self.info_lbl = QLabel("")
        self.info_lbl.setProperty("hint", True)

        self.pipeline = PipelineWidget()
        self.bar = QProgressBar(); self.bar.setRange(0, 100)

        self.plot = pg.PlotWidget(title="Force-coefficient convergence")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "iteration")
        self.plot.addLegend(offset=(-10, 10))
        self.cl_curve = self.plot.plot([], [], pen=pg.mkPen(theme.ACCENT, width=2),
                                       name="CL")
        self.cd_curve = self.plot.plot([], [], pen=pg.mkPen("#e8a33d", width=2),
                                       name="CD")
        self._its, self._cl, self._cd = [], [], []

        grid = QGridLayout()
        grid.addWidget(self.case_lbl, 0, 0)
        grid.addWidget(self.info_lbl, 0, 1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addLayout(grid)
        lay.addWidget(self.pipeline)
        lay.addWidget(self.bar)
        lay.addWidget(self.plot, 1)

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
        elif t == "solve.progress":
            self._its.append(d["it"]); self._cl.append(d["cl"])
            self._cd.append(d["cd"])
            self.cl_curve.setData(self._its, self._cl)
            self.cd_curve.setData(self._its, self._cd)
            frac = d["it"] / max(1, d.get("max_it", 1))
            self.bar.setValue(int(25 + 70 * min(1.0, frac)))
            self.info_lbl.setText(
                f'iter {d["it"]}   CL={d["cl"]:.4f}   CD={d["cd"]:.5f}')
        elif t in ("solve.converged", "solve.maxiter"):
            self.bar.setValue(95)
        elif t == "case.done":
            self.pipeline.set_stage("extract", "done")
            self.bar.setValue(100)
        elif t == "case.failed":
            self.pipeline.mark_active_failed()
            self.info_lbl.setText(f'FAILED: {d.get("error", "")[:120]}')

    def _reset_case(self, d: dict) -> None:
        extra = "  ".join(f"{k}={v:g}" for k, v in d.get("extra", {}).items())
        self.case_lbl.setText(
            f'Case {d["index"]}/{d["total"]} — {d["case_id"]}')
        self.info_lbl.setText(
            f'AOA {d["aoa"]:g}°   V {d["velocity"]:g} m/s   {extra}')
        self.pipeline.reset()
        self.bar.setValue(0)
        self._its, self._cl, self._cd = [], [], []
        self.cl_curve.setData([], [])
        self.cd_curve.setData([], [])
