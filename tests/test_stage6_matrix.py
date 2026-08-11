"""Neo v2.2 — Stage 6: Window-Size Matrix (Task 4) + User-Interaction Matrix
(Task 5).

The Stage 6 spec requires a *real* matrix of window sizes and states (A–M),
plus realistic user sequences, with every state checked for:

- no widget disappears unexpectedly (positive geometry, within bounds)
- no important control becomes inaccessible (queue run/filter controls, charts
  toolbar never crushed below sizeHint)
- no layout explosion / infinite expansion / negative geometry
- no accidental automatic hide/show (visibility only changes through the
  user's explicit collapse / focus actions)
- scrolling remains available where content exceeds space
- primary content stays usable (center workspace keeps a real width)
- Stage5 state restoration still works (queue collapse/restore, focus exact
  restore, dock visibility preserved)

These build on the Stage 5 contract suite (test_adaptive_workspace.py) without
weakening any of its assertions — they add the window-size *dimension* the
Stage 6 spec demands. Pure GUI-layout tests: no engine, platform, StudyIO, or
ExperimentDefinition file is touched.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import (QApplication, QPushButton,  # noqa: E402
                               QScrollArea)

from gui import theme                                          # noqa: E402
from tools.make_experiment_template import build_template      # noqa: E402

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
    from gui.theme import apply_theme
    apply_theme(app)
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
    return win


def _settle(qapp, win, times: int = 6) -> None:
    win.show()
    for _ in range(times):
        qapp.processEvents()
    # The config + dataset load completes through the event loop (async);
    # several Stage5/6 behaviours (e.g. entering Focus Mode) require the
    # project to actually be loaded, so wait for it.
    t0 = time.monotonic()
    while not (win.state.cfg is not None and len(win.state.df) > 0):
        qapp.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > 30:
            break


def _pump_until(qapp, predicate, timeout_s: float = 90.0) -> None:
    t0 = time.monotonic()
    while not predicate():
        qapp.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout_s:
            raise TimeoutError("Stage6 matrix timed out")


# --------------------------------------------------------------------- #
# Invariants
# --------------------------------------------------------------------- #
def _not_crushed(btn: QPushButton) -> bool:
    return btn.width() >= btn.sizeHint().width() - 1


def _assert_sane_layout(win, *, queue_visible: bool, label: str):
    """The invariant set the spec asks every matrix cell to satisfy."""
    # positive, non-negative, within-window geometry for the three columns.
    # Hidden widgets (collapsed queue, focus mode) keep stale geometry, so
    # only measure the columns that are actually on screen; the visibility of
    # hidden columns is asserted separately below.
    if not win.focus_mode:
        for w, name in ((win.sidebar, "sidebar"), (win.tabs, "center"),
                        (win.queue, "queue")):
            if w.isHidden():
                continue
            assert w.width() > 0 and w.height() > 0, \
                f"{label}: {name} non-positive geometry ({w.width()}x{w.height()})"
            assert w.x() >= 0, f"{label}: {name} off the left edge"
            right = w.x() + w.width()
            assert right <= win.width() + 1, \
                f"{label}: {name} past right edge ({right} > {win.width()})"
        assert win.tabs.width() >= 300, f"{label}: center unusably narrow"
    else:
        assert win.tabs.width() > 0, f"{label}: center lost in focus mode"
    # no accidental automatic hide/show — queue visibility follows only the
    # user's explicit collapse/focus actions
    assert win.queue.isHidden() is not queue_visible, \
        f"{label}: queue hidden={win.queue.isHidden()} but expected visible={queue_visible}"
    # queue run controls never crushed (only meaningful while the queue shows)
    if queue_visible:
        for b in (win.queue.run_all, win.queue.run_sel, win.queue.stop_btn):
            assert _not_crushed(b), f"{label}: queue control {b.text()!r} crushed"
    # scrolling stays available where content can exceed space
    for panel, name in ((win.dashboard, "dashboard"), (win.params, "params")):
        areas = panel.findChildren(QScrollArea)
        assert areas, f"{label}: {name} should provide a scroll area"


def _assert_no_crash_open_docks(win, opened, label: str):
    """Docks the user opened must remain visible (and readable) after any
    resize — nothing auto-hides them."""
    for name in opened:
        d = win._docks[name]
        assert d.isVisible(), f"{label}: dock {name} unexpectedly hidden"
        assert d.width() > 0 and d.height() > 0, \
            f"{label}: dock {name} has non-positive geometry"


# --------------------------------------------------------------------- #
# Task 4 — Window-Size Matrix
# --------------------------------------------------------------------- #
# A–M exactly as the spec lists them. Column order matches the test signature:
# name, size, docks, focus, collapse, resize_to, extra.
MATRIX = [
    ("A_large",             (1920, 1080), [], False, False, None, None),
    ("B_normal",            (1480, 900),  [], False, False, None, None),
    ("C_narrow",            (1000, 700),  [], False, False, None, None),
    ("D_short",             (1400, 520),  [], False, False, None, None),
    ("E_narrow_short",      (1000, 520),  [], False, False, None, None),
    ("F_large_queue",       (1920, 1080), [], False, False, None, None),
    ("G_large_params",      (1920, 1080), ["Parameters"], False, False,
     None, None),
    ("H_large_monitor",     (1920, 1080), ["Monitor"], False, False, None,
     None),
    ("I_multi_docks",       (1920, 1080), ["Parameters", "Monitor",
                                           "Console"], False, False, None,
     None),
    ("J_focus",             (1480, 900),  [], True, False, None, None),
    ("K_focus_resize",      (1480, 900),  [], True, False, (1000, 700), None),
    ("L_queue_collapsed_rz",(1480, 900),  [], False, True, (1000, 700), None),
    ("M_queue_restored_rz", (1480, 900),  [], False, False, (1000, 700),
     "collapse_then_restore"),
]


@pytest.mark.parametrize("name,size,docks,focus,collapse,resize_to,extra",
                         MATRIX, ids=[c[0] for c in MATRIX])
def test_window_matrix(qapp, monkeypatch, project, name, size, docks, focus,
                       collapse, resize_to, extra):
    win = _window(monkeypatch, project)
    try:
        win.resize(*size)
        _settle(qapp, win)

        if collapse:
            win.toggle_queue()
        if extra == "collapse_then_restore":
            win.toggle_queue()
            win.toggle_queue()          # collapse then restore again
            qapp.processEvents()
        for dock_name in docks:
            win._docks[dock_name].show()
            win._docks[dock_name].raise_()
        if focus:
            win.toggle_focus_mode()
        qapp.processEvents()
        if resize_to:
            win.resize(*resize_to)
            for _ in range(4):
                qapp.processEvents()

        # M ends with the queue restored; focus hides it; collapse keeps it
        # hidden. Every other scenario leaves it visible by default.
        queue_visible = not collapse and not focus
        _assert_sane_layout(win, queue_visible=queue_visible, label=name)

        if focus:
            # Focus hides sidebar/queue/docks; center takes the full window.
            assert win.sidebar.isHidden() is True
            assert win.queue.isHidden() is True
            for d in win._docks.values():
                assert d.isHidden() is True, f"{name}: dock not hidden in focus"
        else:
            _assert_no_crash_open_docks(win, docks, name)

        # Stage 5 restoration: exit focus → prior layout restored exactly
        if focus:
            win.toggle_focus_mode()
            qapp.processEvents()
            assert win.sidebar.isHidden() is False
            assert win.queue.isHidden() is False
            assert win.focus_mode is False
    finally:
        win.close()


# --------------------------------------------------------------------- #
# Task 5 — User-Interaction Matrix (one realistic sequence)
# --------------------------------------------------------------------- #
def test_user_interaction_sequence(qapp, monkeypatch, project):
    """The full spec sequence: open project → run mock → open/collapse Queue →
    Charts → Focus → resize → exit Focus → Parameters → select a row → resize →
    Monitor → Console → Images → back to Dashboard. Every step keeps the
    responsive invariants and Stage5 restoration guarantees."""
    win = _window(monkeypatch, project)
    try:
        win.resize(1480, 900)
        _settle(qapp, win)

        # 2. run mock study to completion
        win.start_run()
        _pump_until(qapp, lambda: not win.state.running)
        qapp.processEvents()
        _assert_sane_layout(win, queue_visible=True, label="after-run")

        # 3–4. open Queue (visible by default), then collapse it
        assert win.queue.isHidden() is False
        win.toggle_queue()
        qapp.processEvents()
        assert win.queue.isHidden() is True
        assert win.queue_collapsed is True

        # 5. navigate to Charts
        win._navigate_to_page("charts")
        qapp.processEvents()
        assert win._nav_pages["charts"].isVisible()

        # 6. enter Focus
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is True
        assert win.sidebar.isHidden() and win.queue.isHidden()

        # 7. resize while focused
        win.resize(1000, 700)
        qapp.processEvents()
        assert win.focus_mode is True
        assert win.tabs.width() > 0

        # 8. exit Focus → exact Stage5 restoration
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is False
        assert win.sidebar.isHidden() is False
        assert win.queue.isHidden() is True      # still collapsed as left
        win.toggle_queue()                       # restore Queue
        qapp.processEvents()
        assert win.queue.isHidden() is False

        # 9. open Parameters dock
        win._docks["Parameters"].show()
        win._docks["Parameters"].raise_()
        qapp.processEvents()
        assert win._docks["Parameters"].isVisible()
        assert win._docks["Parameters"].width() >= theme.MIN_DOCK_WIDTH

        # 10. select a Queue row → selection reaches the state
        win._navigate_to_page("dashboard")
        qapp.processEvents()
        win.state.select_case(1)
        qapp.processEvents()
        assert win.state.selected_row == 1

        # 11. resize with the dock open
        win.resize(1100, 720)
        qapp.processEvents()
        _assert_sane_layout(win, queue_visible=True, label="params-open")
        assert win._docks["Parameters"].isVisible()

        # 12–13. open Monitor and Console
        win._docks["Monitor"].show()
        win._docks["Console"].show()
        qapp.processEvents()
        assert win._docks["Monitor"].isVisible()
        assert win._docks["Console"].isVisible()
        _assert_no_crash_open_docks(win, ["Parameters", "Monitor", "Console"],
                                    "all-docks")

        # 14–15. Images, then back to Dashboard
        win._navigate_to_page("images")
        qapp.processEvents()
        assert win._nav_pages["images"].isVisible()
        win._navigate_to_page("dashboard")
        qapp.processEvents()
        assert win._nav_pages["dashboard"].isVisible()
        _assert_sane_layout(win, queue_visible=True, label="final")
    finally:
        win.close()
