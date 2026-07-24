"""Capability 3 — UI foundation (presentation only).

Covers the reusable design tokens, the Monitor/Parameters scroll+minimum-size
fixes that prevent clipping in short docks, the responsive main-splitter floors
(no region collapses to an unreadable sliver), and the project dialog's
template selector. No business logic is exercised here — only presentation
infrastructure for the upcoming Neo UI redesign.
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

from PySide6.QtWidgets import QApplication, QScrollArea      # noqa: E402

from gui import theme                                        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from gui.theme import apply_theme
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


# --------------------------------------------------------------------- #
# Objective 8 — reusable design constants exist and are coherent
# --------------------------------------------------------------------- #
def test_design_tokens_present_and_ordered():
    assert theme.SPACE_XS < theme.SPACE_SM < theme.SPACE_MD < theme.SPACE_LG
    for name in ("MIN_SIDEBAR_WIDTH", "MIN_CENTER_WIDTH", "MIN_QUEUE_WIDTH",
                 "MIN_PANEL_WIDTH", "MIN_PLOT_HEIGHT", "MIN_CONTROL_HEIGHT",
                 "SECTION_SPACING", "CONTROL_SPACING"):
        assert isinstance(getattr(theme, name), int) and getattr(theme, name) > 0


# --------------------------------------------------------------------- #
# Objective 6 — Monitor no longer clips: scrolls, min sizes, plot floor
# --------------------------------------------------------------------- #
def test_monitor_scrolls_and_declares_minimums(qapp):
    from gui.panels.monitor import MonitorPanel
    m = MonitorPanel()
    assert isinstance(m._scroll, QScrollArea)
    assert m._scroll.widgetResizable() is True
    assert m.minimumWidth() == theme.MIN_PANEL_WIDTH
    assert m._tabs.minimumHeight() == theme.MIN_PLOT_HEIGHT
    # Its public monitoring surface is untouched (business logic unchanged).
    assert hasattr(m, "bar") and hasattr(m, "pipeline") and hasattr(m, "handle_event")


def test_monitor_survives_tiny_resize_without_clipping(qapp):
    from gui.panels.monitor import MonitorPanel
    m = MonitorPanel()
    m.resize(280, 200)          # smaller than the content — should scroll
    qapp.processEvents()
    m.resize(900, 1000)         # generous — content expands
    qapp.processEvents()
    assert m._scroll.widget() is not None      # no crash, content intact


# --------------------------------------------------------------------- #
# Objective 7 — Parameters panel scrolls (dynamic forms can be long)
# --------------------------------------------------------------------- #
def test_params_panel_scrolls(qapp):
    from gui.panels.params_panel import ParamsPanel
    from gui.state import AppState
    p = ParamsPanel(AppState())
    assert isinstance(p._scroll, QScrollArea)
    assert p.minimumWidth() == theme.MIN_PANEL_WIDTH


# --------------------------------------------------------------------- #
# Objective 7 — main splitter has responsive floors, no collapse
# --------------------------------------------------------------------- #
def test_main_window_has_responsive_minimums(qapp, monkeypatch):
    from gui.main_window import MainWindow
    # A config-less MainWindow defers a *modal* project-selector dialog via
    # QTimer.singleShot; neutralize it so processEvents() can't block the
    # offscreen test on a modal exec().
    monkeypatch.setattr(MainWindow, "_open_project_selector", lambda self: None)
    win = MainWindow()
    try:
        assert win.sidebar.minimumWidth() == theme.MIN_SIDEBAR_WIDTH
        assert win.tabs.minimumWidth() == theme.MIN_CENTER_WIDTH
        assert win.queue.minimumWidth() == theme.MIN_QUEUE_WIDTH
        assert win.splitter.childrenCollapsible() is False
        win.resize(900, 600)        # shrink hard — must not raise
        qapp.processEvents()
    finally:
        win.close()
        qapp.processEvents()


# --------------------------------------------------------------------- #
# Objective 1 — the project dialog offers a template selector, and
# creating a project scaffolds the chosen template.
# --------------------------------------------------------------------- #
def test_project_dialog_template_selector_and_create(qapp, tmp_path):
    from cfdauto.config import load_config
    from cfdauto.platform import DEFAULT_TEMPLATE_ID
    from gui.project_selector_dialog import ProjectSelectorDialog

    store = tmp_path / "recents.json"
    dlg = ProjectSelectorDialog(recents_store_path=store)
    ids = [dlg.template_combo.itemData(i)
           for i in range(dlg.template_combo.count())]
    assert set(ids) == {"external-aerodynamics", "internal-flow"}
    assert dlg.template_combo.currentData() == DEFAULT_TEMPLATE_ID

    root = tmp_path / "PipeProj"
    assert dlg.create_path(root, "PipeProj", template_id="internal-flow") is True
    cfg = load_config(root / "config" / "config.yaml")
    assert cfg.template_id() == "internal-flow"
