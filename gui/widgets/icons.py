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


def _settings(p: QPainter, c: QColor, s: float) -> None:
    """Gear: centre hub + eight radial teeth (configuration)."""
    _stroke(p, c, s)
    p.save()
    p.translate(12 * s, 12 * s)
    for _ in range(8):
        p.rotate(45)
        p.drawLine(QPointF(6.5 * s, 0), QPointF(9.5 * s, 0))
    p.drawEllipse(QPointF(0, 0), 4.5 * s, 4.5 * s)
    p.restore()
    _fill(p, c)
    p.drawEllipse(QPointF(12 * s, 12 * s), 1.7 * s, 1.7 * s)


def _export(p: QPainter, c: QColor, s: float) -> None:
    """Export: up-arrow rising out of a tray."""
    _stroke(p, c, s)
    p.drawLine(4 * s, 17.5 * s, 20 * s, 17.5 * s)    # tray floor
    p.drawLine(4 * s, 17.5 * s, 4 * s, 15 * s)       # tray sides
    p.drawLine(20 * s, 17.5 * s, 20 * s, 15 * s)
    p.drawLine(12 * s, 15 * s, 12 * s, 6 * s)        # arrow shaft
    p.drawLine(12 * s, 6 * s, 8.5 * s, 9.5 * s)
    p.drawLine(12 * s, 6 * s, 15.5 * s, 9.5 * s)


def _report(p: QPainter, c: QColor, s: float) -> None:
    """Report: document with a header rule and body lines."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(3.5 * s, 3.5 * s, 17 * s, 17 * s), 2 * s, 2 * s)
    p.drawLine(3.5 * s, 9 * s, 20.5 * s, 9 * s)      # header rule
    p.drawLine(7 * s, 12.5 * s, 17 * s, 12.5 * s)
    p.drawLine(7 * s, 15.5 * s, 17 * s, 15.5 * s)


def _validate(p: QPainter, c: QColor, s: float) -> None:
    """Validate: clipboard sheet with an approval check."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(4 * s, 4 * s, 16 * s, 16 * s), 2 * s, 2 * s)
    p.drawLine(4 * s, 8.5 * s, 20 * s, 8.5 * s)      # sheet top rule
    path = QPainterPath(QPointF(7.5 * s, 13.5 * s))
    path.lineTo(10.5 * s, 16 * s)
    path.lineTo(16.5 * s, 10.5 * s)
    p.drawPath(path)


def _resume(p: QPainter, c: QColor, s: float) -> None:
    """Resume: play triangle inside a rounded square (continue)."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(4 * s, 4 * s, 16 * s, 16 * s), 3 * s, 3 * s)
    _fill(p, c)
    path = QPainterPath(QPointF(9 * s, 7.5 * s))
    path.lineTo(17 * s, 12 * s)
    path.lineTo(9 * s, 16.5 * s)
    path.closeSubpath()
    p.drawPath(path)


def _terminal(p: QPainter, c: QColor, s: float) -> None:
    """Terminal: prompt chevron + cursor block in a window."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(3 * s, 4 * s, 18 * s, 16 * s), 2 * s, 2 * s)
    path = QPainterPath(QPointF(7.5 * s, 8.5 * s))
    path.lineTo(10.5 * s, 11 * s)
    path.lineTo(7.5 * s, 13.5 * s)
    p.drawPath(path)
    p.drawLine(13 * s, 14.5 * s, 17 * s, 14.5 * s)   # cursor line


def _filter(p: QPainter, c: QColor, s: float) -> None:
    """Filter: funnel narrowing to a stem."""
    _stroke(p, c, s)
    path = QPainterPath()
    path.moveTo(4 * s, 5 * s)
    path.lineTo(20 * s, 5 * s)
    path.lineTo(13.5 * s, 13 * s)
    path.lineTo(13.5 * s, 19 * s)
    path.lineTo(10.5 * s, 19 * s)
    path.lineTo(10.5 * s, 13 * s)
    path.closeSubpath()
    p.drawPath(path)


def _search(p: QPainter, c: QColor, s: float) -> None:
    """Search: magnifying glass."""
    _stroke(p, c, s)
    p.drawEllipse(QPointF(10 * s, 10 * s), 5.5 * s, 5.5 * s)
    p.drawLine(14.5 * s, 14.5 * s, 19.5 * s, 19.5 * s)


def _plus(p: QPainter, c: QColor, s: float) -> None:
    """Add: simple cross."""
    _stroke(p, c, s)
    p.drawLine(12 * s, 5.5 * s, 12 * s, 18.5 * s)
    p.drawLine(5.5 * s, 12 * s, 18.5 * s, 12 * s)


def _duplicate(p: QPainter, c: QColor, s: float) -> None:
    """Duplicate: two offset sheets."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(5.5 * s, 5.5 * s, 13 * s, 13 * s), 1.5 * s, 1.5 * s)
    p.drawRoundedRect(QRectF(8.5 * s, 8.5 * s, 13 * s, 13 * s), 1.5 * s, 1.5 * s)


def _info(p: QPainter, c: QColor, s: float) -> None:
    """Info: circle with a dot over a stem."""
    _stroke(p, c, s)
    p.drawEllipse(QPointF(12 * s, 12 * s), 8 * s, 8 * s)
    _fill(p, c)
    p.drawEllipse(QPointF(12 * s, 7.5 * s), 1.3 * s, 1.3 * s)
    _stroke(p, c, s)
    p.drawLine(12 * s, 11 * s, 12 * s, 16 * s)


def _warning(p: QPainter, c: QColor, s: float) -> None:
    """Warning: circled exclamation (softer than the alert triangle)."""
    _stroke(p, c, s)
    p.drawEllipse(QPointF(12 * s, 12 * s), 8 * s, 8 * s)
    p.drawLine(12 * s, 7.5 * s, 12 * s, 13 * s)
    _fill(p, c)
    p.drawEllipse(QPointF(12 * s, 16.5 * s), 1.3 * s, 1.3 * s)


def _file(p: QPainter, c: QColor, s: float) -> None:
    """File: document with body lines."""
    _stroke(p, c, s)
    p.drawRoundedRect(QRectF(4 * s, 3.5 * s, 16 * s, 17 * s), 1.5 * s, 1.5 * s)
    p.drawLine(7 * s, 9 * s, 17 * s, 9 * s)
    p.drawLine(7 * s, 12.5 * s, 17 * s, 12.5 * s)
    p.drawLine(7 * s, 16 * s, 14 * s, 16 * s)


def _folder(p: QPainter, c: QColor, s: float) -> None:
    """Folder: closed folder with a top tab."""
    _stroke(p, c, s)
    path = QPainterPath()
    path.moveTo(3 * s, 6.5 * s)
    path.lineTo(9.5 * s, 6.5 * s)
    path.lineTo(11.5 * s, 8.5 * s)
    path.lineTo(21 * s, 8.5 * s)
    path.lineTo(21 * s, 18 * s)
    path.lineTo(3 * s, 18 * s)
    path.closeSubpath()
    p.drawPath(path)


def _queue(p: QPainter, c: QColor, s: float) -> None:
    """Queue: stacked experiment rows with leading status squares."""
    _stroke(p, c, s)
    for y in (6.5, 12, 17.5):
        p.drawRoundedRect(QRectF(4 * s, y * s, 16 * s, 3.5 * s), 1 * s, 1 * s)
    _fill(p, c)
    for y in (6.5, 12, 17.5):
        p.drawRoundedRect(QRectF(4 * s, y * s, 3 * s, 3.5 * s), 1 * s, 1 * s)


def _zoom(p: QPainter, c: QColor, s: float) -> None:
    """Fit/zoom-to-view: four corner brackets."""
    _stroke(p, c, s)
    p.drawLine(4 * s, 9 * s, 4 * s, 4 * s)
    p.drawLine(4 * s, 4 * s, 9 * s, 4 * s)
    p.drawLine(15 * s, 4 * s, 20 * s, 4 * s)
    p.drawLine(20 * s, 4 * s, 20 * s, 9 * s)
    p.drawLine(20 * s, 15 * s, 20 * s, 20 * s)
    p.drawLine(20 * s, 20 * s, 15 * s, 20 * s)
    p.drawLine(9 * s, 20 * s, 4 * s, 20 * s)
    p.drawLine(4 * s, 20 * s, 4 * s, 15 * s)


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
    "settings": _settings,
    "export": _export,
    "report": _report,
    "validate": _validate,
    "resume": _resume,
    "terminal": _terminal,
    "filter": _filter,
    "search": _search,
    "plus": _plus,
    "duplicate": _duplicate,
    "info": _info,
    "warning": _warning,
    "file": _file,
    "folder": _folder,
    "queue": _queue,
    "zoom": _zoom,
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
