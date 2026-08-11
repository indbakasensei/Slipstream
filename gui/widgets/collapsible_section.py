"""CollapsibleSection — a reusable, toggle-able container (Neo v2.2).

Used for anything that shouldn't permanently occupy screen space when
empty/inactive — the canonical case being the Study Summary's warnings
list. The wrapped content widget is unaffected by collapsing: it keeps
existing, keeps its data, and remains fully inspectable by tests — only
its *visibility* toggles. This is deliberately dumb: no animation, no
persistence beyond the current session, just a toggle button and a
QWidget.setVisible() call.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from gui import theme


class CollapsibleSection(QWidget):
    """Wrap ``content`` (any QWidget, added via :meth:`set_content` or at
    construction) behind a clickable header that toggles its visibility.
    """

    toggled = Signal(bool)          # emits the new expanded state

    def __init__(self, title: str, content: QWidget = None,
                start_expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = start_expanded

        self._toggle_btn = QPushButton()
        self._toggle_btn.setProperty("flat", True)
        # Neo (v2.1): uppercase caption header chrome, consistent with the
        # sidebar's section labels (behavior untouched — still a toggle button).
        self._toggle_btn.setProperty("sectionHeader", True)
        self._toggle_btn.setCursor(Qt.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._on_clicked)

        self._title = title
        self._content: QWidget = content or QWidget()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.SPACE_XS)
        lay.addWidget(self._toggle_btn)
        lay.addWidget(self._content)

        self._sync()

    # ------------------------------------------------------------------ #
    def set_content(self, content: QWidget) -> None:
        layout = self.layout()
        layout.replaceWidget(self._content, content)
        self._content.setParent(None)
        self._content = content
        self._content.setVisible(self._expanded)

    def set_title(self, title: str) -> None:
        self._title = title
        self._sync()

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._sync()
        self.toggled.emit(self._expanded)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    # ------------------------------------------------------------------ #
    def _on_clicked(self) -> None:
        self.toggle()

    def _sync(self) -> None:
        chevron = "▾" if self._expanded else "▸"
        self._toggle_btn.setText(f"{chevron}  {self._title}")
        self._content.setVisible(self._expanded)
