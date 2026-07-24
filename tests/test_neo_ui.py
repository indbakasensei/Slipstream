"""UX Milestone 1 — Slipstream Neo UI (presentation only).

Snapshot-style checks for the design system (token scales, palette, stylesheet
coverage), the shared components (Card, StatusChip), and the redesigned Monitor
— including that it still renders purely from engine events and preserves its
public API. No business logic is exercised.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication                   # noqa: E402

from gui import theme                                        # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app)
    return app


def _evt(t, **data):
    return SimpleNamespace(type=t, data=data)


# --------------------------------------------------------------------- #
# Design system
# --------------------------------------------------------------------- #
def test_spacing_scale_is_4_based_and_complete():
    assert [theme.SPACE_XS, theme.SPACE_SM, theme.SPACE_MD, theme.SPACE_LG,
            theme.SPACE_XL, theme.SPACE_2XL, theme.SPACE_3XL] == \
        [4, 8, 12, 16, 24, 32, 48]


def test_radius_and_type_scales():
    assert (theme.RADIUS_SM, theme.RADIUS, theme.RADIUS_LG) == (6, 8, 12)
    assert theme.FONT_SIZE_DISPLAY > theme.FONT_SIZE_H1 > theme.FONT_SIZE_H2
    assert theme.FONT_SIZE_BODY > theme.FONT_SIZE_CAPTION


def test_semantic_colour_tokens_present():
    for name in ("BG_WINDOW", "SURFACE", "SURFACE_ELEVATED", "ACCENT",
                 "SUCCESS", "WARNING", "ERROR", "INFO", "BORDER", "GRID",
                 "FOCUS", "SELECTION", "TEXT", "TEXT_DIM", "TEXT_FAINT"):
        val = getattr(theme, name)
        assert isinstance(val, str) and val.startswith("#") or val in (
            theme.ACCENT, theme.ACCENT_DIM)  # FOCUS/SELECTION alias tokens


def test_stylesheet_restyles_core_widgets(qapp):
    qss = qapp.styleSheet()
    for selector in ("QTableView", "QPushButton", "QHeaderView::section",
                     "QScrollBar", "QTabBar::tab", 'QFrame[card="true"]',
                     "QToolTip", "QMenu"):
        assert selector in qss, f"stylesheet missing {selector}"


# --------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------- #
def test_card_header_body_and_accessory(qapp):
    from PySide6.QtWidgets import QLabel
    from gui.widgets import Card
    c = Card("Current Study", "live")
    assert c.property("card") is True
    assert c.title_lbl.text() == "Current Study"
    assert c.caption_lbl.text() == "live"
    w = c.add(QLabel("body"))
    assert c.body.indexOf(w) >= 0
    c.set_accessory(QLabel("chip"))          # no raise


def test_status_chip_recolours(qapp):
    from gui.widgets import StatusChip
    chip = StatusChip("Idle", "idle")
    assert chip.text() == "Idle"
    chip.set_state("Running", "RUNNING")
    assert chip.text() == "Running"
    assert theme.STATUS_COLORS["RUNNING"].lstrip("#").lower() in \
        chip.styleSheet().lower()


# --------------------------------------------------------------------- #
# Monitor redesign — cards + live-from-events, API preserved
# --------------------------------------------------------------------- #
def test_monitor_has_neo_cards_and_preserved_api(qapp):
    from gui.panels.monitor import MonitorPanel
    m = MonitorPanel()
    # New Neo surfaces.
    for attr in ("status_chip", "eta_lbl", "timeline", "_metric_vals"):
        assert hasattr(m, attr)
    assert set(m._metric_vals) == {"iterations", "residual", "cl", "cd"}
    # Preserved public API (app/tests depend on these).
    for attr in ("bar", "pipeline", "forces", "residuals", "cl_curve",
                 "cd_curve", "_tabs", "_scroll", "handle_event",
                 "_append_iteration", "_reset_case"):
        assert hasattr(m, attr)
    assert m._tabs.minimumHeight() == theme.MIN_PLOT_HEIGHT
    assert m.minimumWidth() == theme.MIN_PANEL_WIDTH


def test_monitor_updates_live_from_events(qapp):
    from gui.panels.monitor import MonitorPanel
    m = MonitorPanel()
    m.handle_event(_evt("case.started", index=1, total=8, case_id="r001",
                        aoa=0, velocity=20))
    assert m.status_chip.text() == "Running"
    assert m.timeline.count() >= 1

    m.handle_event(_evt("fluent.iteration", it=100, cl=0.5, cd=0.02,
                        max_it=1000, residuals={"continuity": 1e-3}))
    assert m._metric_vals["iterations"].text() == "100"
    assert m._metric_vals["cl"].text() == "0.5000"
    assert m._metric_vals["cd"].text() == "0.02000"
    assert m.bar.value() > 25          # progress advanced with the iteration

    m.handle_event(_evt("solve.converged", it=100))
    assert m.status_chip.text() == "Converged"

    m.handle_event(_evt("case.done", case_id="r001"))
    assert m.bar.value() == 100        # preserved behaviour the smoke test asserts
    newest = m.timeline.item(0).text()
    assert "Results written" in newest
