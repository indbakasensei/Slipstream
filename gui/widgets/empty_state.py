"""EmptyState — a centered "nothing to show yet" placeholder page.

Used as the startup / no-project screen (title + hint + optional accent
action button) and reusable anywhere a blank page would otherwise appear.
Purely presentational; the action button only emits :attr:`actionClicked`.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from gui import theme
from gui.widgets.icons import make_icon


class EmptyState(QWidget):
    actionClicked = Signal()

    def __init__(self, title: str, hint: str,
                 action_text: Optional[str] = None, icon: str = "logo",
                 parent=None):
        super().__init__(parent)
        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("emptyTitle", True)
        self.hint_lbl = QLabel(hint)
        self.hint_lbl.setProperty("emptyHint", True)
        self.hint_lbl.setAlignment(Qt.AlignCenter)
        self.hint_lbl.setWordWrap(True)

        mark = QLabel()
        drawn = make_icon(icon, theme.ACCENT, 56)
        if drawn is not None:
            mark.setPixmap(drawn.pixmap(56, 56))

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(theme.SPACE_MD)
        lay.addWidget(mark, 0, Qt.AlignCenter)
        lay.addWidget(self.title_lbl, 0, Qt.AlignCenter)
        lay.addWidget(self.hint_lbl, 0, Qt.AlignCenter)

        if action_text:
            self.action_btn = QPushButton(action_text)
            self.action_btn.setProperty("accent", True)
            self.action_btn.setCursor(Qt.PointingHandCursor)
            self.action_btn.clicked.connect(self.actionClicked)
            lay.addSpacing(theme.SPACE_SM)
            lay.addWidget(self.action_btn, 0, Qt.AlignCenter)
