"""GUI smoke test — the whole v0.8 shell, offscreen, against the mock engine.

Skipped automatically when PySide6/pyqtgraph aren't installed (e.g. on a
CLI-only machine); in CI/dev containers it exercises: project load, Run All
through the EngineWorker thread, live event handling in every panel, dataset
refresh, chart population, mock contour images, and resume semantics.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication          # noqa: E402

from gui.main_window import MainWindow              # noqa: E402
from gui.theme import apply_theme                   # noqa: E402
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


def _pump_until(qapp, predicate, timeout_s: float = 60.0) -> None:
    t0 = time.monotonic()
    while not predicate():
        qapp.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout_s:
            raise TimeoutError("GUI smoke test timed out")


def test_full_gui_mock_batch(qapp, project):
    win = MainWindow(config_path=str(project))
    try:
        # -- project loaded ------------------------------------------------
        assert len(win.state.df) == 8                    # 4 AOA × 2 V template
        assert win.queue.table.rowCount() == 8
        assert win.tabs.count() == 4

        # -- run everything through the worker thread ----------------------
        win.start_run()
        assert win.state.running
        _pump_until(qapp, lambda: not win.state.running)
        if win.worker:                                    # reaped in handler
            win.worker.wait(5000)

        df = win.state.df
        assert list(df["Status"].unique()) == ["DONE"]
        assert df["CL"].notna().all() and df["CD"].notna().all()

        # -- panels reflected the batch -------------------------------------
        assert win.monitor.bar.value() == 100
        assert win.monitor.pipeline.states["solve"] == "done"
        assert win.dashboard.cards["DONE"].value_lbl.text() == "8"
        assert win.dashboard.recent.count() > 0
        win.charts.refresh()
        assert win.charts.point_count() == 8
        assert "Best L/D" in win.stats.best.text()

        # -- mock contour images visible in the Images panel ----------------
        win.state.select_case(int(df["Row"].iloc[0]))
        qapp.processEvents()
        win.images.refresh()
        assert win.images.list.count() >= 4               # 4 demo PNGs/case
        assert win.images.pix_item.pixmap().width() > 0

        # -- log console received engine lines ------------------------------
        assert "Batch finished" in win.log_panel.text.toPlainText()

        # -- resume semantics: second run finds nothing to do ---------------
        win.start_run()
        _pump_until(qapp, lambda: not win.state.running, 20)
        assert (win.state.df["Status"] == "DONE").all()
    finally:
        win.close()
        qapp.processEvents()


def test_stop_after_current_case(qapp, project):
    win = MainWindow(config_path=str(project))
    try:
        win.start_run()
        # Ask for a stop as soon as the first case starts; the graceful stop
        # finishes that case and halts the rest.
        _pump_until(qapp, lambda: win.sb_engine.text().startswith(
            "engine: case"), 20)
        win.worker.request_stop()
        _pump_until(qapp, lambda: not win.state.running, 30)
        statuses = set(win.state.df["Status"])
        assert "DONE" in statuses and "PENDING" in statuses
    finally:
        win.close()
        qapp.processEvents()
