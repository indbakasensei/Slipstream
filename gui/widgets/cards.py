"""Small dashboard stat card: big number, small caption, optional accent."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from gui import theme


class StatCard(QFrame):
    def __init__(self, title: str, color: str | None = None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            f"QFrame{{background:{theme.BG_PANEL};border:1px solid "
            f"{theme.BORDER};border-radius:8px;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.value_lbl = QLabel("–")
        f = self.value_lbl.font(); f.setPointSize(20); f.setBold(True)
        self.value_lbl.setFont(f)
        if color:
            self.value_lbl.setStyleSheet(f"color:{color};")
        cap = QLabel(title)
        cap.setProperty("h2", True)
        cap.setAlignment(Qt.AlignLeft)
        lay.addWidget(self.value_lbl)
        lay.addWidget(cap)

    def set_value(self, text: str) -> None:
        self.value_lbl.setText(text)
