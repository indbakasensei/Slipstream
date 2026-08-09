"""Project explorer — config, schedule, and every case's artifacts as a tree.

Double-click behaviour: images open in the Images panel; anything else opens
with the system default application. Selecting a case folder selects that
case everywhere (queue, monitor, images)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QPushButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from gui import theme
from gui.state import AppState
from gui.widgets.icons import make_icon

_IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


class ExplorerPanel(QWidget):
    imageActivated = Signal(object)        # Path
    caseActivated = Signal(int)            # Excel row

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._activate)
        self.tree.itemClicked.connect(self._clicked)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.rebuild)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self.tree, 1)
        lay.addWidget(refresh)

        state.projectLoaded.connect(self.rebuild)
        state.runStateChanged.connect(
            lambda running: None if running else self.rebuild())

    # ------------------------------------------------------------------ #
    def rebuild(self) -> None:
        self.tree.clear()
        st = self.state
        if not st.cfg:
            return
        proj = QTreeWidgetItem([f"Project — {st.config_path.stem}"])
        self.tree.addTopLevelItem(proj)

        def add(parent, label, path: Optional[Path] = None, row: int = -1,
                icon: Optional[str] = None):
            it = QTreeWidgetItem([label])
            if path is not None:
                it.setData(0, Qt.UserRole, str(path))
            if row >= 0:
                it.setData(0, Qt.UserRole + 1, row)
            if icon:
                ic = make_icon(icon, theme.TEXT_DIM, 14)
                if ic is not None:
                    it.setIcon(0, ic)
            parent.addChild(it)
            return it

        add(proj, f"Config — {st.config_path.name}", st.config_path,
            icon="settings")
        add(proj, f"Schedule — {Path(st.cfg.excel.file).name}",
            st.cfg.excel.path(), icon="queue")
        if st.cfg.fluent.baseline_case:
            add(proj,
                f"Baseline case — {Path(st.cfg.fluent.baseline_case).name}",
                Path(st.cfg.fluent.baseline_case), icon="file")

        runs = QTreeWidgetItem(["Runs"])
        proj.addChild(runs)
        cases_dir = st.cfg.work_dir() / "cases"
        row_by_case = {str(r["CaseID"]): int(r["Row"])
                       for _, r in st.df.iterrows()}
        if cases_dir.exists():
            for case in sorted(cases_dir.iterdir()):
                if not case.is_dir():
                    continue
                node = add(runs, case.name, case,
                           row_by_case.get(case.name, -1), icon="folder")
                for f in sorted(case.iterdir()):
                    if f.is_file():
                        add(node, f.name, f, icon="file")
        proj.setExpanded(True)
        runs.setExpanded(True)

    # ------------------------------------------------------------------ #
    def _clicked(self, item: QTreeWidgetItem, _c: int) -> None:
        row = item.data(0, Qt.UserRole + 1)
        if row is not None and int(row) >= 0:
            self.state.select_case(int(row))
            self.caseActivated.emit(int(row))

    def _activate(self, item: QTreeWidgetItem, _c: int) -> None:
        raw = item.data(0, Qt.UserRole)
        if not raw:
            return
        path = Path(raw)
        if path.is_file() and path.suffix.lower() in _IMG_EXTS:
            self.imageActivated.emit(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
