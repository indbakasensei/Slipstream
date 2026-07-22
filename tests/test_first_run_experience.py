"""Sprint 6 — behavioral tests for the GUI's first-run experience.

Regression Scenario: a fresh clone (or a config path that no longer
exists) used to leave the user staring at an empty Dashboard with no
obvious next step. Expected Behaviour: MainWindow now proactively offers
the existing Project Selector (Sprint 5) instead — but only when no
project actually loaded; a normal launch with a valid config must behave
exactly as before. Why this test exists: proves the new behavior fires
exactly once, only when appropriate, without ever blocking on a real modal
dialog (QTimer.singleShot + Project Selector are monkeypatched here so the
test can process the deferred call deterministically instead of trusting
a wall-clock delay).
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


def test_first_run_with_no_config_schedules_project_selector(qapp, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(MainWindow, "_open_project_selector",
                        lambda self: calls.append(1))

    win = MainWindow(config_path=None)
    try:
        assert win.state.cfg is None
        qapp.processEvents()          # let the deferred QTimer.singleShot fire
        assert calls == [1]
    finally:
        win.close()
        qapp.processEvents()


def test_first_run_with_missing_config_path_schedules_project_selector(qapp, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(MainWindow, "_open_project_selector",
                        lambda self: calls.append(1))

    win = MainWindow(config_path=str(tmp_path / "does_not_exist.yaml"))
    try:
        qapp.processEvents()
        assert calls == [1]
    finally:
        win.close()
        qapp.processEvents()


def test_normal_launch_with_valid_config_does_not_show_project_selector(qapp, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(MainWindow, "_open_project_selector",
                        lambda self: calls.append(1))

    xlsx = tmp_path / "experiments.xlsx"
    build_template(xlsx)
    cfg = tmp_path / "config.yaml"
    cfg.write_text(CONFIG_TPL.format(xlsx=xlsx.as_posix(),
                                     work=(tmp_path / "runs").as_posix()))

    win = MainWindow(config_path=str(cfg))
    try:
        assert win.state.cfg is not None
        qapp.processEvents()
        assert calls == []            # unchanged existing behavior: no popup
    finally:
        win.close()
        qapp.processEvents()
