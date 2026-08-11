"""FlowLayout — a wrapping box layout (Stage 6).

A classic Qt flow layout: children are laid left-to-right and wrap onto new
lines when the available width runs out. The Dashboard's KPI row and column
pairs have used one since v2.2; Stage 6 promotes it to a shared widget so the
Queue's filter pills and the Charts toolbar can *reflow instead of crush*
when the workspace is narrow.

This is the mechanism behind the responsive rules: secondary panels never
shrink their controls into unreadable slivers — they wrap, and the wrapping
row grows taller rather than clipping its children.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """Children wrap onto new rows when the available width runs out.

    Each child is placed at its ``sizeHint`` and the row breaks before the
    next child would overflow, so no control is ever compressed below its
    natural size — the layout grows in height instead (``heightForWidth``).
    An item with an ``Expanding`` size policy absorbs the leftover space on
    its line, which lets callers right-align a trailing control without
    losing the wrap behaviour.
    """

    def __init__(self, parent=None, margin: int = 0, hspacing: int = -1,
                 vspacing: int = -1, spacing: int = -1):
        super().__init__(parent)
        self._items = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        if spacing >= 0:
            self.setSpacing(spacing)
        self.setContentsMargins(margin, margin, margin, margin)

    # ------------------------------------------------------------------ #
    # QLayout API
    # ------------------------------------------------------------------ #
    def addItem(self, item):  # noqa: D401
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    # ------------------------------------------------------------------ #
    def _hsp(self) -> int:
        return self._hspacing if self._hspacing >= 0 else self.spacing()

    def _vsp(self) -> int:
        return self._vspacing if self._vspacing >= 0 else self.spacing()

    def _do(self, rect: QRect, test_only: bool) -> int:
        m = self.contentsMargins()
        eff = QRect(rect.x() + m.left(), rect.y() + m.top(),
                    rect.width() - m.left() - m.right(),
                    rect.height() - m.top() - m.bottom())

        # Phase 1 — wrap items into lines using their natural sizeHint widths.
        lines = []                      # (line_y, line_height, [items])
        cur, x, y, line_height = [], eff.x(), eff.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > eff.right() + 1 and line_height > 0:
                lines.append((y, line_height, cur))
                cur = []
                x = eff.x()
                y = y + line_height + self._vsp()
                line_height = 0
            cur.append(item)
            x += hint.width() + self._hsp()
            line_height = max(line_height, hint.height())
        lines.append((y, line_height, cur))

        if not test_only:
            # Phase 2 — lay out each line, giving the leftover width to items
            # that expand horizontally (e.g. an ``addStretch``-style spacer).
            for y0, lh, items in lines:
                widths = [it.sizeHint().width() for it in items]
                used = sum(widths) + self._hsp() * max(0, len(items) - 1)
                expanders = [i for i, it in enumerate(items)
                             if bool(it.expandingDirections()
                                     & Qt.Orientation.Horizontal)]
                if expanders:
                    leftover = max(0, eff.width() - used)
                    share = leftover // len(expanders)
                    for i in expanders:
                        widths[i] += share
                        leftover -= share
                    widths[expanders[0]] += leftover
                xx = eff.x()
                for it, w in zip(items, widths):
                    hint = it.sizeHint()
                    it.setGeometry(QRect(QPoint(xx, y0), QSize(w, hint.height())))
                    xx += w + self._hsp()
        return (y + line_height - eff.y() + m.top() + m.bottom())
