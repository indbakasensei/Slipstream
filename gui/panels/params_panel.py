"""Input parameters — edit the selected row's inputs, add new experiments.

All mutations go through AppState (which enforces the run-lock and saves the
workbook atomically). Editing is only offered for rows that have not produced
results yet; DONE rows show read-only values with a hint.
"""

from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import (QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from gui.state import AppState

_EDITABLE = {"PENDING", "FAILED", "SKIP", ""}


def _spin(lo: float, hi: float, dec: int, val: float = 0.0) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(lo, hi); s.setDecimals(dec); s.setValue(val)
    s.setKeyboardTracking(False)
    return s


class ParamsPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._wbp_spins: Dict[str, QDoubleSpinBox] = {}

        # -- selected row editor ------------------------------------------#
        self.sel_box = QGroupBox("Selected experiment")
        self.sel_lbl = QLabel("Select a row in the Queue")
        self.sel_lbl.setProperty("hint", True)
        self.aoa = _spin(-90, 90, 2)
        self.vel = _spin(0.01, 5000, 2)
        self.form = QFormLayout()
        self.form.addRow(self.sel_lbl)
        self.form.addRow("AOA [deg]", self.aoa)
        self.form.addRow("Velocity [m/s]", self.vel)
        self.apply_btn = QPushButton("Apply changes")
        self.skip_btn = QPushButton("Toggle SKIP")
        row = QHBoxLayout(); row.addWidget(self.apply_btn); row.addWidget(self.skip_btn)
        v = QVBoxLayout(self.sel_box); v.addLayout(self.form); v.addLayout(row)

        # -- add-new ------------------------------------------------------#
        self.add_box = QGroupBox("Add experiment")
        self.new_aoa = _spin(-90, 90, 2, 0.0)
        self.new_vel = _spin(0.01, 5000, 2, 20.0)
        af = QFormLayout(self.add_box)
        af.addRow("AOA [deg]", self.new_aoa)
        af.addRow("Velocity [m/s]", self.new_vel)
        self.add_btn = QPushButton("＋ Add row")
        self.dup_btn = QPushButton("Duplicate selected")
        ar = QHBoxLayout(); ar.addWidget(self.add_btn); ar.addWidget(self.dup_btn)
        af.addRow(ar)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.sel_box)
        lay.addWidget(self.add_box)
        lay.addStretch(1)

        # -- wiring ---------------------------------------------------------
        self.apply_btn.clicked.connect(self._apply)
        self.skip_btn.clicked.connect(self._skip)
        self.add_btn.clicked.connect(self._add)
        self.dup_btn.clicked.connect(self._duplicate)
        state.caseSelected.connect(self._load_row)
        state.projectLoaded.connect(self._rebuild_wbp)
        state.runStateChanged.connect(lambda r: self.setEnabled(not r))
        state.datasetChanged.connect(lambda: self._load_row(state.selected_row))

    # ------------------------------------------------------------------ #
    def _rebuild_wbp(self) -> None:
        for name, spin in self._wbp_spins.items():
            self.form.removeRow(spin)
        self._wbp_spins.clear()
        for name in self.state.wbp_names:
            spin = _spin(-1e6, 1e6, 3)
            self._wbp_spins[name] = spin
            self.form.insertRow(self.form.rowCount(), f"{name} (WBP)", spin)

    def _load_row(self, row: int) -> None:
        df = self.state.df
        m = df[df["Row"] == row]
        if row < 0 or m.empty:
            self.sel_lbl.setText("Select a row in the Queue")
            self.sel_box.setEnabled(False)
            return
        rec = m.iloc[0]
        status = str(rec["Status"])
        editable = status in _EDITABLE
        self.sel_box.setEnabled(True)
        self.sel_lbl.setText(
            f'Row {row} — {rec["CaseID"]}   [{status}]'
            + ("" if editable else "  · inputs locked (already has results)"))
        self.aoa.setValue(float(rec["AOA"]))
        self.vel.setValue(float(rec["Velocity"]))
        for name, spin in self._wbp_spins.items():
            v = rec.get(name)
            spin.setValue(0.0 if v is None else float(v))
        for w in (self.aoa, self.vel, self.apply_btn, *self._wbp_spins.values()):
            w.setEnabled(editable)

    # -- actions ----------------------------------------------------------#
    def _guard(self, fn) -> None:
        try:
            fn()
        except Exception as exc:                    # ExcelWriteError et al.
            QMessageBox.warning(self, "Schedule update failed", str(exc))

    def _apply(self) -> None:
        row = self.state.selected_row
        def do():
            self.state.update_input(row, "aoa", self.aoa.value())
            self.state.update_input(row, "velocity", self.vel.value())
            for name, spin in self._wbp_spins.items():
                self.state.update_input(row, name, spin.value())
        self._guard(do)

    def _skip(self) -> None:
        row = self.state.selected_row
        if row > 0:
            self._guard(lambda: self.state.toggle_skip(row))

    def _add(self) -> None:
        self._guard(lambda: self.state.add_experiment(
            self.new_aoa.value(), self.new_vel.value()))

    def _duplicate(self) -> None:
        row = self.state.selected_row
        m = self.state.df[self.state.df["Row"] == row]
        if m.empty:
            return
        rec = m.iloc[0]
        extra = {n: float(rec[n]) for n in self.state.wbp_names
                 if rec.get(n) is not None}
        self._guard(lambda: self.state.add_experiment(
            float(rec["AOA"]), float(rec["Velocity"]), extra))
