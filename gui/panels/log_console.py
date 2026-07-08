"""Log console — the terminal, domesticated.

Receives formatted records from :class:`gui.event_bridge.QtLogHandler`,
colour-codes by level, keeps a bounded scrollback, and offers a minimum-level
filter so INFO chatter can be hidden during a long batch.
"""

from __future__ import annotations

import html
import logging

from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

_LEVEL_COLOR = {logging.DEBUG: "#7f8695", logging.INFO: "#d7dae0",
                logging.WARNING: "#e8a33d", logging.ERROR: "#e5534b",
                logging.CRITICAL: "#ff6b63"}


class LogConsolePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_level = logging.INFO

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Min level:"))
        self.level_box = QComboBox()
        self.level_box.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_box.setCurrentText("INFO")
        self.level_box.currentTextChanged.connect(
            lambda t: setattr(self, "min_level", getattr(logging, t)))
        bar.addWidget(self.level_box)
        self.autoscroll = QCheckBox("Auto-scroll")
        self.autoscroll.setChecked(True)
        bar.addWidget(self.autoscroll)
        bar.addStretch(1)
        clear = QPushButton("Clear")
        clear.clicked.connect(lambda: self.text.clear())
        bar.addWidget(clear)

        self.text = QPlainTextEdit(readOnly=True)
        self.text.setMaximumBlockCount(6000)      # bounded scrollback

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addLayout(bar)
        lay.addWidget(self.text)

    def append(self, level: int, line: str) -> None:
        if level < self.min_level:
            return
        color = _LEVEL_COLOR.get(level, "#d7dae0")
        self.text.appendHtml(
            f'<span style="color:{color}">{html.escape(line)}</span>')
        if self.autoscroll.isChecked():
            sb = self.text.verticalScrollBar()
            sb.setValue(sb.maximum())
