"""Simulation queue — the engineering worklist for a running study.

Emits high-level intent (run/stop); the MainWindow owns the EngineWorker.
Row selection drives every other case-aware panel through AppState.

v2.2 Workspace Revolution: the queue is restyled as a professional engineering
worklist with a summary header, status filter pills, compact row density, and
an empty state — all presentation-only. Every public attribute and signal is
preserved; the data model (AppState.df) is never modified.
"""

from __future__ import annotations

from typing import Optional, Set

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QHBoxLayout,
                               QHeaderView, QLabel, QMenu, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from gui import param_render, theme
from gui.state import AppState
from gui.widgets import (SectionHeader, StatusBadgeDelegate, ToolbarSection,
                         make_icon)
from gui.widgets.flow_layout import FlowLayout


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
        self._active_filter: str = "ALL"

        # ---- Header row: section title + status summary ----------------- #
        header = QHBoxLayout()
        header.setSpacing(theme.SPACE_MD)
        header.addWidget(SectionHeader("Queue", icon_name="queue"), 1)

        # Status summary — computed on every refresh from df
        self._summary_lbl = QLabel("")
        self._summary_lbl.setProperty("hint", True)
        header.addWidget(self._summary_lbl)

        # ---- Run controls — own wrapping row (Stage 6, P1) --------------- #
        # The three controls need ~345px together; a queue header can't afford
        # that once the panel narrows. On their own full-width row they stay on
        # one readable line at the default width and wrap to a second line
        # (growing the panel taller) instead of crushing below sizeHint.
        run_grp = ToolbarSection("Run", wrap=True)
        self.run_all = QPushButton("Run All")
        self.run_all.setProperty("accent", True)
        self.run_all.setIcon(make_icon("run", theme.ACCENT_TEXT))
        self.run_all.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                       theme.TOOLBAR_ICON_SIZE))
        self.run_sel = QPushButton("Run Selected")
        self.stop_btn = QPushButton("Stop after case")
        self.stop_btn.setIcon(make_icon("stop", theme.WARNING))
        self.stop_btn.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                        theme.TOOLBAR_ICON_SIZE))
        self.stop_btn.setEnabled(False)
        run_grp.add(self.run_all)
        run_grp.add(self.run_sel)
        run_grp.add(self.stop_btn)

        # ---- Filter row — reflows instead of crushing (Stage 6, P2) ------ #
        self._filter_btns: dict[str, QPushButton] = {}
        filter_row = FlowLayout()
        filter_row.setSpacing(theme.SPACE_XS)
        for label in ("ALL", "PENDING", "RUNNING", "DONE", "FAILED"):
            btn = QPushButton(label)
            btn.setProperty("queueFilter", True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, l=label: self._set_filter(l))
            self._filter_btns[label] = btn
            filter_row.addWidget(btn)
        self.retry_chk = QCheckBox("Retry FAILED")
        filter_row.addWidget(self.retry_chk)
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 9999)
        self.max_spin.setSpecialValueText("all")
        filter_row.addWidget(QLabel("Max:"))
        filter_row.addWidget(self.max_spin)
        self._update_filter_btns()

        # ---- Table ----------------------------------------------------- #
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self._status_delegate = StatusBadgeDelegate()
        try:
            self.table.setItemDelegateForColumn(
                self.columns().index("Status"), self._status_delegate)
        except ValueError:
            pass

        # ---- Empty state ------------------------------------------------ #
        self._empty = QLabel("No simulation cases in queue.\nLoad a project "
                             "and run a study to populate the queue.")
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setProperty("hint", True)

        # ---- Assemble -------------------------------------------------- #
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.PANEL_MARGIN, theme.PANEL_MARGIN,
                               theme.PANEL_MARGIN, theme.PANEL_MARGIN)
        lay.setSpacing(theme.SPACE_SM)
        lay.addLayout(header)
        lay.addWidget(run_grp)
        lay.addLayout(filter_row)
        lay.addWidget(self.table, 1)
        lay.addWidget(self._empty)
        self._empty.hide()
        self.setMinimumWidth(theme.MIN_QUEUE_WIDTH)

        # -- wiring ------------------------------------------------------- #
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
        # Which columns are dynamic study inputs (display-name keyed in the
        # dataset) vs. free Workbench params — both render as plain numbers.
        input_labels = self.state.experiment_definition.input_columns()
        numeric_input_cols = set(input_labels) | set(self.state.wbp_names)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self._apply_header_metadata(cols)
        for r, (_, row) in enumerate(df.iterrows()):
            for c, name in enumerate(cols):
                text, sv = self._cell_value(row, name, numeric_input_cols)
                it = _item(text, sv)
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
        # v2.2: summary header + status filter
        self._update_summary(df)
        self._apply_filter()

    # ------------------------------------------------------------------ #
    def _cell_value(self, row, name: str, numeric_input_cols: Set[str]):
        """(display text, sort value) for one queue cell — driven by which
        column this is, with dynamic study-input columns handled generically
        (no parameter names hardcoded)."""
        if name == "Row":
            return str(int(row["Row"])), row["Row"]
        if name in numeric_input_cols:
            v = row.get(name)
            return _fmt(v, "{:g}"), v
        if name == "Status":
            return str(row["Status"]), None
        if name == "It":
            return _fmt(row["Iterations"], "{:.0f}"), row["Iterations"]
        if name == "Conv":
            return str(row["Converged"] or ""), None
        fmt = {"CL": "{:.4f}", "CD": "{:.5f}", "L/D": "{:.2f}"}.get(name, "{:g}")
        v = row.get(name)
        return _fmt(v, fmt), v

    def _apply_header_metadata(self, cols) -> None:
        """Attach each study-input column header a metadata tooltip (label,
        unit, default, range) so the queue surfaces units/limits on hover —
        External Aero and any other template alike."""
        by_label = {p.display_name: p for p in self.state.input_parameters()}
        for c, name in enumerate(cols):
            sp = by_label.get(name)
            item = self.table.horizontalHeaderItem(c)
            if sp is not None and item is not None:
                item.setToolTip(param_render.tooltip_for(sp.parameter))

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

    # -- v2.2: status summary + filter ------------------------------------ #
    def _update_summary(self, df) -> None:
        """Recompute the compact header status line from the current df."""
        total = len(df)
        if total == 0:
            self._summary_lbl.setText("No cases")
            return
        counts = df["Status"].value_counts() if "Status" in df.columns else {}
        done = int(counts.get("DONE", 0))
        failed = int(counts.get("FAILED", 0))
        running = int(counts.get("RUNNING", 0))
        pending = int(counts.get("PENDING", 0))
        parts = [f"{total} cases"]
        if done:
            parts.append(f"{done} done")
        if running:
            parts.append(f"{running} running")
        if pending:
            parts.append(f"{pending} pending")
        if failed:
            parts.append(f"{failed} failed")
        self._summary_lbl.setText(" · ".join(parts))

    def _set_filter(self, label: str) -> None:
        self._active_filter = label
        self._update_filter_btns()
        self._apply_filter()

    def _update_filter_btns(self) -> None:
        for lbl, btn in self._filter_btns.items():
            btn.setProperty("active", lbl == self._active_filter)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _apply_filter(self) -> None:
        """Show/hide table rows to match the active status filter.
        Presentation-only — never modifies AppState.df."""
        f = self._active_filter
        visible = 0
        for r in range(self.table.rowCount()):
            if f == "ALL":
                show = True
            else:
                status_item = None
                try:
                    status_item = self.table.item(
                        r, self.columns().index("Status"))
                except (ValueError, IndexError):
                    pass
                row_status = status_item.text() if status_item else ""
                show = (row_status == f)
            self.table.setRowHidden(r, not show)
            if show:
                visible += 1
        # Toggle empty state
        has_data = self.table.rowCount() > 0
        self._empty.setVisible(not has_data or visible == 0)
        self.table.setVisible(has_data and visible > 0)

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
