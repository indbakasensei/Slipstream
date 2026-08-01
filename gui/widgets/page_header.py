"""PageHeader — the reusable title bar for a workspace page.

h1 title + optional subtitle (project · template · schedule context) plus an
optional right-side accessory. Used directly by the WorkspaceHeader in the
main window and reusable by any future page/panel that wants a consistent
title treatment.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from gui import theme
from gui.widgets.icons import make_icon


class PageHeader(QWidget):
    def __init__(self, title: str = "", subtitle: str = "", icon: str = "",
                 parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setProperty("pageHeader", True)
        self.setMinimumHeight(theme.PAGE_HEADER_HEIGHT)

        self.title_lbl = QLabel(title)
        self.title_lbl.setProperty("h1", True)
        self.subtitle_lbl = QLabel(subtitle)
        self.subtitle_lbl.setProperty("hint", True)
        self.subtitle_lbl.setWordWrap(True)

        titles = QVBoxLayout()
        titles.setSpacing(theme.SPACE_XS)
        titles.addWidget(self.title_lbl)
        titles.addWidget(self.subtitle_lbl)

        row = QHBoxLayout(self)
        row.setContentsMargins(theme.SPACE_LG, theme.SPACE_MD,
                               theme.SPACE_LG, theme.SPACE_MD)
        row.setSpacing(theme.SPACE_MD)

        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(theme.TOOLBAR_ICON_SIZE + 8,
                                   theme.TOOLBAR_ICON_SIZE + 8)
        if icon:
            self.set_icon(icon)
        row.addWidget(self.icon_lbl, 0, Qt.AlignTop)
        self.icon_lbl.setVisible(bool(icon))
        row.addLayout(titles, 1)
        self._accessory: Optional[QWidget] = None
        row.addStretch(0)

    def set_icon(self, icon: str) -> None:
        drawn = make_icon(icon, theme.ACCENT, theme.TOOLBAR_ICON_SIZE)
        if drawn is not None:
            self.icon_lbl.setPixmap(drawn.pixmap(theme.TOOLBAR_ICON_SIZE,
                                                 theme.TOOLBAR_ICON_SIZE))
            self.icon_lbl.setVisible(True)

    # ------------------------------------------------------------------ #
    def set_title(self, text: str) -> None:
        self.title_lbl.setText(text)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_lbl.setText(text)
        self.subtitle_lbl.setVisible(bool(text))

    def set_accessory(self, widget: Optional[QWidget]) -> None:
        """Place ``widget`` on the right edge (previous accessory removed)."""
        if self._accessory is not None:
            self.layout().removeWidget(self._accessory)
            self._accessory.deleteLater()
        if widget is not None:
            self.layout().addWidget(widget, 0, Qt.AlignVCenter)
        self._accessory = widget
