"""WorkspaceHeader — the workspace chrome above the center page stack.

Composes a :class:`PageHeader` with the current page's icon + title and a
one-line context subtitle ("project · template · schedule"). The main window
drives it: ``set_page()`` on navigation, ``set_context()`` whenever the
project/template changes. Purely presentational.

v2.2 Stage 5 — Adaptive Workspace: the header gains two compact workspace
controls on the right edge:

* **Queue toggle** — show/hide the secondary Queue panel so the center
  workspace can reclaim its horizontal space.
* **Focus toggle** — hide all secondary/utility UI (Sidebar, Queue, docks)
  and give the current primary workspace the full window.

Both are presentation-only: they emit a signal and MainWindow owns the layout
state machine. The focus button's tooltip/accessible label follows the current
primary workspace page (Charts → "Focus Charts", Images → "Focus Images", …)
and is disabled until a project is loaded.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QPushButton

from gui import theme
from gui.widgets import make_icon
from gui.widgets.page_header import PageHeader

# Focus-button tooltip per primary workspace page (presentation-only labels;
# no template-specific branching — every page maps through this table).
_FOCUS_LABELS = {
    "dashboard": "Focus Workspace",
    "results": "Focus Workspace",
    "charts": "Focus Charts",
    "images": "Focus Images",
    "monitor": "Focus Monitor",
}


class WorkspaceHeader(PageHeader):
    queueToggleRequested = Signal()
    focusToggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(icon="", parent=parent)
        self.page_id: str = ""

        self.queue_btn = self._make_toggle(
            "queue", "Toggle Queue", "Hide the Queue to reclaim workspace")
        self.focus_btn = self._make_toggle(
            "zoom", "Focus Workspace", self._focus_tip("dashboard"))
        self.focus_btn.setEnabled(False)     # no project yet → no Focus Mode

        row = self.layout()
        row.addSpacing(theme.SPACE_MD)
        row.addWidget(self.queue_btn, 0, Qt.AlignVCenter)
        row.addSpacing(theme.SPACE_XS)
        row.addWidget(self.focus_btn, 0, Qt.AlignVCenter)

        self.queue_btn.clicked.connect(self.queueToggleRequested.emit)
        self.focus_btn.clicked.connect(self.focusToggleRequested.emit)

    def _make_toggle(self, icon: str, accessible: str, tip: str) -> QPushButton:
        btn = QPushButton()
        btn.setProperty("headerToggle", True)
        btn.setIcon(make_icon(icon, theme.TEXT_DIM))
        btn.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE, theme.TOOLBAR_ICON_SIZE))
        btn.setFixedSize(theme.HEADER_TOGGLE_SIZE + 4,
                         theme.HEADER_TOGGLE_SIZE + 4)
        btn.setToolTip(tip)
        btn.setAccessibleName(accessible)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    # ------------------------------------------------------------------ #
    # Presentation state driven by MainWindow (never mutated here)
    # ------------------------------------------------------------------ #
    def set_queue_visible(self, visible: bool) -> None:
        """Reflect whether the Queue is shown (the toggle is "on" while it is)."""
        self.queue_btn.setProperty("active", visible)
        self.queue_btn.setToolTip(
            "Hide the Queue to reclaim workspace" if visible
            else "Show the Queue")
        self._polish(self.queue_btn)

    def set_focus_active(self, active: bool) -> None:
        """Reflect Focus Mode state; while active the Queue toggle is disabled
        because the Queue is managed by Focus Mode."""
        self.focus_btn.setProperty("active", active)
        self.focus_btn.setToolTip(
            "Exit Focus Mode — restore the previous layout" if active
            else self._focus_tip(self.page_id))
        self.queue_btn.setEnabled(not active)
        self._polish(self.focus_btn)
        self._polish(self.queue_btn)

    def set_focus_enabled(self, enabled: bool) -> None:
        """Focus requires a loaded project."""
        self.focus_btn.setEnabled(enabled)

    def set_focus_label(self, page_id: str) -> None:
        """Update the focus tooltip for the current primary workspace page."""
        if not self.focus_btn.property("active"):
            self.focus_btn.setToolTip(self._focus_tip(page_id))

    @staticmethod
    def _focus_tip(page_id: str) -> str:
        return _FOCUS_LABELS.get(page_id, "Focus Workspace")

    @staticmethod
    def _polish(widget: QPushButton) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    # ------------------------------------------------------------------ #
    # PageHeader API preserved
    # ------------------------------------------------------------------ #
    def set_page(self, page_id: str, title: str) -> None:
        """Switch the leading icon + title to ``page_id``/``title``."""
        self.page_id = page_id
        self.set_title(title)
        self.set_icon(page_id)          # icon name == page id (plugin pages
                                        # with unknown icons render text-only)
        self.set_focus_label(page_id)

    def set_context(self, project: str, template: str, schedule: str = "") -> None:
        """Update the subtitle context line. Empty pieces are omitted."""
        bits = []
        if project:
            bits.append(f"Project: {project}")
        if template:
            bits.append(f"Template: {template}")
        if schedule:
            bits.append(f"Schedule: {schedule}")
        self.set_subtitle("   ·   ".join(bits))
