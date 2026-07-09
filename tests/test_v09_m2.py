"""v0.9 M2 telemetry tests.

Covers the tap in isolation (synthetic files, no ANSYS) and end-to-end
through the mock engine + GUI Monitor panel."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# --- Tap: reads new rows only, decodes residuals, drains cleanly --------- #
def test_telemetry_tap_streams_history_rows(tmp_path):
    from cfdauto.telemetry import TelemetryTap

    hist = tmp_path / "history.out"
    trn = tmp_path / "transcript.trn"
    hist.write_text(
        '"cfdauto_history"\n'
        '"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
        "1 0.100 0.010\n"
        "2 0.150 0.011\n"
        "3 0.180 0.012\n"
    )
    trn.write_text("")

    events: List[dict] = []
    def emit(t, **d): events.append({"type": t, **d})

    tap = TelemetryTap(hist, trn, emit, max_it=100, poll_hz=1000)
    tap._poll_once()

    its = [e["it"] for e in events]
    assert its == [1, 2, 3]
    assert events[0]["cl"] == 0.100 and events[0]["cd"] == 0.010

    # Appending must only produce new rows.
    hist.write_text(hist.read_text() + "4 0.200 0.013\n")
    tap._poll_once()
    assert [e["it"] for e in events][-1] == 4


def test_telemetry_tap_correlates_residuals(tmp_path):
    from cfdauto.telemetry import TelemetryTap

    hist = tmp_path / "history.out"
    trn = tmp_path / "transcript.trn"
    hist.write_text(
        '"cfdauto_history"\n'
        '"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
    )
    trn.write_text(
        "  iter  continuity  x-velocity  y-velocity  z-velocity  k  omega\n"
        "     1   1.0e-2      2.0e-3      2.0e-3      1.5e-3      3e-3  4e-3\n"
        "     2   5.0e-3      1.5e-3      1.5e-3      1.0e-3      2e-3  3e-3\n"
    )
    hist.write_text(hist.read_text() + "1 0.10 0.010\n2 0.15 0.011\n")

    events: List[dict] = []
    tap = TelemetryTap(hist, trn, lambda t, **d: events.append(d),
                       max_it=100, poll_hz=1000)
    tap._poll_once()

    assert len(events) == 2
    r1 = events[0]["residuals"]
    assert r1["continuity"] == pytest.approx(1e-2, rel=1e-3)
    assert r1["omega"] == pytest.approx(4e-3, rel=1e-3)


def test_telemetry_tap_missing_files_ok(tmp_path):
    from cfdauto.telemetry import TelemetryTap
    tap = TelemetryTap(tmp_path / "nope.out", tmp_path / "nope.trn",
                       lambda t, **d: None, max_it=1)
    tap._poll_once()                                # no exceptions


# --- Mock engine now emits fluent.iteration per iteration ---------------- #
def test_mock_emits_per_iteration_events(tmp_path):
    from cfdauto.config import load_config
    from cfdauto.events import EventBus
    from cfdauto.excel_manager import ExcelManager
    from cfdauto.mocks import MockFluentController, MockWorkbenchController
    from tools.make_experiment_template import build_template

    xlsx = tmp_path / "e.xlsx"
    build_template(xlsx)
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(f"""
excel: {{file: "{xlsx.as_posix()}"}}
runtime: {{work_dir: "{(tmp_path / 'runs').as_posix()}", mock: true}}
fluent: {{aoa_method: geometry, wall_zones: [wing]}}
""")
    cfg = load_config(cfg_path)
    bus = EventBus()
    events: List[dict] = []
    bus.subscribe(lambda e: events.append({"type": e.type, **e.data}))

    wb = MockWorkbenchController(cfg, bus=bus)
    fl = MockFluentController(cfg, bus=bus)
    exp = ExcelManager(cfg.excel).read_experiments()[0]
    case_dir = tmp_path / "case"; case_dir.mkdir()
    mesh = wb.prepare_mesh(exp, case_dir)
    fl.run_case(exp, mesh, case_dir)

    it_events = [e for e in events if e["type"] == "fluent.iteration"]
    assert len(it_events) >= 20
    # Iterations must be monotonically increasing, residuals present.
    its = [e["it"] for e in it_events]
    assert its == sorted(its)
    assert "residuals" in it_events[0]
    assert it_events[-1]["residuals"]["continuity"] > 0


# --- GUI Monitor consumes both event types ------------------------------ #
if os.environ.get("QT_QPA_PLATFORM", "") == "offscreen" or True:
    pytest.importorskip("PySide6")
    pytest.importorskip("pyqtgraph")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication      # noqa: E402
    from cfdauto.events import Event                # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_monitor_renders_per_iteration_and_residuals(qapp):
    from gui.panels.monitor import MonitorPanel
    mon = MonitorPanel()

    mon.handle_event(Event("case.started",
                           {"row": 2, "case_id": "r002_test",
                            "index": 1, "total": 1,
                            "aoa": 4.0, "velocity": 20.0, "extra": {}}))
    mon.handle_event(Event("stage",
                           {"row": 2, "case_id": "r002_test",
                            "stage": "solve", "state": "start"}))
    for it in range(1, 51):
        mon.handle_event(Event("fluent.iteration", {
            "row": 2, "case_id": "r002_test",
            "it": it, "max_it": 500,
            "cl": 0.02 * it, "cd": 0.001 * it,
            "residuals": {"continuity": 1e-2 / it,
                          "x_velocity": 5e-3 / it,
                          "y_velocity": 5e-3 / it,
                          "z_velocity": 3e-3 / it,
                          "k": 4e-3 / it,
                          "omega": 4e-3 / it}}))
    assert len(mon._its) == 50
    assert mon._its[-1] == 50
    assert mon._cl[-1] == pytest.approx(1.0)
    assert mon._residuals_seen is True
    assert "residuals live" in mon.info_lbl.text()
    # Progress bar advanced to somewhere between the setup baseline and 95%
    assert 25 < mon.bar.value() < 95


def test_monitor_falls_back_to_solve_progress(qapp):
    """A pre-M2 engine only emits solve.progress; Monitor must still plot."""
    from gui.panels.monitor import MonitorPanel
    mon = MonitorPanel()
    mon.handle_event(Event("case.started",
                           {"row": 2, "case_id": "r002_test",
                            "index": 1, "total": 1,
                            "aoa": 4.0, "velocity": 20.0, "extra": {}}))
    for it in (100, 200, 300):
        mon.handle_event(Event("solve.progress", {
            "row": 2, "case_id": "r002_test",
            "it": it, "max_it": 500, "cl": 0.5, "cd": 0.02}))
    assert mon._its == [100, 200, 300]
    assert not mon._residuals_seen
