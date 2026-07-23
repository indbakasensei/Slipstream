"""Sidebar — navigation only (GUI Modernization, v1.0.0-rc2).

Architecture (deliberately one-way):

    Sidebar --pageRequested(page_id)--> MainWindow --> QStackedWidget

The sidebar never touches a page/panel directly and never imports
anything from ``gui.panels`` — it only emits which page was requested;
MainWindow owns switching the center stack. This keeps navigation fully
decoupled from the workspace pages themselves.

The "Project" section embeds the *existing* ``ExplorerPanel`` instance
unchanged (passed in by the caller) — this widget does not reimplement
any of that tree/file logic, it only provides the collapsible section
chrome around it.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui import theme
from gui.widgets.collapsible_section import CollapsibleSection

# (page_id, label, icon) — icons follow this app's existing convention of
# single Unicode glyphs (✓/✗/⚠/▶ elsewhere) rather than icon resource files.
WORKSPACE_PAGES: List[Tuple[str, str, str]] = [
    ("dashboard", "Dashboard", "▦"),
    ("results", "Results", "▤"),
    ("charts", "Charts", "📈"),
    ("images", "Images", "🖼"),
]


class Sidebar(QWidget):
    pageRequested = Signal(str)      # one of WORKSPACE_PAGES's page_id

    def __init__(self, explorer_widget: QWidget, parent=None):
        super().__init__(parent)
        self._nav_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM,
                                 theme.SPACE_SM, theme.SPACE_SM)
        outer.setSpacing(theme.SPACE_MD)

        # -- Workspace: page navigation ------------------------------------
        nav_body = QWidget()
        nav_lay = QVBoxLayout(nav_body)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(theme.SPACE_XS)
        for page_id, label, icon in WORKSPACE_PAGES:
            btn = QPushButton(f"{icon}   {label}")
            btn.setProperty("flat", True)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked, pid=page_id: self._select(pid))
            nav_lay.addWidget(btn)
            self._nav_buttons[page_id] = btn
        self.workspace_section = CollapsibleSection("Workspace", nav_body)

        # -- Project: existing ExplorerPanel, unchanged --------------------
        self.project_section = CollapsibleSection("Project", explorer_widget)

        outer.addWidget(self.workspace_section)
        outer.addWidget(self.project_section, 1)

        if WORKSPACE_PAGES:
            self._select(WORKSPACE_PAGES[0][0], emit=False)

    # ------------------------------------------------------------------ #
    def _select(self, page_id: str, emit: bool = True) -> None:
        for pid, btn in self._nav_buttons.items():
            active = pid == page_id
            btn.setChecked(active)
            btn.setProperty("active", active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        if emit:
            self.pageRequested.emit(page_id)

    def current_page(self) -> str:
        for pid, btn in self._nav_buttons.items():
            if btn.isChecked():
                return pid
        return ""
