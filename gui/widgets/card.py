"""Card — the one elevated-surface container of the Neo design system.

A titled, padded, rounded surface used across the Dashboard, Monitor, and
Parameters screens so every grouped block looks identical: same radius, same
border, same header treatment, same internal padding (all from
:mod:`gui.theme` tokens). Give it a title (and optional caption / header
accessory) and add content widgets to ``body``.

Presentation-only: pure layout, no signals, no business logic.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout,
                               QWidget)

from gui import theme


class Card(QFrame):
    """An elevated card: optional header (title + caption + right-side
    accessory) over a ``body`` content area."""

    def __init__(self, title: str = "", caption: str = "",
                 hero: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        if hero:
            self.setProperty("hero", True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.CARD_MARGIN, theme.CARD_MARGIN,
                                 theme.CARD_MARGIN, theme.CARD_MARGIN)
        outer.setSpacing(theme.SPACE_MD)

        # -- header (only built when there is a title) -------------------- #
        self._header: Optional[QHBoxLayout] = None
        self.title_lbl: Optional[QLabel] = None
        self.caption_lbl: Optional[QLabel] = None
        if title or caption:
            head = QHBoxLayout()
            head.setSpacing(theme.SPACE_SM)
            titles = QVBoxLayout()
            titles.setSpacing(0)
            if title:
                self.title_lbl = QLabel(title)
                self.title_lbl.setProperty("h1", True)
                titles.addWidget(self.title_lbl)
            if caption:
                self.caption_lbl = QLabel(caption)
                self.caption_lbl.setProperty("caption", True)
                titles.addWidget(self.caption_lbl)
            head.addLayout(titles, 1)
            self._accessory_host = QHBoxLayout()
            self._accessory_host.setSpacing(theme.SPACE_SM)
            head.addLayout(self._accessory_host, 0)
            outer.addLayout(head)
            self._header = head

        # -- body --------------------------------------------------------- #
        self.body = QVBoxLayout()
        self.body.setSpacing(theme.SPACE_SM)
        outer.addLayout(self.body, 1)

    # ------------------------------------------------------------------ #
    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        """Add a widget to the card body; returns it for chaining."""
        self.body.addWidget(widget, stretch)
        return widget

    def add_layout(self, layout, stretch: int = 0):
        self.body.addLayout(layout, stretch)
        return layout

    def set_accessory(self, widget: QWidget) -> None:
        """Place a small widget (e.g. a status chip) on the right of the
        header. No-op if the card was created without a header."""
        if self._header is not None:
            self._accessory_host.addWidget(widget)

    def set_title(self, text: str) -> None:
        if self.title_lbl is not None:
            self.title_lbl.setText(text)

    def set_caption(self, text: str) -> None:
        if self.caption_lbl is not None:
            self.caption_lbl.setText(text)
