"""Interactive results charts (pyqtgraph): pick X/Y/color-by, presets for the
classic aero plots, hover-to-identify, PNG export. Only DONE rows with valid
numbers are plotted; grouping by the colour variable draws one sorted
scatter+line series per group with a legend.

v2.2 Workspace Revolution: the chart page is restyled as a professional
analytical workspace — grouped axis controls, polished plot surface with an
engineering empty state, and consistent visual hierarchy with the redesigned
Dashboard and Monitor. Presentation-only; pyqtgraph untouched.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy,
                               QStackedLayout, QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState
from gui.widgets import make_icon

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

        # ---- Toolbar: axis selectors + presets + export ----------------- #
        toolbar = QWidget()
        toolbar.setProperty("chartToolbar", True)
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM,
                              theme.SPACE_SM, theme.SPACE_SM)
        tb.setSpacing(theme.SPACE_SM)

        for lbl_text in ("X", "Y", "Color"):
            lbl = QLabel(f"{lbl_text}:")
            lbl.setProperty("caption", True)
            tb.addWidget(lbl)

        self.x_box = QComboBox()
        tb.addWidget(self.x_box)
        self.y_box = QComboBox()
        self.y_box.addItems(Y_CHOICES)
        tb.addWidget(self.y_box)
        self.c_box = QComboBox()
        tb.addWidget(self.c_box)

        tb.addSpacing(theme.SPACE_MD)

        # Preset buttons reference the study's own input columns (from
        # metadata) — never literal parameter names — so they read naturally
        # for whatever template is loaded (AOA/Velocity for External Aero).
        prim = state.primary_input()
        sec = state.secondary_input()
        px = prim.display_name if prim is not None else "X"
        sx = sec.display_name if sec is not None else px
        for label, preset in ((f"CL vs {px}", (px, "CL", sx)),
                              ("Drag polar", ("CD", "CL", px)),
                              (f"L/D vs {sx}", (sx, "L/D", px))):
            b = QPushButton(label)
            b.clicked.connect(lambda _, p=preset: self._preset(*p))
            tb.addWidget(b)

        tb.addStretch(1)

        png = QPushButton("Export PNG…")
        png.setIcon(make_icon("export", theme.TEXT_DIM))
        png.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE, theme.TOOLBAR_ICON_SIZE))
        png.clicked.connect(self._export)
        tb.addWidget(png)

        # ---- Chart (dominant) ------------------------------------------- #
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel("bottom", "")
        self.plot.setLabel("left", "")
        self.plot.setTitle("")
        self.legend = self.plot.addLegend(offset=(-10, 10))
        self.hover = pg.TextItem("", anchor=(0, 1),
                                 color=theme.TEXT, fill=(30, 32, 36, 220))
        self.hover.setZValue(10)
        self.plot.addItem(self.hover)
        self.hover.hide()
        self._points: List[Tuple[float, float, str]] = []
        self._proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved,
                                     rateLimit=25, slot=self._mouse_moved)

        # ---- Empty state ------------------------------------------------ #
        empty_icon = make_icon("results", theme.TEXT_DIM, 48)
        self._empty_widget = QWidget()
        empty_lay = QVBoxLayout(self._empty_widget)
        empty_lay.setAlignment(Qt.AlignCenter)
        if empty_icon:
            ic_lbl = QLabel()
            ic_lbl.setPixmap(empty_icon.pixmap(48, 48))
            ic_lbl.setAlignment(Qt.AlignCenter)
            empty_lay.addWidget(ic_lbl)
        title_lbl = QLabel("No Result Data")
        title_lbl.setProperty("chartEmptyTitle", True)
        title_lbl.setAlignment(Qt.AlignCenter)
        empty_lay.addWidget(title_lbl)
        hint_lbl = QLabel("Run a study to populate engineering plots.")
        hint_lbl.setProperty("chartEmptyHint", True)
        hint_lbl.setAlignment(Qt.AlignCenter)
        empty_lay.addWidget(hint_lbl)

        # ---- Stack: plot vs empty --------------------------------------- #
        self._content_stack = QStackedLayout()
        self._content_stack.addWidget(self.plot)         # index 0
        self._content_stack.addWidget(self._empty_widget) # index 1

        # ---- Assemble -------------------------------------------------- #
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM,
                               theme.SPACE_SM, theme.SPACE_SM)
        lay.setSpacing(theme.SPACE_SM)
        lay.addWidget(toolbar)
        lay.addLayout(self._content_stack, 1)

        state.projectLoaded.connect(self._rebuild_axes)
        state.datasetChanged.connect(self.refresh)
        for box in (self.x_box, self.y_box, self.c_box):
            box.currentTextChanged.connect(lambda *_: self.refresh())

    # ------------------------------------------------------------------ #
    def _rebuild_axes(self) -> None:
        # Phase 3B: the input-axis order comes from the runtime
        # ExperimentDefinition, not a hardcoded ["AOA", "Velocity"].
        # Identical result today; correct automatically for any future template.
        xs = self.state.experiment_definition.input_columns() + self.state.wbp_names
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
            self._content_stack.setCurrentIndex(1)
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
        self._content_stack.setCurrentIndex(0 if self._points else 1)

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
