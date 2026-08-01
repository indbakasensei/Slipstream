"""NavigationButton — the nav item used by the sidebar (and any future rail).

A checkable :class:`QPushButton` that pairs a theme-coloured icon with a
label and an accent "active rail" (drawn by the ``navItem`` QSS rule). It is
deliberately a thin subclass — ``click()``, ``isChecked()``, ``setChecked()``
and the ``clicked`` signal all behave exactly like a plain QPushButton, which
is what the sidebar's existing behavioral tests rely on.

``set_active()`` is the one method panels/sidebars call: it flips the checked
state, the ``active`` QSS property (rail + tint), and recolors the icon
(``ACCENT`` when active, ``TEXT_DIM`` otherwise).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QStyle

from gui import theme
from gui.widgets.icons import make_icon


class NavigationButton(QPushButton):
    def __init__(self, label: str, icon: str = "", parent=None):
        super().__init__(label, parent)
        self.setProperty("navItem", True)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(theme.NAV_ITEM_HEIGHT)
        self._icon_name = icon
        self._apply_icon()
        # Keep a standalone button coherent when clicked outside the sidebar.
        self.clicked.connect(lambda: self.set_active(self.isChecked()))

    # ------------------------------------------------------------------ #
    def set_active(self, active: bool) -> None:
        """Mark this item as the active one (checked + rail + accent icon)."""
        self.setChecked(active)
        self.setProperty("active", active)
        self._apply_icon()
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def _apply_icon(self) -> None:
        icon = make_icon(self._icon_name, theme.ACCENT if self.property("active")
                         else theme.TEXT_DIM, theme.TOOLBAR_ICON_SIZE)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE,
                                   theme.TOOLBAR_ICON_SIZE))
