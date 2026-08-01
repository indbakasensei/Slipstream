"""KpiCard — the premium KPI tile of the Dashboard Revolution.

A status-coloured accent bar, an icon, a large number and a caption make up a
single self-contained tile. It *keeps the StatCard public surface* (``value_lbl``
and ``set_value()``) so ``DashboardPanel.cards`` and every existing caller keeps
working, but it is visually a different, more premium object:

* top accent bar tinted with the status colour (KPI_ACCENT_HEIGHT px);
* optional monochrome icon drawn by the shared IconFactory;
* large value (KPI_VALUE_FONT_SIZE) with a smaller caption beneath;
* optional trend hint (``set_trend``) rendered in green/red.

Presentation-only: no signals, no business logic.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from gui import theme
from gui.widgets.icons import make_icon


class KpiCard(QFrame):
    """A StatCard-compatible KPI tile with icon + accent bar + trend hint."""

    def __init__(self, title: str, color: Optional[str] = None,
                 icon: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.setProperty("kpiCard", True)
        self.setMinimumHeight(112)
        self.setMinimumWidth(150)

        self._color = color or theme.TEXT_DIM

        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.CARD_MARGIN, 0, theme.CARD_MARGIN,
                               theme.CARD_MARGIN)
        lay.setSpacing(0)

        # -- status accent bar (coloured strip at the very top) ----------- #
        self.accent = QFrame()
        self.accent.setFixedHeight(theme.KPI_ACCENT_HEIGHT)
        self.accent.setStyleSheet(
            f"background:{self._color}; border:none; border-radius:0px;")
        lay.addWidget(self.accent)

        # -- body: icon + value/caption ------------------------------------ #
        body = QHBoxLayout()
        body.setContentsMargins(0, theme.SPACE_MD, 0, 0)
        body.setSpacing(theme.SPACE_MD)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(theme.KPI_ICON_SIZE * 2 + 8,
                                   theme.KPI_ICON_SIZE * 2 + 8)
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self._set_icon(icon)
        body.addWidget(self.icon_lbl, 0, Qt.AlignTop)

        texts = QVBoxLayout()
        texts.setSpacing(0)

        self.value_lbl = QLabel("–")
        self.value_lbl.setProperty("kpiValue", True)
        texts.addWidget(self.value_lbl)

        self.caption_lbl = QLabel(title)
        self.caption_lbl.setProperty("kpiCaption", True)
        texts.addWidget(self.caption_lbl)

        self.trend_lbl = QLabel("")
        self.trend_lbl.setProperty("kpiCaption", True)
        texts.addWidget(self.trend_lbl)

        body.addLayout(texts, 1)
        lay.addLayout(body, 1)

    # ------------------------------------------------------------------ #
    def _set_icon(self, name: Optional[str]) -> None:
        icon: Optional[QIcon] = None
        if name:
            icon = make_icon(name, theme.TEXT_DIM, theme.KPI_ICON_SIZE)
        if icon is not None:
            self.icon_lbl.setPixmap(icon.pixmap(theme.KPI_ICON_SIZE * 2,
                                                theme.KPI_ICON_SIZE * 2))
        else:
            self.icon_lbl.hide()

    def set_value(self, text: str) -> None:
        """StatCard-compatible setter — updates the big number."""
        self.value_lbl.setText(text)

    def set_icon(self, name: Optional[str]) -> None:
        """Swap the tile icon at runtime (None hides it)."""
        self._set_icon(name)

    def set_trend(self, text: str, positive: bool = True) -> None:
        """Show an optional trend hint under the caption."""
        if not text:
            self.trend_lbl.clear()
            self.trend_lbl.hide()
            return
        colour = theme.SUCCESS if positive else theme.ERROR
        self.trend_lbl.setText(text)
        self.trend_lbl.setStyleSheet(f"color:{colour};")
        self.trend_lbl.show()
