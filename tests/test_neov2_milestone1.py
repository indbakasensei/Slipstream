"""Neo UI v2, Milestone 1 — Workspace Revolution (presentation only).

Minimal tests for the *genuinely new* reusable components introduced in this
milestone: the IconFactory, NavigationButton, BrandHeader, PageHeader /
WorkspaceHeader, StatusBadgeDelegate, EmptyState, and the premium Sidebar
composition. No business logic is exercised, and no pre-existing test is
modified — the old contract keeps living in test_sidebar/test_neo_ui/
test_ui_foundation/test_gui_smoke, which are untouched.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QPainter, QPixmap                       # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel, QStyleOptionViewItem,  # noqa: E402
                               QTableWidget, QTableWidgetItem)
from gui import theme                                          # noqa: E402
from gui.widgets.brand_header import BrandHeader                # noqa: E402
from gui.widgets.badge_delegate import StatusBadgeDelegate      # noqa: E402
from gui.widgets.empty_state import EmptyState                  # noqa: E402
from gui.widgets.icons import icon_names, make_icon             # noqa: E402
from gui.widgets.nav_button import NavigationButton             # noqa: E402
from gui.widgets.sidebar import WORKSPACE_PAGES, Sidebar        # noqa: E402
from gui.widgets.workspace_header import WorkspaceHeader        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


# --------------------------------------------------------------------- #
# IconFactory
# --------------------------------------------------------------------- #
def test_icon_factory_has_expected_names_and_renders(qapp):
    assert "dashboard" in icon_names()
    assert "run" in icon_names()
    icon = make_icon("dashboard", theme.ACCENT, 18)
    assert icon is not None
    assert not icon.isNull()
    # Unknown names degrade to None (text-only fallback), never crash.
    assert make_icon("no_such_icon", theme.TEXT) is None


# --------------------------------------------------------------------- #
# NavigationButton
# --------------------------------------------------------------------- #
def test_navigation_button_is_a_checkable_push_button(qapp):
    btn = NavigationButton("Dashboard", icon="dashboard")
    assert btn.isCheckable() is True
    assert btn.text() == "Dashboard"
    btn.setChecked(True)
    assert btn.isChecked() is True


def test_navigation_button_set_active_toggles_state_and_property(qapp):
    btn = NavigationButton("Charts", icon="charts")
    btn.set_active(True)
    assert btn.isChecked() is True
    assert btn.property("active") is True
    btn.set_active(False)
    assert btn.isChecked() is False
    assert btn.property("active") is False


# --------------------------------------------------------------------- #
# BrandHeader / PageHeader / WorkspaceHeader
# --------------------------------------------------------------------- #
def test_brand_header_shows_name_tagline_and_version(qapp):
    bh = BrandHeader(name="SLIPSTREAM", tagline="Universal CFD Platform",
                     version="9.9.9")
    assert bh.name_lbl.text() == "SLIPSTREAM"
    assert bh.tagline_lbl.text() == "Universal CFD Platform"
    assert bh.version_lbl.text() == "9.9.9"


def test_workspace_header_updates_page_and_context(qapp):
    wh = WorkspaceHeader()
    wh.set_page("charts", "Charts")
    assert wh.page_id == "charts"
    assert wh.title_lbl.text() == "Charts"
    wh.set_context("Wing Sweep", "External Aerodynamics", "experiments.xlsx")
    sub = wh.subtitle_lbl.text()
    assert "Wing Sweep" in sub and "External Aerodynamics" in sub
    wh.set_context("", "", "")
    assert wh.subtitle_lbl.text() == ""


# --------------------------------------------------------------------- #
# StatusBadgeDelegate — paint-only, never crashes offscreen
# --------------------------------------------------------------------- #
def test_badge_delegate_paints_a_status_cell(qapp):
    table = QTableWidget(1, 1)
    delegate = StatusBadgeDelegate()
    table.setItemDelegate(delegate)
    table.setItem(0, 0, QTableWidgetItem("DONE"))
    table.resize(120, 40)
    pm = QPixmap(120, 40)
    pm.fill()
    painter = QPainter(pm)
    opt = QStyleOptionViewItem()
    opt.initFrom(table)
    opt.font = table.font()
    opt.rect = table.visualRect(table.model().index(0, 0))
    delegate.paint(painter, opt, table.model().index(0, 0))
    painter.end()
    # Underlying item data is untouched (text survives for sort/selection).
    assert table.item(0, 0).text() == "DONE"


# --------------------------------------------------------------------- #
# EmptyState
# --------------------------------------------------------------------- #
def test_empty_state_shows_title_hint_and_emits_action(qapp):
    es = EmptyState("No Project Loaded", "Open or create a project.",
                    action_text="Open Project…")
    assert es.title_lbl.text() == "No Project Loaded"
    assert es.hint_lbl.text().startswith("Open or create")
    seen = []
    es.actionClicked.connect(lambda: seen.append(True))
    es.action_btn.click()
    assert seen == [True]


# --------------------------------------------------------------------- #
# Sidebar composition parity — behavior contract preserved
# --------------------------------------------------------------------- #
def test_sidebar_still_navigates_exactly_as_before(qapp):
    sb = Sidebar(QLabel("explorer placeholder"))
    assert list(sb._nav_buttons) == [p[0] for p in WORKSPACE_PAGES]
    assert sb.current_page() == WORKSPACE_PAGES[0][0]
    assert sb.project_section.is_expanded() is True
    for btn in sb._nav_buttons.values():
        assert btn.isCheckable() is True

    seen = []
    sb.pageRequested.connect(seen.append)
    sb._nav_buttons["charts"].click()
    assert seen == ["charts"]
    assert sb.current_page() == "charts"
    assert sb._nav_buttons["charts"].isChecked() is True
    assert sb._nav_buttons["dashboard"].isChecked() is False
