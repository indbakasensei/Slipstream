"""Sidebar — premium engineering navigation (Neo UI v2, Workspace Revolution).

Architecture (deliberately one-way, unchanged from the modernized shell):

    Sidebar --pageRequested(page_id)--> MainWindow --> QStackedWidget

The sidebar never touches a page/panel directly and never imports anything
from ``gui.panels`` — it only emits which page was requested; MainWindow owns
switching the center stack. This keeps navigation fully decoupled from the
workspace pages themselves.

Neo structure (v2.1), top → bottom:

* :class:`BrandHeader` — SLIPSTREAM wordmark + version chip.
* Workspace — collapsible section of :class:`NavigationButton` items (painted
  icons + accent active rail); the *only* thing that changed is the chrome,
  every public attribute/behavior the app and tests rely on is preserved
  (``pageRequested``, ``_nav_buttons`` keyed by page_id, ``current_page()``,
  ``_select()``, auto-select-first-page, both sections as CollapsibleSections).
* Project — the *existing* ``ExplorerPanel`` instance embedded unchanged.

Search-ready: :meth:`set_search_widget` inserts a search field above the
Workspace list; it is intentionally empty by default (no dead chrome).
Plugin-ready: ``WORKSPACE_PAGES`` is the page registry — a new page appears
automatically (pages with no icon yet render text-only).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui import theme
from gui.widgets.brand_header import BrandHeader
from gui.widgets.collapsible_section import CollapsibleSection
from gui.widgets.nav_button import NavigationButton

# (page_id, label, icon) — the icon field is kept for backward compatibility
# with any reader of WORKSPACE_PAGES; the sidebar renders its own painted
# icons (see icons.py) keyed by page_id instead of these legacy glyphs.
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
        self._nav_buttons: dict[str, NavigationButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.SPACE_SM, theme.SPACE_SM,
                                 theme.SPACE_SM, theme.SPACE_SM)
        outer.setSpacing(theme.SPACE_MD)

        # -- brand ---------------------------------------------------------- #
        outer.addWidget(BrandHeader())

        # -- search-ready seam (empty by default) --------------------------- #
        self.search_slot: Optional[QWidget] = None

        # -- Workspace: page navigation ------------------------------------- #
        nav_body = QWidget()
        nav_lay = QVBoxLayout(nav_body)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(theme.SPACE_XS)
        for page_id, label, _icon in WORKSPACE_PAGES:
            btn = NavigationButton(label, icon=page_id)
            btn.clicked.connect(lambda _checked, pid=page_id: self._select(pid))
            nav_lay.addWidget(btn)
            self._nav_buttons[page_id] = btn
        self.workspace_section = CollapsibleSection("Workspace", nav_body)

        # -- Project: existing ExplorerPanel, unchanged ---------------------- #
        self.project_section = CollapsibleSection("Project", explorer_widget)

        outer.addWidget(self.workspace_section)
        outer.addWidget(self.project_section, 1)

        if WORKSPACE_PAGES:
            self._select(WORKSPACE_PAGES[0][0], emit=False)

    # ------------------------------------------------------------------ #
    def set_search_widget(self, widget: Optional[QWidget]) -> None:
        """Insert (or clear) a search field above the Workspace list. The
        layout seam is always present; this just fills it."""
        if self.search_slot is not None:
            self.layout().removeWidget(self.search_slot)
            self.search_slot.deleteLater()
            self.search_slot = None
        if widget is not None:
            self.layout().insertWidget(1, widget)
            self.search_slot = widget

    def _select(self, page_id: str, emit: bool = True) -> None:
        for pid, btn in self._nav_buttons.items():
            active = pid == page_id
            btn.set_active(active)
        if emit:
            self.pageRequested.emit(page_id)

    def current_page(self) -> str:
        for pid, btn in self._nav_buttons.items():
            if btn.isChecked():
                return pid
        return ""
