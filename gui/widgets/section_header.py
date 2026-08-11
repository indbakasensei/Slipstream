"""SectionHeader — a small, reusable title bar used at the top of every
dashboard/panel section (Neo v2.2).

Consistent typography and spacing everywhere it's used, instead of each
panel hand-rolling its own QLabel + separator. Purely presentational —
no signals, no state.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui import theme
from gui.widgets.icons import make_icon


class SectionHeader(QWidget):
    """``icon`` is an optional single glyph/emoji, matching this app's
    existing convention of Unicode-glyph icons (✓/✗/⚠/▶) rather than icon
    font/resource files. ``icon_name`` is the preferred alternative: a painted
    :func:`gui.widgets.icons.make_icon` name, used where a vector icon exists.
    ``separator`` draws a thin rule below the title."""

    def __init__(self, title: str, icon: Optional[str] = None,
                 icon_name: Optional[str] = None,
                 separator: bool = True, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(theme.SPACE_XS)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(theme.SPACE_SM)
        if icon:
            icon_lbl = QLabel(icon)
            icon_lbl.setProperty("h2", True)
            row.addWidget(icon_lbl)
        elif icon_name:
            ic = make_icon(icon_name, theme.TEXT_DIM, 14)
            if ic is not None:
                icon_lbl = QLabel()
                icon_lbl.setPixmap(ic.pixmap(14, 14))
                row.addWidget(icon_lbl)
        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("h2", True)
        row.addWidget(self.title_lbl)
        row.addStretch(1)
        outer.addLayout(row)

        if separator:
            rule = QFrame()
            rule.setFrameShape(QFrame.HLine)
            rule.setStyleSheet(f"background: {theme.BORDER}; max-height: 1px;"
                              f"border: none;")
            outer.addWidget(rule)

    def set_title(self, text: str) -> None:
        self.title_lbl.setText(text)
