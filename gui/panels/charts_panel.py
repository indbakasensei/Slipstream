"""Interactive results charts (pyqtgraph): pick X/Y/color-by, presets for the
classic aero plots, hover-to-identify, PNG export. Only DONE rows with valid
numbers are plotted; grouping by the colour variable draws one sorted
scatter+line series per group with a legend."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState

Y_CHOICES = ["CL", "CD", "L/D", "Lift_N", "Drag_N", "Iterations"]


def series_groups(df, x: str, y: str, color_by: Optional[str]
                  ) -> List[Tuple[str, List[float], List[float], List[str]]]:
    """(label, xs, ys, case_ids) per colour group — shared with Dashboard."""
    d = df[df["Status"] == "DONE"].copy()
    if d.empty or x not in d or y not in d:
        return []
    d = d[[x, y, "CaseID"] + ([color_by] if color_by and color_by in d else [])]
    d = d.dropna(subset=[x, y])
    if d.empty:
        return []
    groups = []
    if color_by and color_by in d:
        for key, sub in d.groupby(color_by, dropna=True):
            sub = sub.sort_values(x)
            groups.append((f"{color_by}={key:g}" if isinstance(key, float)
                           else f"{color_by}={key}",
                           list(sub[x]), list(sub[y]), list(sub["CaseID"])))
    else:
        d = d.sort_values(x)
        groups.append((y, list(d[x]), list(d[y]), list(d["CaseID"])))
    return groups


class ChartsPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        bar = QHBoxLayout()
        bar.addWidget(QLabel("X:"))
        self.x_box = QComboBox()
        bar.addWidget(self.x_box)
        bar.addWidget(QLabel("Y:"))
        self.y_box = QComboBox(); self.y_box.addItems(Y_CHOICES)
        bar.addWidget(self.y_box)
        bar.addWidget(QLabel("Color by:"))
        self.c_box = QComboBox()
        bar.addWidget(self.c_box)
        bar.addSpacing(10)
        for label, preset in (("CL vs AOA", ("AOA", "CL", "Velocity")),
                              ("Drag polar", ("CD", "CL", "AOA")),
                              ("L/D vs V", ("Velocity", "L/D", "AOA"))):
            b = QPushButton(label)
            b.clicked.connect(lambda _, p=preset: self._preset(*p))
            bar.addWidget(b)
        bar.addStretch(1)
        png = QPushButton("Export PNG…")
        png.clicked.connect(self._export)
        bar.addWidget(png)

        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.legend = self.plot.addLegend(offset=(-10, 10))
        self.hover = pg.TextItem("", anchor=(0, 1),
                                 color=theme.TEXT, fill=(30, 32, 36, 220))
        self.hover.setZValue(10)
        self.plot.addItem(self.hover)
        self.hover.hide()
        self._points: List[Tuple[float, float, str]] = []
        self._proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved,
                                     rateLimit=25, slot=self._mouse_moved)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(bar)
        lay.addWidget(self.plot)

        state.projectLoaded.connect(self._rebuild_axes)
        state.datasetChanged.connect(self.refresh)
        for box in (self.x_box, self.y_box, self.c_box):
            box.currentTextChanged.connect(lambda *_: self.refresh())

    # ------------------------------------------------------------------ #
    def _rebuild_axes(self) -> None:
        xs = ["AOA", "Velocity"] + self.state.wbp_names
        for box, items in ((self.x_box, xs),
                           (self.c_box, ["(none)"] + xs)):
            box.blockSignals(True)
            box.clear(); box.addItems(items)
            box.blockSignals(False)
        self.refresh()

    def _preset(self, x: str, y: str, c: str) -> None:
        for box, val in ((self.x_box, x), (self.y_box, y), (self.c_box, c)):
            i = box.findText(val)
            if i >= 0:
                box.setCurrentIndex(i)
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        x, y = self.x_box.currentText(), self.y_box.currentText()
        c = self.c_box.currentText()
        c = None if c in ("", "(none)") else c
        for item in list(self.plot.listDataItems()):
            self.plot.removeItem(item)
        self.legend.clear()
        self._points.clear()
        if not x or not y:
            return
        groups = series_groups(self.state.df, x, y, c)
        for i, (label, xs, ys, ids) in enumerate(groups):
            col = theme.CHART_SERIES[i % len(theme.CHART_SERIES)]
            self.plot.plot(xs, ys, pen=pg.mkPen(col, width=1.6),
                           symbol="o", symbolSize=7,
                           symbolBrush=col, symbolPen=None, name=label)
            self._points += [(px, py, f"{cid}\n{x}={px:g}  {y}={py:g}")
                             for px, py, cid in zip(xs, ys, ids)]
        self.plot.setLabel("bottom", x)
        self.plot.setLabel("left", y)
        self.plot.setTitle(f"{y} vs {x}" + (f"  ·  by {c}" if c else ""))

    def point_count(self) -> int:            # used by the smoke test
        return len(self._points)

    # ------------------------------------------------------------------ #
    def _mouse_moved(self, args) -> None:
        if not self._points:
            return
        pos = args[0]
        vb = self.plot.getPlotItem().vb
        if not self.plot.sceneBoundingRect().contains(pos):
            self.hover.hide(); return
        mp = vb.mapSceneToView(pos)
        px, py = vb.viewPixelSize()
        best, bd = None, 1e18
        for x, y, label in self._points:
            d = ((x - mp.x()) / (px or 1)) ** 2 + ((y - mp.y()) / (py or 1)) ** 2
            if d < bd:
                bd, best = d, (x, y, label)
        if best and math.sqrt(bd) < 14:       # within ~14 px
            self.hover.setText(best[2])
            self.hover.setPos(best[0], best[1])
            self.hover.show()
        else:
            self.hover.hide()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export chart",
                                              "chart.png", "PNG (*.png)")
        if path:
            ImageExporter(self.plot.getPlotItem()).export(path)
