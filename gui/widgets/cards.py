"""Dashboard stat card: big number, small caption, optional accent colour.

Neo v2.2: restyled to the shared card/spacing design
system in gui/theme.py (larger padding, bigger number, consistent radius)
— the public surface (``value_lbl``, ``set_value()``) is unchanged so
every existing caller/test keeps working exactly as before.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui import theme


class StatCard(QFrame):
    def __init__(self, title: str, color: str | None = None, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setMinimumHeight(96)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                               theme.CARD_MARGIN, theme.CARD_MARGIN)
        lay.setSpacing(theme.SPACE_XS)

        self.value_lbl = QLabel("–")
        self.value_lbl.setProperty("stat", True)
        if color:
            self.value_lbl.setStyleSheet(f"color:{color};")
        cap = QLabel(title)
        cap.setProperty("h2", True)
        cap.setAlignment(Qt.AlignLeft)

        lay.addWidget(self.value_lbl)
        lay.addWidget(cap)

    def set_value(self, text: str) -> None:
        self.value_lbl.setText(text)
