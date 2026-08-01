"""StatusBadgeDelegate — paint a table cell as a rounded status pill.

Attach it to a column (``table.setItemDelegateForColumn(col, delegate)``) and
every cell in that column renders as a colour-coded chip instead of flat
text. The underlying item is **untouched** — text stays for sorting and
selection, tooltips keep working, and `selected_rows()`-style logic keeps
reading items normally. Purely presentational.

``color_fn`` maps a cell's text (e.g. ``"DONE"``) to a colour; the default
uses :data:`gui.theme.STATUS_COLORS` so queue statuses share the exact
palette used by StatusChip and the pipeline.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QStyleOptionViewItem

from gui import theme


def _default_color(text: str) -> str:
    return theme.STATUS_COLORS.get(text, theme.BORDER_STRONG)


class StatusBadgeDelegate(QStyledItemDelegate):
    def __init__(self, color_fn: Optional[Callable[[str], str]] = None,
                 parent=None):
        super().__init__(parent)
        self._color_fn = color_fn or _default_color

    # ------------------------------------------------------------------ #
    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # keep the row's hover/selection highlight behind the chip
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())

        colour = QColor(self._color_fn(str(index.data(Qt.DisplayRole))))
        tint = QColor(colour)
        tint.setAlpha(40)

        r = QRectF(option.rect).adjusted(4, 3, -4, -3)
        pill = QRectF(r.left(), r.top(), r.width(), r.height())

        painter.setPen(Qt.NoPen)
        painter.setBrush(tint)
        painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)

        painter.setPen(QPen(colour, 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(pill, pill.height() / 2, pill.height() / 2)

        painter.setPen(QPen(colour, 1.0))
        painter.setFont(index.data(Qt.FontRole) or option.font)
        painter.drawText(pill, Qt.AlignCenter, str(index.data(Qt.DisplayRole)))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> object:
        return super().sizeHint(option, index)
