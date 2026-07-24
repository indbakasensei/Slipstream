"""StatusChip — a small pill label that colour-codes a state.

Used for the Monitor's solver status ("Idle / Running / Converged / Failed")
and anywhere a compact, colour-coded state indicator reads better than plain
text. Colours come from the shared status palette in :mod:`gui.theme`.

Presentation-only.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel

from gui import theme


class StatusChip(QLabel):
    def __init__(self, text: str = "Idle", color: str = None, parent=None):
        super().__init__(parent)
        self.setProperty("badge", True)
        self.set_state(text, color)

    def set_state(self, text: str, color: str = None) -> None:
        """Set the chip's label and colour. ``color`` may be a status token
        (``"RUNNING"``) or a hex string; defaults to a neutral grey."""
        self.setText(text)
        col = QColor(theme.STATUS_COLORS.get(color, color)
                     if color else theme.TEXT_DIM)
        tint = QColor(col); tint.setAlpha(38)
        self.setStyleSheet(
            f"color: {col.name()}; background: rgba("
            f"{tint.red()},{tint.green()},{tint.blue()},0.15);"
            f"border: 1px solid {col.name()};")
