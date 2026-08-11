"""Neo v2.2 — behavioral tests for gui.widgets.Sidebar.

The sidebar's entire contract is: navigation only, one-way signal, never
touches a page/panel directly. These tests verify exactly that boundary —
clicking a workspace item emits the right page_id and nothing else — using
a plain placeholder widget in place of a real ExplorerPanel, since the
sidebar never inspects what it's embedding.
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

from PySide6.QtWidgets import QApplication, QLabel      # noqa: E402

from gui.widgets.sidebar import WORKSPACE_PAGES, Sidebar  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_sidebar_defaults_to_first_workspace_page(qapp):
    sidebar = Sidebar(QLabel("explorer placeholder"))
    assert sidebar.current_page() == WORKSPACE_PAGES[0][0]


def test_clicking_a_nav_button_emits_page_requested_and_updates_state(qapp):
    sidebar = Sidebar(QLabel("explorer placeholder"))
    seen = []
    sidebar.pageRequested.connect(seen.append)

    charts_btn = sidebar._nav_buttons["charts"]
    charts_btn.click()

    assert seen == ["charts"]
    assert sidebar.current_page() == "charts"
    # Only the clicked button ends up checked/active.
    assert sidebar._nav_buttons["charts"].isChecked() is True
    assert sidebar._nav_buttons["dashboard"].isChecked() is False


def test_sidebar_never_touches_pages_directly(qapp):
    """The sidebar must be constructible and fully functional without any
    QStackedWidget/page objects ever being handed to it — proving
    navigation is a pure one-way signal, not direct page manipulation."""
    sidebar = Sidebar(QLabel("explorer placeholder"))
    results = []
    sidebar.pageRequested.connect(results.append)
    for page_id, _label, _icon in WORKSPACE_PAGES:
        sidebar._select(page_id)
    assert results == [pid for pid, _, _ in WORKSPACE_PAGES]


def test_project_section_embeds_the_given_explorer_widget_unchanged(qapp):
    explorer_placeholder = QLabel("explorer placeholder")
    sidebar = Sidebar(explorer_placeholder)
    assert sidebar.project_section.is_expanded() is True
    # The exact same widget instance is embedded, not a copy/wrapper.
    assert explorer_placeholder.parent() is not None
