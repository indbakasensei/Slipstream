"""Dataset table — every completed (and pending) experiment, sortable,
exportable to CSV. Read-only by design: inputs are edited in the Params
panel, results only ever come from the engine."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState


class ResultsTablePanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state

        bar = QHBoxLayout()
        self.count_lbl = QLabel("")
        self.count_lbl.setProperty("hint", True)
        bar.addWidget(self.count_lbl)
        bar.addStretch(1)
        exp = QPushButton("Export CSV…")
        exp.clicked.connect(self._export)
        bar.addWidget(exp)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._select)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(bar)
        lay.addWidget(self.table)
        state.datasetChanged.connect(self.refresh)

    def refresh(self) -> None:
        df = self.state.df
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels(list(df.columns))
        for r in range(len(df)):
            for c, col in enumerate(df.columns):
                v = df.iloc[r, c]
                text = "" if v is None else (f"{v:g}" if isinstance(v, float)
                                             else str(v))
                it = QTableWidgetItem(text)
                if isinstance(v, (int, float)) and v is not None:
                    it.setData(Qt.UserRole, float(v))
                if col == "Status":
                    it.setForeground(theme.qcolor(text))
                if col == "Error" and text:
                    it.setToolTip(text)
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents)
        done = int((df["Status"] == "DONE").sum()) if len(df) else 0
        self.count_lbl.setText(f"{len(df)} experiments · {done} completed")

    def _select(self) -> None:
        rows = {int(self.table.item(i.row(), 0).text())
                for i in self.table.selectedItems() if i.column() == 0}
        if rows:
            self.state.select_case(sorted(rows)[0])

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export dataset",
                                              "results.csv", "CSV (*.csv)")
        if path:
            self.state.df.to_csv(path, index=False)
