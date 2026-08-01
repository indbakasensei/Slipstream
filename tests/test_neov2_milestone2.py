"""Neo UI v2, Milestone 2 — Dashboard Revolution (presentation only).

Tests for the genuinely new components of this milestone: KpiCard,
HeroHeader, ActivityFeed, QuickActionsPanel, the responsive _FlowLayout, and
the public-API preservation contract of the rebuilt DashboardPanel. No
business logic is exercised and no pre-existing test is modified — the old
contract keeps living in test_gui_smoke / test_ui_foundation / test_neo_ui /
test_sidebar, which are untouched.
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

from PySide6.QtCore import QSize, Qt                         # noqa: E402
from PySide6.QtWidgets import (QApplication, QLabel, QListWidget,  # noqa: E402
                               QPushButton, QWidget)
from gui import theme                                     # noqa: E402
from gui.state import AppState                            # noqa: E402
from gui.widgets import (ActivityFeed, HeroHeader, KpiCard,  # noqa: E402
                         QuickActionsPanel)
from gui.widgets.icons import icon_names                  # noqa: E402
from gui.panels.dashboard import DashboardPanel, _FlowLayout  # noqa: E402
from tools.make_experiment_template import build_template  # noqa: E402

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
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


@pytest.fixture()
def state(qapp) -> AppState:
    return AppState()


@pytest.fixture()
def project(tmp_path: Path):
    xlsx = tmp_path / "experiments.xlsx"
    build_template(xlsx)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG_TPL.format(xlsx=xlsx.as_posix(),
                                     work=(tmp_path / "runs").as_posix()))
    return cfg


# --------------------------------------------------------------------- #
# KpiCard
# --------------------------------------------------------------------- #
def test_kpi_card_renders_value_caption_and_status_color(qapp):
    card = KpiCard("Done", theme.STATUS_COLORS["DONE"], icon="check")
    card.set_value("8")
    assert card.value_lbl.text() == "8"
    assert card.caption_lbl.text() == "Done"
    # the top accent bar carries the status colour
    assert theme.STATUS_COLORS["DONE"] in card.accent.styleSheet()


def test_kpi_card_preserves_statcard_interface(qapp):
    """KpiCard must duck-type StatCard: value_lbl + set_value() + min height."""
    card = KpiCard("Pending", theme.STATUS_COLORS["PENDING"])
    assert hasattr(card, "value_lbl")
    assert hasattr(card, "set_value")
    card.set_value("12")
    assert card.value_lbl.text() == "12"
    assert card.minimumHeight() >= 96


def test_kpi_card_unknown_icon_degrades_gracefully(qapp):
    card = KpiCard("X", icon="no_such_icon")
    assert card.icon_lbl.isHidden()          # text-only fallback, no crash


def test_kpi_card_trend_hint_shows_positive_and_negative(qapp):
    card = KpiCard("Success Rate", theme.SUCCESS)
    card.set_trend("↑ 3% vs last batch", positive=True)
    assert theme.SUCCESS in card.trend_lbl.styleSheet()
    card.set_trend("↓ 1% vs last batch", positive=False)
    assert theme.ERROR in card.trend_lbl.styleSheet()
    card.set_trend("")
    assert card.trend_lbl.isHidden()


# --------------------------------------------------------------------- #
# HeroHeader
# --------------------------------------------------------------------- #
def test_hero_header_displays_project_info(qapp):
    hero = HeroHeader()
    hero.set_project("wing_sweep", "External Aerodynamics",
                     "Sweep AOA at two freestream velocities.")
    assert hero.project_lbl.text() == "wing_sweep"
    assert hero.meta_lbl.text() == "External Aerodynamics"
    assert "Sweep AOA" in hero.desc_lbl.text()


def test_hero_header_mock_badge_toggles(qapp):
    hero = HeroHeader()
    hero.set_mock(True)
    assert hero.badge_lbl.text() == "MOCK"
    assert not hero.badge_lbl.isHidden()
    hero.set_mock(False)
    assert hero.badge_lbl.text() == "REAL"
    assert not hero.badge_lbl.isHidden()


def test_hero_header_signals_and_status(qapp):
    hero = HeroHeader()
    seen = []
    hero.runClicked.connect(lambda: seen.append("run"))
    hero.openProjectClicked.connect(lambda: seen.append("open"))
    hero.actionClicked.connect(lambda a: seen.append(a))
    hero.run_btn.click()
    hero.open_btn.click()
    hero.report_btn.click()
    assert seen == ["run", "open", "report"]
    hero.set_status(True, 50)
    assert "running" in hero.status_lbl.text().lower()
    assert "50%" in hero.progress_lbl.text()
    hero.set_solver("ansys-fluent")
    assert hero.solver_lbl.text() == "ansys-fluent"


def test_hero_header_idle_state(qapp):
    hero = HeroHeader()
    hero.set_project("", "", "")
    assert hero.project_lbl.text() == "No project loaded"


# --------------------------------------------------------------------- #
# ActivityFeed
# --------------------------------------------------------------------- #
def test_activity_feed_push_and_count(qapp):
    feed = ActivityFeed()
    assert feed.count == 0
    feed.push("case r001 started", kind="started")
    feed.push("case r001 done", kind="done")
    assert feed.count == 2
    # raw text survives on the underlying items (queryable, sortable)
    assert feed.list.item(0).data(Qt.UserRole) == "case r001 done"


def test_activity_feed_caps_row_count(qapp):
    feed = ActivityFeed()
    for i in range(20):
        feed.push(f"event {i}", kind="info")
    assert feed.count == ActivityFeed.MAX_ROWS


def test_activity_feed_uses_qlistwidget(qapp):
    """DashboardPanel.recent is the feed's list — count() is the raw list."""
    feed = ActivityFeed()
    assert isinstance(feed.list, QListWidget)


# --------------------------------------------------------------------- #
# QuickActionsPanel
# --------------------------------------------------------------------- #
def test_quick_actions_emits_action_id(qapp):
    panel = QuickActionsPanel()
    seen = []
    panel.actionTriggered.connect(seen.append)
    panel._buttons["open"].click()
    panel._buttons["run"].click()
    panel._buttons["report"].click()
    assert seen == ["open", "run", "report"]


def test_quick_actions_disable_single_action(qapp):
    panel = QuickActionsPanel()
    panel.set_action_enabled("run", False)
    assert panel._buttons["run"].isEnabled() is False
    assert panel._buttons["open"].isEnabled() is True


# --------------------------------------------------------------------- #
# Responsive flow layout
# --------------------------------------------------------------------- #
class _Tile(QWidget):
    """A tile with a real, explicit size hint (bare QWidget's is invalid)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hint = QSize(300, 80)

    def sizeHint(self):
        return self._hint


def _flow_container():
    """A shown container with the flow layout installed (required for the
    item size hints to become real, mirroring the dashboard's own usage)."""
    container = QWidget()
    flow = _FlowLayout(spacing=8)
    container.setLayout(flow)
    flow.addWidget(_Tile())
    flow.addWidget(_Tile())
    container.resize(700, 300)
    container.show()
    QApplication.instance().processEvents()
    return container, flow


def test_flow_layout_wraps_when_narrow(qapp):
    """Two wide tiles share one row when wide, stack when narrow."""
    container, flow = _flow_container()
    wide_h = flow.heightForWidth(700)            # 300+8+300 = 608 < 700 → one row
    narrow_h = flow.heightForWidth(350)          # only 300 fits → two rows
    assert wide_h == 80
    assert narrow_h == 80 + 8 + 80               # wrapped → taller
    assert narrow_h > wide_h
    container.close()


def test_flow_layout_counts_items(qapp):
    container, flow = _flow_container()
    assert flow.count() == 2
    assert flow.itemAt(1) is not None
    assert flow.itemAt(9) is None
    container.close()


# --------------------------------------------------------------------- #
# Dashboard public-API preservation contract
# --------------------------------------------------------------------- #
def test_dashboard_preserves_all_public_api(qapp, state):
    d = DashboardPanel(state)
    # attributes (types must match the pre-milestone surface)
    assert isinstance(d.title, QLabel)
    assert isinstance(d.subtitle, QLabel)
    assert isinstance(d.run_btn, QPushButton)
    assert set(d.cards) == {"PENDING", "RUNNING", "DONE", "FAILED"}
    assert hasattr(d.progress, "setValue")
    assert d.pipeline is not None
    assert isinstance(d.pipe_lbl, QLabel)
    assert d.chart is not None
    assert d.recent is not None                 # QListWidget
    assert d.study_overview is not None
    assert d.study_summary is not None
    # signals + methods
    assert d.runAllRequested is not None
    assert d.openProjectRequested is not None
    for m in ("refresh", "handle_event", "push_recent", "set_study_summary"):
        assert callable(getattr(d, m))


def test_dashboard_kpi_cards_are_statcard_compatible(qapp, state):
    d = DashboardPanel(state)
    for key in ("PENDING", "RUNNING", "DONE", "FAILED"):
        card = d.cards[key]
        card.set_value("3")
        assert card.value_lbl.text() == "3"
    assert d.rate_card.value_lbl.text() is not None
    assert d.time_card.value_lbl.text() is not None


def test_dashboard_empty_state_then_project_load(qapp, state, project):
    d = DashboardPanel(state)
    assert d._stack.currentIndex() == 0          # empty state shown first
    state.load_project(project)
    assert d._stack.currentIndex() == 1          # content after load
    assert d.title.text() == project.stem
    assert d.subtitle.text() == "External Aerodynamics"
    assert d.hero_header.badge_lbl.text() == "MOCK"
    assert d.cards["PENDING"].value_lbl.text() == "8"
    # live run events populate the activity feed
    d.push_recent("r001 done", kind="done")
    assert d.recent.count() > 0


def test_dashboard_quick_actions_route_to_signals(qapp, state, project):
    d = DashboardPanel(state)
    state.load_project(project)
    seen = []
    d.openProjectRequested.connect(lambda: seen.append("open"))
    d.runAllRequested.connect(lambda: seen.append("run"))
    d.quick_actions._buttons["open"].click()
    d.quick_actions._buttons["run"].click()
    assert seen == ["open", "run"]


# --------------------------------------------------------------------- #
# New icons
# --------------------------------------------------------------------- #
def test_new_kpi_icons_available(qapp):
    for name in ("check", "alert", "clock"):
        assert name in icon_names()
