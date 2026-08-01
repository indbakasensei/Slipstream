"""ActivityFeed — the rich, time-stamped event feed on the Dashboard.

Replaces the flat QListWidget rows with a polished feed where every event is a
small row of its own: a coloured status dot, a description line and a faint
timestamp. Newest events are prepended (so the list reads top-down), and the
feed is capped at a fixed number of rows so the panel never grows unbounded.

The internal :class:`QListWidget` is exposed as ``.list`` and the row count as
the ``count`` property so existing callers that relied on the raw widget
(``DashboardPanel.recent``, ``.count()``) keep working unchanged. Timestamps are
generated at display time — purely presentation, no backend logs are touched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QListWidget,
                               QListWidgetItem, QSizePolicy, QVBoxLayout,
                               QWidget)

from gui import theme

# event kind -> (glyph, colour)
_KIND = {
    "info": ("•", theme.INFO),
    "started": ("▶", theme.ACCENT),
    "done": ("✓", theme.SUCCESS),
    "failed": ("✗", theme.ERROR),
}


class ActivityFeed(QWidget):
    """Icon + timestamp + description event rows, newest first."""

    MAX_ROWS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.setSelectionMode(QListWidget.NoSelection)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.list)

    # ------------------------------------------------------------------ #
    @property
    def count(self) -> int:
        return self.list.count()

    def clear(self) -> None:
        self.list.clear()

    def push(self, text: str, kind: str = "info",
             color: Optional[str] = None) -> None:
        """Prepend one event row. ``kind`` selects the dot glyph/colour;
        an explicit ``color`` overrides it."""
        glyph, dot = _KIND.get(kind, _KIND["info"])
        colour = color or dot

        item = QListWidgetItem()
        item.setData(Qt.UserRole, text)          # keeps the raw text queryable

        row = self._row(glyph, colour, text)
        item.setSizeHint(QSize(0, row.sizeHint().height()))
        self.list.insertItem(0, item)
        self.list.setItemWidget(item, row)

        while self.list.count() > self.MAX_ROWS:
            self.list.takeItem(self.list.count() - 1)

    # ------------------------------------------------------------------ #
    def _row(self, glyph: str, colour: str, text: str) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(theme.SPACE_SM, 2, theme.SPACE_SM, 2)
        lay.setSpacing(theme.SPACE_MD)

        # status dot: small rounded square with the kind glyph
        dot = QLabel(glyph)
        dot.setFixedSize(22, 22)
        dot.setAlignment(Qt.AlignCenter)
        dot.setStyleSheet(
            f"color:#ffffff; background:{colour}; border-radius:4px;"
            f"font-weight:700; font-size:11px;")
        lay.addWidget(dot, 0, Qt.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        desc = QLabel(text)
        desc.setProperty("heroDesc", True)
        desc.setWordWrap(True)
        texts.addWidget(desc)
        ts = QLabel(datetime.now().strftime("%H:%M:%S"))
        ts.setProperty("kpiCaption", True)
        texts.addWidget(ts)
        lay.addLayout(texts, 1)

        return row
