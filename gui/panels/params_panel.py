"""Input parameters — edit the selected row's inputs, add new experiments.

Dynamic Template UI (Capability 2): every editor in this panel is *generated*
from the active template's :class:`StudyDefinition` — one spin box per study
parameter, with its label, unit, range, precision, default, tooltip, and
validation all sourced from the :class:`ParameterDefinition` metadata (via
:mod:`gui.param_render`). The panel contains **no parameter names**: it renders
External Aerodynamics (AOA, Velocity) and Internal Flow (inlet velocity, pipe
diameter, …) identically well, and a future template needs zero UI code.

All mutations go through AppState (which enforces the run-lock and saves the
workbook atomically). Editing is only offered for rows without results yet;
DONE rows show read-only values with a hint.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from PySide6.QtWidgets import (QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QVBoxLayout, QWidget)

from gui import param_render
from gui.state import AppState

_EDITABLE = {"PENDING", "FAILED", "SKIP", ""}

# One (StudyParameter, spin) row of a generated form.
_Row = Tuple[object, QDoubleSpinBox]


class ParamsPanel(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self._wbp_spins: Dict[str, QDoubleSpinBox] = {}
        self._sel_rows: List[_Row] = []
        self._add_rows: List[_Row] = []

        # -- selected row editor ----------------------------------------- #
        self.sel_box = QGroupBox("Selected experiment")
        self.sel_lbl = QLabel("Select a row in the Queue")
        self.sel_lbl.setProperty("hint", True)
        self.form = QFormLayout()
        self.form.addRow(self.sel_lbl)
        for sp in state.input_parameters():
            spin = param_render.make_spin(sp.parameter, value=0.0)
            self.form.addRow(param_render.label_for(sp.parameter), spin)
            self._sel_rows.append((sp, spin))
        self.apply_btn = QPushButton("Apply changes")
        self.skip_btn = QPushButton("Toggle SKIP")
        row = QHBoxLayout(); row.addWidget(self.apply_btn); row.addWidget(self.skip_btn)
        v = QVBoxLayout(self.sel_box); v.addLayout(self.form); v.addLayout(row)

        # -- add-new ----------------------------------------------------- #
        self.add_box = QGroupBox("Add experiment")
        af = QFormLayout(self.add_box)
        for sp in state.input_parameters():
            spin = param_render.make_spin(sp.parameter)     # template default
            af.addRow(param_render.label_for(sp.parameter), spin)
            self._add_rows.append((sp, spin))
        self.add_btn = QPushButton("＋ Add row")
        self.dup_btn = QPushButton("Duplicate selected")
        ar = QHBoxLayout(); ar.addWidget(self.add_btn); ar.addWidget(self.dup_btn)
        af.addRow(ar)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.sel_box)
        lay.addWidget(self.add_box)
        lay.addStretch(1)

        # -- wiring ------------------------------------------------------ #
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
        for spin in self._wbp_spins.values():
            self.form.removeRow(spin)
        self._wbp_spins.clear()
        for name in self.state.wbp_names:
            spin = param_render.plain_spin(tooltip=f"{name} — free Workbench "
                                           f"parameter (no metadata bounds).")
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
        for sp, spin in self._sel_rows:
            val = rec.get(sp.display_name)
            spin.setValue(0.0 if val is None else float(val))
        for name, spin in self._wbp_spins.items():
            val = rec.get(name)
            spin.setValue(0.0 if val is None else float(val))
        for _sp, spin in self._sel_rows:
            spin.setEnabled(editable)
        for w in (self.apply_btn, *self._wbp_spins.values()):
            w.setEnabled(editable)

    # -- actions --------------------------------------------------------- #
    def _guard(self, fn) -> None:
        try:
            fn()
        except Exception as exc:                    # ExcelWriteError et al.
            QMessageBox.warning(self, "Schedule update failed", str(exc))

    def _validate(self, values: Dict[str, float]) -> bool:
        """Surface any metadata validation problems; True = OK to write."""
        problems = param_render.validate_row(self.state.experiment_definition,
                                             values)
        if problems:
            QMessageBox.warning(self, "Invalid input", "\n".join(problems))
            return False
        return True

    def _apply(self) -> None:
        row = self.state.selected_row
        values = {sp.name: spin.value() for sp, spin in self._sel_rows}
        if not self._validate(values):
            return
        def do():
            self.state.update_inputs(row, values)
            for name, spin in self._wbp_spins.items():
                self.state.update_input(row, name, spin.value())
        self._guard(do)

    def _skip(self) -> None:
        row = self.state.selected_row
        if row > 0:
            self._guard(lambda: self.state.toggle_skip(row))

    def _add(self) -> None:
        values = {sp.name: spin.value() for sp, spin in self._add_rows}
        if not self._validate(values):
            return
        self._guard(lambda: self.state.add_experiment(values))

    def _duplicate(self) -> None:
        row = self.state.selected_row
        m = self.state.df[self.state.df["Row"] == row]
        if m.empty:
            return
        rec = m.iloc[0]
        values = {sp.name: float(rec[sp.display_name])
                  for sp, _spin in self._sel_rows
                  if rec.get(sp.display_name) is not None}
        extra = {n: float(rec[n]) for n in self.state.wbp_names
                 if rec.get(n) is not None}
        if not self._validate(values):
            return
        self._guard(lambda: self.state.add_experiment(values, extra))
