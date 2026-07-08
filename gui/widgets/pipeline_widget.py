"""Pipeline visualization — the CFD workflow as coloured stage chips.

Geometry+Mesh → Launch → Setup → Init → Solve → Extract, each chip coloured
by state (idle/start/done/cached/skip/failed). Driven directly by the
engine's ``stage`` events; ``compact=True`` renders a slimmer strip for the
dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui import theme

# (engine stage key, display label)
STAGES = [
    ("mesh", "Geometry+Mesh"),
    ("fluent_launch", "Fluent"),
    ("setup", "Setup"),
    ("initialize", "Init"),
    ("solve", "Solve"),
    ("extract", "Extract"),
]
_IGNORED = {"read_case", "replace_mesh"}   # folded into Fluent/Setup visually


class PipelineWidget(QWidget):
    def __init__(self, compact: bool = False, parent=None):
        super().__init__(parent)
        self.compact = compact
        self.states = {k: "idle" for k, _ in STAGES}
        h = 34 if compact else 46
        self.setMinimumHeight(h)
        self.setMaximumHeight(h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    # -- API ------------------------------------------------------------ #
    def reset(self) -> None:
        self.states = {k: "idle" for k, _ in STAGES}
        self.update()

    def set_stage(self, stage: str, state: str) -> None:
        if stage in _IGNORED:
            return
        if stage in self.states:
            # a chip already 'done' never regresses to 'start' on retries
            if state == "start" and self.states[stage] in ("done", "cached"):
                return
            self.states[stage] = state
            self.update()

    def mark_active_failed(self) -> None:
        """Colour whichever chip is currently 'start' as failed."""
        for k, v in self.states.items():
            if v == "start":
                self.states[k] = "failed"
        self.update()

    # -- painting --------------------------------------------------------#
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = len(STAGES)
        gap = 16
        w = (self.width() - gap * (n - 1)) / n
        h = self.height() - 8
        y = 4
        font = QFont(self.font())
        font.setPointSizeF(8.5 if not self.compact else 8)
        font.setBold(True)
        p.setFont(font)
        x = 0.0
        for i, (key, label) in enumerate(STAGES):
            state = self.states[key]
            col = theme.qcolor(state)
            rect = QRectF(x, y, w, h)
            fill = QColor(col)
            fill.setAlpha(46 if state == "idle" else 70)
            p.setPen(QPen(col, 1.4))
            p.setBrush(fill)
            p.drawRoundedRect(rect, 7, 7)
            p.setPen(QColor(theme.TEXT if state != "idle" else theme.TEXT_DIM))
            p.drawText(rect, Qt.AlignCenter, label)
            if i < n - 1:                                   # connector arrow
                ax = x + w + 3
                cy = y + h / 2
                p.setPen(QPen(QColor(theme.TEXT_DIM), 1.4))
                p.drawLine(int(ax), int(cy), int(ax + gap - 6), int(cy))
                p.drawLine(int(ax + gap - 10), int(cy - 3),
                           int(ax + gap - 6), int(cy))
                p.drawLine(int(ax + gap - 10), int(cy + 3),
                           int(ax + gap - 6), int(cy))
            x += w + gap
