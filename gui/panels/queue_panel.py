"""Simulation queue — the schedule as a live, colour-coded table + run controls.

Emits high-level intent (run/stop); the MainWindow owns the EngineWorker.
Row selection drives every other case-aware panel through AppState.
"""

from __future__ import annotations

from typing import Optional, Set

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout,
                               QHeaderView, QLabel, QMenu, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState
from gui.widgets import SectionHeader


def _item(text: str, sort_value=None) -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    if sort_value is not None:
        it.setData(Qt.UserRole, float(sort_value))
    return it


class _SortableTable(QTableWidgetItem):
    pass


class QueuePanel(QWidget):
    runRequested = Signal(object, bool, int)   # only_rows | None, retry, max
    stopRequested = Signal()

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        # -- controls ---------------------------------------------------- #
        bar = QHBoxLayout()
        self.run_all = QPushButton("▶ Run All")
        self.run_all.setProperty("accent", True)
        self.run_sel = QPushButton("Run Selected")
        self.stop_btn = QPushButton("⏹ Stop after case")
        self.stop_btn.setEnabled(False)
        self.retry_chk = QCheckBox("Retry FAILED")
        bar.addWidget(self.run_all)
        bar.addWidget(self.run_sel)
        bar.addWidget(self.stop_btn)
        bar.addSpacing(12)
        bar.addWidget(self.retry_chk)
        bar.addWidget(QLabel("Max cases:"))
        self.max_spin = QSpinBox(); self.max_spin.setRange(0, 9999)
        self.max_spin.setSpecialValueText("all")
        bar.addWidget(self.max_spin)
        bar.addStretch(1)

        # -- table --------------------------------------------------------#
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemSelectionChanged.connect(self._selection_changed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                               theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        lay.setSpacing(theme.SPACE_SM)
        lay.addWidget(SectionHeader("Queue", icon="▤"))
        lay.addLayout(bar)
        lay.addWidget(self.table)

        # -- wiring -------------------------------------------------------#
        self.run_all.clicked.connect(lambda: self.runRequested.emit(
            None, self.retry_chk.isChecked(), self.max_spin.value()))
        self.run_sel.clicked.connect(self._run_selected)
        self.stop_btn.clicked.connect(self.stopRequested.emit)
        state.datasetChanged.connect(self.refresh)
        state.runStateChanged.connect(self._on_run_state)

    # ------------------------------------------------------------------ #
    def columns(self):
        # Phase 3B: the input columns come from the runtime ExperimentDefinition
        # (materialized from the active template's study definition) rather
        # than being hardcoded here. Identical result today.
        return (["Row"] + self.state.experiment_definition.input_columns()
                + self.state.wbp_names
                + ["Status", "CL", "CD", "L/D", "It", "Conv"])

    def refresh(self) -> None:
        df = self.state.df
        cols = self.columns()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        for r, (_, row) in enumerate(df.iterrows()):
            vals = {
                "Row": (str(int(row["Row"])), row["Row"]),
                "AOA": (f'{row["AOA"]:g}', row["AOA"]),
                "Velocity": (f'{row["Velocity"]:g}', row["Velocity"]),
                "Status": (str(row["Status"]), None),
                "CL": (_fmt(row["CL"], "{:.4f}"), row["CL"]),
                "CD": (_fmt(row["CD"], "{:.5f}"), row["CD"]),
                "L/D": (_fmt(row["L/D"], "{:.2f}"), row["L/D"]),
                "It": (_fmt(row["Iterations"], "{:.0f}"), row["Iterations"]),
                "Conv": (str(row["Converged"] or ""), None),
            }
            for name in self.state.wbp_names:
                v = row.get(name)
                vals[name] = (_fmt(v, "{:g}"), v)
            for c, name in enumerate(cols):
                text, sv = vals[name]
                it = _item(text, sv if sv is not None else None)
                if name == "Status":
                    col = theme.qcolor(text)
                    it.setForeground(col)
                    f = it.font(); f.setBold(True); it.setFont(f)
                    badge = QColor(col); badge.setAlpha(36)   # soft status "badge" tint
                    it.setBackground(badge)
                if name == "Conv" and text == "NO":
                    it.setForeground(QColor(theme.STATUS_COLORS["FAILED"]))
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)

    # ------------------------------------------------------------------ #
    def selected_rows(self) -> Set[int]:
        col = self.columns().index("Row")
        out = set()
        for it in self.table.selectedItems():
            if it.column() == col:
                out.add(int(float(it.text())))
        return out

    def _run_selected(self) -> None:
        rows = self.selected_rows()
        if rows:
            self.runRequested.emit(rows, self.retry_chk.isChecked(),
                                   self.max_spin.value())

    def _selection_changed(self) -> None:
        rows = sorted(self.selected_rows())
        if rows:
            self.state.select_case(rows[0])

    def _on_run_state(self, running: bool) -> None:
        for w in (self.run_all, self.run_sel, self.retry_chk, self.max_spin):
            w.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    # -- context menu -----------------------------------------------------#
    def _menu(self, pos) -> None:
        rows = self.selected_rows()
        if not rows or self.state.running:
            return
        m = QMenu(self)
        m.addAction("Toggle SKIP", lambda: self._each(rows, self.state.toggle_skip))
        m.addAction("Re-queue (clear status)",
                    lambda: self._each(rows, self.state.requeue))
        m.exec(self.table.viewport().mapToGlobal(pos))

    @staticmethod
    def _each(rows, fn):
        for r in sorted(rows):
            fn(r)


def _fmt(v, fmt: str) -> str:
    try:
        return "" if v is None else fmt.format(float(v))
    except (TypeError, ValueError):
        return ""
