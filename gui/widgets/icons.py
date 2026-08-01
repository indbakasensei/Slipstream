"""IconFactory — the single source of icons for the Neo UI.

Every icon in the application is painted here with :class:`QPainter` onto a
transparent pixmap: monochrome, vector-style line icons drawn on a 24-unit
grid and scaled to any requested size at a 2x device-pixel ratio so they stay
crisp on HiDPI screens. Icons are **coloured by the caller** from the shared
theme tokens (``theme.TEXT_DIM`` for rest, ``theme.ACCENT`` for active /
primary), so hover and active states recolor without a second icon asset.

Rules this module enforces for the whole app:

* No emoji, no Unicode glyphs, no external icon files — every pixel is drawn.
* A new icon is one small ``_draw`` function registered in ``_ICONS``; unknown
  names return ``None`` so callers degrade gracefully (e.g. a future plugin
  page with no icon yet simply renders text-only).
* Colours come from the caller — this module never imports a widget palette.

The current set covers the nav pages (dashboard/results/charts/images), the
toolbar (open/reload/run/stop/mock) and the brand mark (``logo``).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QPainter, QPainterPath, QPen,
                           QPixmap, QPolygonF)

_GRID = 24.0                     # all drawings are authored on this grid
_DPI = 2.0                       # render 2x, Qt scales down on 1x displays


def _stroke(p: QPainter, c: QColor, s: float) -> None:
    p.setPen(QPen(c, max(1.4, 1.6 * s), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)


def _fill(p: QPainter, c: QColor) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(c)


# ------------------------------------------------------------------------ #
# Individual drawings (each receives the active painter and scale factor)
# ------------------------------------------------------------------------ #
def _logo(p: QPainter, c: QColor, s: float) -> None:
    """Brand mark: a wing-like swoosh (accent-filled) under two air-flow arcs."""
    _fill(p, c)
    path = QPainterPath()
    path.moveTo(3.5 * s, 17.5 * s)
    path.lineTo(20.5 * s, 17.5 * s)
    path.lineTo(12.0 * s, 11.0 * s)
    path.closeSubpath()
    p.drawPath(path)
    _stroke(p, c, s)
    p.drawArc(QRectF(4.0 * s, 3.5 * s, 16.0 * s, 10.0 * s), 200 * 16, 140 * 16)
    p.drawArc(QRectF(6.0 * s, 6.0 * s, 12.0 * s, 10.0 * s), 200 * 16, 140 * 16)


def _dashboard(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    for (x, y) in ((4, 4), (14, 4), (4, 14), (14, 14)):
        p.drawRoundedRect(QRectF(x * s, y * s, 6 * s, 6 * s), 1.5 * s, 1.5 * s)


def _results(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(3 * s, 3.5 * s, 18 * s, 17 * s), 2 * s, 2 * s)
    p.drawLine(3 * s, 8 * s, 21 * s, 8 * s)     # header rule
    p.drawLine(12 * s, 8 * s, 12 * s, 20.5 * s)  # column divider
    p.drawLine(3 * s, 13 * s, 21 * s, 13 * s)   # body rows
    p.drawLine(3 * s, 17 * s, 21 * s, 17 * s)


def _charts(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawLine(4 * s, 20 * s, 20 * s, 20 * s)   # x axis
    p.drawLine(4 * s, 20 * s, 4 * s, 4 * s)     # y axis
    path = QPainterPath(QPointF(5 * s, 17 * s))
    path.lineTo(9 * s, 12 * s)
    path.lineTo(12 * s, 14 * s)
    path.lineTo(16 * s, 8 * s)
    path.lineTo(19.5 * s, 5.5 * s)
    p.drawPath(path)


def _images(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(3 * s, 4 * s, 18 * s, 16 * s), 2 * s, 2 * s)
    p.drawEllipse(QPointF(16.5 * s, 8.5 * s), 1.6 * s, 1.6 * s)   # sun
    path = QPainterPath(QPointF(4.5 * s, 16.5 * s))
    path.lineTo(9.5 * s, 10.5 * s)
    path.lineTo(13 * s, 14 * s)
    path.lineTo(16.5 * s, 11 * s)
    path.lineTo(20.5 * s, 16.5 * s)
    p.drawPath(path)


def _open_folder(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    path = QPainterPath()
    path.moveTo(3 * s, 9 * s)
    path.lineTo(3 * s, 7 * s)
    path.lineTo(9 * s, 7 * s)
    path.lineTo(11 * s, 9 * s)
    path.lineTo(21 * s, 9 * s)
    path.lineTo(21 * s, 18.5 * s)
    path.lineTo(3 * s, 18.5 * s)
    path.closeSubpath()
    p.drawPath(path)


def _reload(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    # circular arrow with a 90° gap at the top-right for the arrowhead.
    p.drawArc(QRectF(4 * s, 4 * s, 16 * s, 16 * s), 40 * 16, 280 * 16)
    _fill(p, c)
    head = QPolygonF([
        QPointF(18.6 * s, 6.4 * s),
        QPointF(15.2 * s, 6.9 * s),
        QPointF(18.2 * s, 9.4 * s),
    ])
    p.drawPolygon(head)


def _run(p: QPainter, c: QColor, s: float) -> None:
    _fill(p, c)
    path = QPainterPath(QPointF(7.5 * s, 4.5 * s))
    path.lineTo(20 * s, 12 * s)
    path.lineTo(7.5 * s, 19.5 * s)
    path.closeSubpath()
    p.drawPath(path)


def _stop(p: QPainter, c: QColor, s: float) -> None:
    _fill(p, c)
    p.drawRoundedRect(QRectF(6 * s, 6 * s, 12 * s, 12 * s), 2.5 * s, 2.5 * s)


def _check(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawEllipse(QPointF(12 * s, 12 * s), 8 * s, 8 * s)
    path = QPainterPath(QPointF(8.5 * s, 12.6 * s))
    path.lineTo(11 * s, 15 * s)
    path.lineTo(15.8 * s, 9.4 * s)
    p.drawPath(path)


def _alert(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    path = QPainterPath()
    path.moveTo(12 * s, 3.5 * s)
    path.lineTo(21 * s, 19.5 * s)
    path.lineTo(3 * s, 19.5 * s)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(12 * s, 8.5 * s, 12 * s, 14 * s)      # stem
    _fill(p, c)
    p.drawEllipse(QPointF(12 * s, 16.8 * s), 1.2 * s, 1.2 * s)  # exclamation dot


def _clock(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawEllipse(QPointF(12 * s, 12 * s), 8.5 * s, 8.5 * s)
    p.drawLine(12 * s, 12 * s, 12 * s, 7 * s)        # minute hand (up)
    p.drawLine(12 * s, 12 * s, 16 * s, 13.5 * s)     # hour hand


def _mock(p: QPainter, c: QColor, s: float) -> None:
    _stroke(p, c, s)
    p.drawLine(10 * s, 4.5 * s, 14 * s, 4.5 * s)      # neck rim
    p.drawLine(12 * s, 4.5 * s, 12 * s, 9 * s)        # neck
    path = QPainterPath()
    path.moveTo(8 * s, 9.5 * s)
    path.lineTo(16 * s, 9.5 * s)
    path.lineTo(13.5 * s, 18.5 * s)
    path.quadTo(12 * s, 20 * s, 10.5 * s, 18.5 * s)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(10 * s, 14 * s, 14 * s, 14 * s)        # liquid line


# (name) -> draw callable; keep the dict private, expose via icon_names().
_ICONS: Dict[str, Callable[[QPainter, QColor, float], None]] = {
    "logo": _logo,
    "dashboard": _dashboard,
    "results": _results,
    "charts": _charts,
    "images": _images,
    "open": _open_folder,
    "reload": _reload,
    "run": _run,
    "stop": _stop,
    "mock": _mock,
    "check": _check,
    "alert": _alert,
    "clock": _clock,
}



def icon_names() -> List[str]:
    """Every icon name the factory can draw (for tests / registry UIs)."""
    return sorted(_ICONS)


def make_icon(name: str, color: str, size: int = 18) -> Optional[QIcon]:
    """Render ``name`` at ``size`` px in ``color`` (hex). Returns ``None`` for
    unknown names so callers can fall back to a text-only representation."""
    draw = _ICONS.get(name)
    if draw is None:
        return None
    px = int(round(size * _DPI))
    pm = QPixmap(px, px)
    pm.setDevicePixelRatio(_DPI)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    draw(painter, QColor(color), size / _GRID)
    painter.end()
    return QIcon(pm)
