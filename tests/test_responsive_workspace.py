"""Neo v2.2 — Stage 6: Responsive Workspace Polish.

These tests lock in the audit-justified fixes from the Stage 6 hardening pass.
Each one has a concrete measured defect behind it (see the Stage 6 audit):

- **Queue Run row (P1)** — the three run controls (~345px together) were
  crushed below sizeHint inside the header once the panel narrowed. They now
  live on their own full-width row that wraps to a second line instead of
  clipping, so the buttons always render at their natural size.
- **Queue filter row (P2)** — the filter pills + retry/max controls (~551px)
  were crushed to ~34px. The row is now a FlowLayout: pills reflow onto a
  second line and never shrink below sizeHint.
- **Charts toolbar (P3)** — the axis selectors + presets + export (~812px)
  overflowed the ~774px available at the default window. It is now a
  FlowLayout (with the label+combo pairs kept as one non-splittable unit) so
  it wraps instead of crushing the combos.
- **Docks (P4)** — Monitor/Parameters opened at Qt's ~300px default while
  their content needs ~490-575px, forcing a horizontal scrollbar. They now
  request a readable window-proportional width on their first show (released
  afterwards so the user can still drag them narrower).
- **FlowLayout spacer support** — FlowLayout absorbs leftover line width into
  horizontally-expanding items, which is what keeps the toolbar's Export
  button right-aligned while the rest of the row wraps.

Scrolling rules (Task 8): these fixes remove horizontal overflow where content
can wrap; no panel was shrunk into unreadability to avoid scrolling, and no
nested scroll areas were introduced.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import (QApplication, QPushButton,  # noqa: E402
                               QSizePolicy, QWidget)

from gui import theme                                       # noqa: E402
from gui.widgets.flow_layout import FlowLayout              # noqa: E402
from tools.make_experiment_template import build_template   # noqa: E402

CONFIG_TPL = """
fluent:
  aoa_method: "geometry"
  wall_zones: ["wing"]
  reference: {{density: 1.225, area: 1.0}}
excel:
  file: "{xlsx}"
runtime:
  work_dir: "{work}"
  mock: true
"""


def _load_fonts() -> None:
    """Windows Segoe UI/Arial so widget metrics match the real app. Offscreen
    Qt cannot enumerate fonts, so they must be loaded explicitly — without
    them the default font is wider, inflating every sizeHint/minimum."""
    if sys.platform == "win32":
        from PySide6.QtGui import QFontDatabase
        fd = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for name in ("segoeui.ttf", "arial.ttf"):
            p = os.path.join(fd, name)
            if os.path.isfile(p):
                QFontDatabase.addApplicationFont(p)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    _load_fonts()
    return app


@pytest.fixture()
def project(tmp_path: Path):
    xlsx = tmp_path / "experiments.xlsx"
    build_template(xlsx)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG_TPL.format(xlsx=xlsx.as_posix(),
                                     work=(tmp_path / "runs").as_posix()))
    return cfg


def _window(monkeypatch, config_path=None):
    from gui.main_window import MainWindow
    monkeypatch.setattr(MainWindow, "_open_project_selector", lambda self: None)
    win = MainWindow(config_path=str(config_path) if config_path else None)
    win.resize(1480, 900)
    return win


def _show(qapp, win) -> None:
    win.show()
    for _ in range(6):
        qapp.processEvents()


def _run_flow(win) -> FlowLayout:
    """The FlowLayout inside the Queue's wrapping Run-controls row."""
    from gui.widgets.toolbar_section import ToolbarSection
    group = next(w for w in win.queue.findChildren(ToolbarSection))
    return group.layout()


def _charts_toolbar_flow(win) -> FlowLayout:
    toolbar = next(w for w in win.charts.findChildren(QWidget)
                   if w.property("chartToolbar") is True)
    return toolbar.layout()


def _not_crushed(btn: QPushButton) -> bool:
    """A control is crushed when Qt gives it far less than its sizeHint."""
    return btn.width() >= btn.sizeHint().width() - 1


# --------------------------------------------------------------------- #
# P1 — Queue Run row
# --------------------------------------------------------------------- #
def test_queue_run_controls_keep_size_hint_at_default(qapp, monkeypatch,
                                                      project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        for b in (win.queue.run_all, win.queue.run_sel, win.queue.stop_btn):
            assert _not_crushed(b), (
                f"{b.text()!r} crushed: {b.width()} vs sizeHint "
                f"{b.sizeHint().width()}")
    finally:
        win.close()


def test_queue_run_row_wraps_instead_of_crushing(qapp, monkeypatch, project):
    """At the Queue's minimum width the run controls must wrap to a second
    line (the row grows taller) rather than clip below sizeHint."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        # Shrink through several steps so the splitter drives the Queue to its
        # minimum width (a single resize step leaves it mid-transition).
        for w in (1100, 900, 700):
            win.resize(w, 800)
            qapp.processEvents()
        flow = _run_flow(win)
        one_line = flow.heightForWidth(1000)
        wrapped = flow.heightForWidth(win.queue.width() - 16)
        assert win.queue.width() <= theme.MIN_QUEUE_WIDTH
        assert wrapped > one_line
        for b in (win.queue.run_all, win.queue.run_sel, win.queue.stop_btn):
            assert _not_crushed(b)
    finally:
        win.close()


# --------------------------------------------------------------------- #
# P2 — Queue filter row
# --------------------------------------------------------------------- #
def test_queue_filter_pills_keep_size_hint(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        for btn in win.queue._filter_btns.values():
            assert _not_crushed(btn), (
                f"filter {btn.text()!r} crushed: {btn.width()} vs sizeHint "
                f"{btn.sizeHint().width()}")
    finally:
        win.close()


def test_queue_filter_pills_keep_size_hint_narrow(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.resize(900, 800)
        qapp.processEvents()
        for btn in win.queue._filter_btns.values():
            assert _not_crushed(btn)
    finally:
        win.close()


# --------------------------------------------------------------------- #
# P3 — Charts toolbar
# --------------------------------------------------------------------- #
def test_charts_toolbar_keeps_controls_readable(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._navigate_to_page("charts")
        qapp.processEvents()
        tb = _charts_toolbar_flow(win).parentWidget()
        for b in tb.findChildren(QPushButton):
            if b.isVisible():
                assert _not_crushed(b), (
                    f"{b.text()!r} crushed: {b.width()} vs sizeHint "
                    f"{b.sizeHint().width()}")
    finally:
        win.close()


def test_charts_toolbar_wraps_when_narrow(qapp, monkeypatch, project):
    """Narrower toolbar width must produce a taller (wrapped) toolbar, with
    every control still at its natural size."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._navigate_to_page("charts")
        qapp.processEvents()
        tb = _charts_toolbar_flow(win).parentWidget()
        flow = tb.layout()
        wide = flow.heightForWidth(900)
        narrow = flow.heightForWidth(300)
        assert narrow > wide
        for b in tb.findChildren(QPushButton):
            if b.isVisible():
                assert _not_crushed(b)
    finally:
        win.close()


# --------------------------------------------------------------------- #
# P4 — first-show dock width
# --------------------------------------------------------------------- #
def test_parameters_dock_opens_readable_width(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._docks["Parameters"].show()
        qapp.processEvents()
        d = win._docks["Parameters"]
        assert d.width() >= theme.MIN_DOCK_WIDTH
        # the temporary minimum is released so the user can still drag narrower
        assert d.minimumWidth() == 0
    finally:
        win.close()


def test_monitor_dock_opens_readable_width(qapp, monkeypatch, project):
    """The Monitor is tabified with Parameters; its raise must also get the
    readable width (visibilityChanged alone can't detect a raised tab)."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._docks["Parameters"].show()
        qapp.processEvents()
        win._docks["Monitor"].show()
        qapp.processEvents()
        assert win._docks["Monitor"].width() >= theme.MIN_DOCK_WIDTH
    finally:
        win.close()


# --------------------------------------------------------------------- #
# FlowLayout — expanding item right-aligns a trailing control
# --------------------------------------------------------------------- #
def test_flow_layout_expanding_item_right_aligns(qapp):
    """An Expanding item absorbs the leftover line width, so a trailing
    control lands flush-right on its line while earlier items wrap naturally.
    This is what keeps the Charts toolbar's Export button right-aligned
    (the Charts toolbar wraps its Export button in an expanding container)."""
    from PySide6.QtWidgets import QHBoxLayout
    host = QWidget()
    flow = FlowLayout(host, hspacing=4)
    for text in ("Alpha", "Beta", "Gamma", "Delta", "Echo"):
        b = QPushButton(text)
        flow.addWidget(b)
    # Expanding container around the trailing control, matching production.
    tail_host = QWidget()
    tail_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    th = QHBoxLayout(tail_host)
    th.setContentsMargins(0, 0, 0, 0)
    th.addStretch(1)
    tail = QPushButton("Export")
    th.addWidget(tail)
    flow.addWidget(tail_host)
    host.resize(500, 200)
    host.show()
    qapp.processEvents()
    # Drive the layout to the widget's actual size deterministically.
    flow.activate()
    qapp.processEvents()
    # The expanding container absorbs the line's leftover width → flush right
    # within the flow layout's host.
    assert tail_host.geometry().right() >= host.width() - 2, \
        f"container right={tail_host.geometry().right()} host={host.width()}"
    # The Export button rides flush-right inside its container (geometry is
    # parent-relative, so compare against the container's own width).
    assert tail.geometry().right() >= tail_host.width() - 2, \
        f"export right={tail.geometry().right()} container={tail_host.width()}"
    host.close()
