"""ToolbarSection — a reusable control group (buttons/spins) in one surface.

A subtle field-toned container with consistent internal spacing, used for
grouping related controls (e.g. the Queue's Run controls) so a set of
buttons reads as one unit instead of floating widgets. Purely presentational.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from gui import theme
from gui.widgets.flow_layout import FlowLayout


class ToolbarSection(QFrame):
    def __init__(self, title: Optional[str] = None, parent=None,
                 wrap: bool = False):
        super().__init__(parent)
        self.setProperty("toolGroup", True)

        # `wrap` installs a FlowLayout so the section reflows onto extra rows
        # (growing taller) instead of crushing its children when the available
        # width runs out — used by the Queue's Run row (Stage 6).
        if wrap:
            lay = FlowLayout()
            self.setLayout(lay)
        else:
            lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_XS, theme.SPACE_XS,
                               theme.SPACE_XS, theme.SPACE_XS)
        lay.setSpacing(theme.SPACE_XS)

        if title:
            cap = QLabel(title)
            cap.setProperty("toolbarGroup", True)
            lay.addWidget(cap)

    def add(self, widget: QWidget) -> None:
        self.layout().addWidget(widget)

    def add_spacing(self, px: int) -> None:
        self.layout().addSpacing(px)
