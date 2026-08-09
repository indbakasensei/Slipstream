"""QuickActionsPanel — the one-click action grid on the Dashboard.

A compact grid of icon + label buttons that carry out the most common study
tasks directly from the Dashboard, reducing toolbar dependence. Each action is
a simple ``(id, label, icon)`` tuple; clicking any button emits
``actionTriggered(id)`` and the owning screen decides what actually happens —
this panel has no business logic of its own.

``DEFAULT_ACTIONS`` is the standard set used by the Dashboard; screens may pass
their own list instead.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QLabel, QPushButton,
                               QSizePolicy, QVBoxLayout)

from gui import theme
from gui.widgets.icons import make_icon

ActionSpec = Tuple[str, str, Optional[str]]   # (id, label, icon_name)

DEFAULT_ACTIONS: List[ActionSpec] = [
    ("open", "Open Project", "open"),
    ("run", "Run Study", "run"),
    ("resume", "Resume", "resume"),
    ("report", "Generate Report", "report"),
    ("export", "Export Results", "export"),
    ("validate", "Validate Project", "validate"),
    ("config", "Configuration", "settings"),
]


class QuickActionsPanel(QFrame):
    """A titled grid of quick-action buttons emitting ``actionTriggered(id)``."""

    actionTriggered = Signal(str)

    def __init__(self, title: str = "Quick Actions",
                 actions: Sequence[ActionSpec] = DEFAULT_ACTIONS,
                 parent=None):
        super().__init__(parent)
        self.setProperty("dashSection", True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                               theme.CARD_MARGIN, theme.CARD_MARGIN)
        lay.setSpacing(theme.SPACE_MD)

        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("dashSectionTitle", True)
        lay.addWidget(self.title_lbl)

        grid = QGridLayout()
        grid.setSpacing(theme.SPACE_SM)
        self._buttons = {}
        cols = 2
        for i, (aid, label, icon_name) in enumerate(actions):
            btn = self._make_button(aid, label, icon_name)
            self._buttons[aid] = btn
            grid.addWidget(btn, i // cols, i % cols)
        lay.addLayout(grid, 1)

    # ------------------------------------------------------------------ #
    def _make_button(self, aid: str, label: str, icon_name: Optional[str]) -> QPushButton:
        btn = QPushButton(label)
        btn.setProperty("quickAction", True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(theme.QUICK_ACTION_SIZE)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if icon_name:
            ic = make_icon(icon_name, theme.TEXT_DIM, 16)
            if ic is not None:
                btn.setIcon(ic)
        btn.clicked.connect(lambda _=False, a=aid: self.actionTriggered.emit(a))
        return btn

    def set_action_enabled(self, aid: str, enabled: bool) -> None:
        btn = self._buttons.get(aid)
        if btn is not None:
            btn.setEnabled(enabled)
