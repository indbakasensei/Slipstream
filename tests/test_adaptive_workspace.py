"""Neo v2.2 — Stage 5: Adaptive Workspace & Layout Management.

The primary engineering view must always stay usable and visually dominant.
These tests lock in two new behaviours plus their state-restoration contracts:

- **Queue collapse** — user-initiated hide/show that reclaims the Queue's
  horizontal splitter space for the center workspace and restores the Queue at
  its previous width (never the old fixed 30% rule). The Queue stays visible by
  default and is never hidden automatically by resizing.
- **Focus Mode** — a presentation-level toggle that hides Sidebar, Queue, and
  every dock so the current primary workspace gets the full window, then
  restores the *exact* previous layout state on exit.

Both behaviours live entirely in the GUI layout layer: no engine, platform,
StudyIO, or ExperimentDefinition file is touched, and no template-specific
branching exists.
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

from PySide6.QtWidgets import QApplication                     # noqa: E402

from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.platform import EXTERNAL_AERODYNAMICS, INTERNAL_FLOW  # noqa: E402
from cfdauto.simulation_context import SimulationContext        # noqa: E402
from tools.make_experiment_template import build_template       # noqa: E402

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


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


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
    # A config-less MainWindow defers a *modal* project-selector dialog via
    # QTimer.singleShot; neutralize it so processEvents() can't block.
    monkeypatch.setattr(MainWindow, "_open_project_selector", lambda self: None)
    win = MainWindow(config_path=str(config_path) if config_path else None)
    win.resize(1480, 900)
    return win


def _show(qapp, win) -> None:
    win.show()
    qapp.processEvents()


# --------------------------------------------------------------------- #
# Queue — default state, toggle, space reclamation, restore
# --------------------------------------------------------------------- #
def test_queue_visible_by_default(qapp, monkeypatch):
    win = _window(monkeypatch)
    try:
        assert win.queue_collapsed is False
        assert win.queue.isHidden() is False
    finally:
        win.close()


def test_queue_toggle_buttons_exist(qapp, monkeypatch):
    win = _window(monkeypatch)
    try:
        assert hasattr(win.workspace_header, "queue_btn")
        assert hasattr(win.workspace_header, "focus_btn")
        assert win.workspace_header.queue_btn.isEnabled()
    finally:
        win.close()


def test_header_queue_button_state_reflects_visibility(qapp, monkeypatch):
    win = _window(monkeypatch)
    try:
        assert win.workspace_header.queue_btn.property("active") is True
        win.toggle_queue()
        assert win.workspace_header.queue_btn.property("active") is False
        win.toggle_queue()
        assert win.workspace_header.queue_btn.property("active") is True
    finally:
        win.close()


def test_header_queue_button_toggles_queue(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        win.workspace_header.queue_btn.click()
        assert win.queue_collapsed is True
        win.workspace_header.queue_btn.click()
        assert win.queue_collapsed is False
    finally:
        win.close()


def test_queue_collapse_hides_queue(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        win.toggle_queue()
        qapp.processEvents()
        assert win.queue_collapsed is True
        assert win.queue.isVisible() is False
    finally:
        win.close()


def test_queue_restore_shows_queue(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        win.toggle_queue()
        win.toggle_queue()
        qapp.processEvents()
        assert win.queue_collapsed is False
        assert win.queue.isVisible() is True
    finally:
        win.close()


def test_queue_collapse_changes_splitter_sizes(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        before = list(win.splitter.sizes())
        win.toggle_queue()
        qapp.processEvents()
        assert list(win.splitter.sizes()) != before
    finally:
        win.close()


def test_center_gains_space_when_queue_collapsed(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        center_before = win.splitter.sizes()[1]
        win.toggle_queue()
        qapp.processEvents()
        assert win.splitter.sizes()[1] > center_before
    finally:
        win.close()


def test_queue_restored_to_previous_width(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        before = list(win.splitter.sizes())
        win.toggle_queue()
        win.toggle_queue()
        qapp.processEvents()
        after = list(win.splitter.sizes())
        # Previous widths return (splitter handles may shift by 1–2 px).
        assert all(abs(a - b) <= 4 for a, b in zip(after, before))
    finally:
        win.close()


def test_queue_toggle_is_idempotent(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        win.toggle_queue(); win.toggle_queue(); win.toggle_queue()
        assert win.queue_collapsed is True      # odd toggles → collapsed
        win.toggle_queue()
        assert win.queue_collapsed is False     # even → back to visible
    finally:
        win.close()


def test_queue_state_survives_page_navigation(qapp, monkeypatch):
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        win.toggle_queue()
        for page in ("dashboard", "charts", "images", "results", "dashboard"):
            win._navigate_to_page(page)
        assert win.queue_collapsed is True
        assert win.queue.isVisible() is False
    finally:
        win.close()


def test_queue_state_survives_resizing(qapp, monkeypatch, project):
    """Sequence 4: collapse → resize several times → restore, no corrupted
    splitter state and no automatic re-show/hide driven by window size."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.toggle_queue()
        for w, h in ((1280, 800), (1100, 750), (900, 700), (1480, 900)):
            win.resize(w, h)
            qapp.processEvents()
            assert win.queue_collapsed is True
            assert win.queue.isVisible() is False
        win.toggle_queue()
        qapp.processEvents()
        assert win.queue_collapsed is False
        assert win.queue.isVisible() is True
        assert len(win.splitter.sizes()) == 3
    finally:
        win.close()


# --------------------------------------------------------------------- #
# Focus button — existence, enablement, page-driven tooltip
# --------------------------------------------------------------------- #
def test_focus_button_disabled_without_project(qapp, monkeypatch):
    win = _window(monkeypatch)
    try:
        assert win.workspace_header.focus_btn.isEnabled() is False
        win.toggle_focus_mode()                 # guarded → no-op
        assert win.focus_mode is False
        assert win.sidebar.isHidden() is False
    finally:
        win.close()


def test_focus_button_enabled_after_project_load(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    try:
        assert win.workspace_header.focus_btn.isEnabled() is True
    finally:
        win.close()


def test_focus_tooltip_follows_page(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    try:
        win._navigate_to_page("charts")
        assert win.workspace_header.focus_btn.toolTip() == "Focus Charts"
        win._navigate_to_page("images")
        assert win.workspace_header.focus_btn.toolTip() == "Focus Images"
        win._navigate_to_page("dashboard")
        assert win.workspace_header.focus_btn.toolTip() == "Focus Workspace"
    finally:
        win.close()


def test_header_focus_button_toggles_focus(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.workspace_header.focus_btn.click()
        assert win.focus_mode is True
        win.workspace_header.focus_btn.click()
        assert win.focus_mode is False
    finally:
        win.close()


# --------------------------------------------------------------------- #
# Focus Mode — hide everything secondary, preserve page, restore exactly
# --------------------------------------------------------------------- #
def test_focus_hides_sidebar_and_queue(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is True
        assert win.sidebar.isVisible() is False
        assert win.queue.isVisible() is False
    finally:
        win.close()


def test_focus_hides_utility_docks(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.toggle_focus_mode()
        qapp.processEvents()
        for dock in win._docks.values():
            assert dock.isVisible() is False
    finally:
        win.close()


def test_focus_preserves_current_page(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._navigate_to_page("charts")
        win.toggle_focus_mode()
        assert win.tabs.currentWidget() is win.charts
        win.toggle_focus_mode()
        assert win.tabs.currentWidget() is win.charts
    finally:
        win.close()


def test_focus_exit_restores_previous_state(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._docks["Monitor"].show()
        qapp.processEvents()
        assert not win.queue_collapsed
        win.toggle_focus_mode()
        assert win.focus_mode is True
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is False
        assert win.queue.isVisible() is True
        assert win.sidebar.isVisible() is True
        assert win._docks["Monitor"].isVisible() is True
    finally:
        win.close()


def test_queue_collapsed_before_focus_stays_collapsed(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win.toggle_queue()                       # collapse first
        assert win.queue_collapsed is True
        win.toggle_focus_mode()
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.queue_collapsed is True
        assert win.queue.isVisible() is False
    finally:
        win.close()


def test_queue_visible_before_focus_restored_visible(qapp, monkeypatch, project):
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        assert win.queue_collapsed is False       # visible before Focus
        win.toggle_focus_mode()
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.queue_collapsed is False
        assert win.queue.isVisible() is True
    finally:
        win.close()


def test_monitor_parameters_console_state_restores(qapp, monkeypatch, project):
    """Each dock's visibility state (including which tab was raised) returns
    to the exact pre-Focus map after Focus exit."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        win._docks["Monitor"].show()
        win._docks["Parameters"].show()
        win._docks["Console"].show()
        qapp.processEvents()
        pre = {name: d.isVisible() for name, d in win._docks.items()}
        assert any(pre.values())                  # at least the Log tab visible
        win.toggle_focus_mode()
        win.toggle_focus_mode()
        qapp.processEvents()
        post = {name: d.isVisible() for name, d in win._docks.items()}
        assert post == pre
    finally:
        win.close()


def test_multiple_docks_do_not_break_focus(qapp, monkeypatch, project):
    """Stress: every secondary/utility panel open at once — Focus still hides
    all of it and restores the workspace cleanly."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        for name in ("Monitor", "Parameters", "Console"):
            win._docks[name].show()
        qapp.processEvents()
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is True
        assert win.sidebar.isVisible() is False
        assert win.queue.isVisible() is False
        for dock in win._docks.values():
            assert dock.isVisible() is False
        win.toggle_focus_mode()
        qapp.processEvents()
        assert win.focus_mode is False
        assert win.sidebar.isVisible() is True
        assert win.queue.isVisible() is True
    finally:
        win.close()


# --------------------------------------------------------------------- #
# Responsive floors / template independence / existing contracts
# --------------------------------------------------------------------- #
def test_narrow_window_no_clipped_controls(qapp, monkeypatch):
    """Small windows stay usable: no exception, the Queue is never hidden
    automatically by resizing, and the header toggles keep their size."""
    win = _window(monkeypatch)
    _show(qapp, win)
    try:
        for w, h in ((900, 700), (800, 600)):
            win.resize(w, h)
            qapp.processEvents()
            assert win.queue.isVisible() is True   # not auto-hidden on resize
            assert win.queue_collapsed is False
            assert win.workspace_header.queue_btn.width() >= 1
            assert win.workspace_header.focus_btn.width() >= 1
            assert win.splitter.count() == 3
    finally:
        win.close()


def test_workspace_behavior_template_independent(qapp, monkeypatch, project):
    """The adaptive-workspace layer never branches on template. Swapping the
    loaded AppState's runtime metadata to Internal Flow changes nothing about
    Queue collapse, Focus Mode, or the page-driven focus labels."""
    win = _window(monkeypatch, project)
    _show(qapp, win)
    try:
        assert win.state.context.template is EXTERNAL_AERODYNAMICS
        win.state.context = SimulationContext(template=INTERNAL_FLOW)
        win.state.experiment_definition = ExperimentDefinition.from_context(
            win.state.context)
        win._navigate_to_page("charts")
        assert win.workspace_header.focus_btn.toolTip() == "Focus Charts"
        win.toggle_queue(); assert win.queue_collapsed is True
        win.toggle_queue(); assert win.queue_collapsed is False
        win.toggle_focus_mode()
        assert win.focus_mode is True
        assert win.sidebar.isVisible() is False
        win.toggle_focus_mode()
        assert win.focus_mode is False
        assert win.sidebar.isVisible() is True
    finally:
        win.close()


def test_existing_gui_contracts_remain_valid(qapp, monkeypatch):
    """Stage 5 must not regress the responsive minimums or the public API."""
    from gui import theme
    win = _window(monkeypatch)
    try:
        assert win.sidebar.minimumWidth() == theme.MIN_SIDEBAR_WIDTH
        assert win.tabs.minimumWidth() == theme.MIN_CENTER_WIDTH
        assert win.queue.minimumWidth() == theme.MIN_QUEUE_WIDTH
        assert win.splitter.childrenCollapsible() is False
        assert win.splitter.count() == 3
        assert win.tabs.count() == 4
        assert set(win._nav_pages) == {"dashboard", "results", "charts", "images"}
        assert win.workspace_header.page_id == ""
        win._navigate_to_page("dashboard")
        assert win.workspace_header.page_id == "dashboard"
    finally:
        win.close()
