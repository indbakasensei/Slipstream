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

v2.2 Workspace Revolution: restyled as an engineering control panel — each
parameter row shows its display name, allowed range, unit, and default from
metadata, under a shared section header. Presentation only; the form layout,
validation flow (the metadata-driven QMessageBox), and every public attribute
are preserved.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (QDoubleSpinBox, QFormLayout, QFrame, QGroupBox,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from gui import param_render, theme
from gui.state import AppState
from gui.widgets import SectionHeader, make_icon

_EDITABLE = {"PENDING", "FAILED", "SKIP", ""}

# One (StudyParameter, spin) row of a generated form.
_Row = Tuple[object, QDoubleSpinBox]


def _meta_caption(pdef) -> str:
    """Compact caption for a parameter row — unit · default, from metadata."""
    parts: List[str] = []
    if pdef.unit:
        parts.append(pdef.unit)
    if pdef.default_value is not None:
        try:
            parts.append(f"default {float(pdef.default_value):g}")
        except (TypeError, ValueError):
            pass
    return "  ·  ".join(parts)


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
        self.form.setSpacing(theme.SPACE_MD)
        self.form.setHorizontalSpacing(theme.SPACE_MD)
        self.form.addRow(self.sel_lbl)
        for sp in state.input_parameters():
            lbl, spin, field = self._build_row(sp, value=0.0)
            self.form.addRow(lbl, field)
            self._sel_rows.append((sp, spin))
        self.apply_btn = QPushButton("Apply changes")
        self.apply_btn.setIcon(make_icon("validate", theme.TEXT_DIM))
        self.apply_btn.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                         theme.TOOLBAR_ICON_SIZE))
        self.skip_btn = QPushButton("Toggle SKIP")
        row = QHBoxLayout(); row.addWidget(self.apply_btn); row.addWidget(self.skip_btn)
        v = QVBoxLayout(self.sel_box); v.addLayout(self.form); v.addLayout(row)

        # -- add-new ----------------------------------------------------- #
        self.add_box = QGroupBox("Add experiment")
        af = QFormLayout(self.add_box)
        af.setSpacing(theme.SPACE_MD)
        af.setHorizontalSpacing(theme.SPACE_MD)
        for sp in state.input_parameters():
            lbl, spin, field = self._build_row(sp)
            af.addRow(lbl, field)
            self._add_rows.append((sp, spin))
        self.add_btn = QPushButton("＋ Add row")
        self.add_btn.setIcon(make_icon("plus", theme.TEXT_DIM))
        self.add_btn.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                       theme.TOOLBAR_ICON_SIZE))
        self.dup_btn = QPushButton("Duplicate selected")
        self.dup_btn.setIcon(make_icon("duplicate", theme.TEXT_DIM))
        self.dup_btn.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                       theme.TOOLBAR_ICON_SIZE))
        ar = QHBoxLayout(); ar.addWidget(self.add_btn); ar.addWidget(self.dup_btn)
        af.addRow(ar)

        # Capability 3 UI foundation: the form is now dynamic (a template may
        # declare many parameters, e.g. Internal Flow's five + WBP columns), so
        # the whole panel scrolls rather than clipping in a short dock.
        content = QWidget()
        cv = QVBoxLayout(content)
        cv.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                              theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        cv.setSpacing(theme.SECTION_SPACING)
        cv.addWidget(SectionHeader("Parameters", icon_name="settings"))
        hint = QLabel("Editors are generated from the active template "
                      "metadata — units, ranges and defaults included.")
        hint.setProperty("hint", True)
        cv.addWidget(hint)
        cv.addWidget(self.sel_box)
        cv.addWidget(self.add_box)
        cv.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)
        self.setMinimumWidth(theme.MIN_PANEL_WIDTH)

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
    def _build_row(self, sp, value: Optional[float] = None
                   ) -> Tuple[QWidget, QDoubleSpinBox, QWidget]:
        """(label_widget, spin, field_widget) for one metadata-driven
        parameter. The label column carries the display name + allowed range;
        the field column carries the spin + unit/default caption. Every string
        comes from the ParameterDefinition — nothing is hardcoded."""
        pdef = sp.parameter
        spin = param_render.make_spin(pdef, value=value)

        name = QLabel(sp.display_name)
        name.setProperty("paramName", True)
        lbl = QWidget(); ll = QVBoxLayout(lbl)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(theme.SPACE_XS)
        ll.addWidget(name)
        rng = QLabel(param_render.range_text(pdef))
        rng.setProperty("paramMeta", True)
        ll.addWidget(rng)
        ll.addStretch(1)

        field = QWidget(); fl = QVBoxLayout(field)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(theme.SPACE_XS)
        fl.addWidget(spin)
        cap = _meta_caption(pdef)
        if cap:
            cap_lbl = QLabel(cap)
            cap_lbl.setProperty("paramMeta", True)
            fl.addWidget(cap_lbl)
        return lbl, spin, field

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
