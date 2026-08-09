"""Neo v2.2 — Stage 3: Parameters + Images + Engineering Console.

Stage 3 is presentation-only. These tests lock in the new presentation
behaviour (engineering parameter captions, image metadata readout + empty
state, and the command console) while proving the redesigned panels still
satisfy the contracts the older suites rely on:

- Parameters: the form is still generated from metadata (`_sel_rows` /
  `_add_rows`, spin bounds + defaults), and the panel still scrolls.
- Images: thumbnails + zoomable preview still populate (`list`,
  `pix_item`), now with a real metadata readout and an empty state.
- Console: commands map *only* to signals the MainWindow wires to its
  existing public actions — no eval/exec, no backend access.

No engine, platform, StudyIO, or ExperimentDefinition file is touched.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt                                  # noqa: E402
from PySide6.QtGui import QPixmap                              # noqa: E402
from PySide6.QtWidgets import QApplication                     # noqa: E402

from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.platform import EXTERNAL_AERODYNAMICS             # noqa: E402
from cfdauto.simulation_context import SimulationContext       # noqa: E402
from gui.state import AppState                                 # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _state_for(template) -> AppState:
    st = AppState()
    st.context = SimulationContext(template=template)
    st.experiment_definition = ExperimentDefinition.from_context(st.context)
    return st


# --------------------------------------------------------------------- #
# Parameters — engineering control panel
# --------------------------------------------------------------------- #
def test_params_panel_has_section_header(qapp):
    from gui.panels.params_panel import ParamsPanel, _meta_caption
    panel = ParamsPanel(_state_for(EXTERNAL_AERODYNAMICS))
    # One row of study-param editors per metadata parameter (the first row is
    # the selection caption); structure is unchanged from before.
    assert panel.form.rowCount() == 1 + len(panel._sel_rows)
    assert [sp.name for sp, _ in panel._sel_rows] == ["aoa", "velocity"]
    # Caption strings are read from metadata — never hardcoded.
    aoa = EXTERNAL_AERODYNAMICS.parameter("aoa")
    assert _meta_caption(aoa) == "deg  ·  default 0"
    vel = EXTERNAL_AERODYNAMICS.parameter("velocity")
    assert _meta_caption(vel) == "m/s  ·  default 20"


def test_params_panel_still_scrolls_and_min_width(qapp):
    from gui.panels.params_panel import ParamsPanel
    from PySide6.QtWidgets import QScrollArea
    from gui import theme
    panel = ParamsPanel(AppState())
    assert isinstance(panel._scroll, QScrollArea)
    assert panel.minimumWidth() == theme.MIN_PANEL_WIDTH
    # Buttons / public attributes preserved.
    for name in ("sel_box", "add_box", "apply_btn", "skip_btn",
                 "add_btn", "dup_btn", "sel_lbl"):
        assert hasattr(panel, name)


# --------------------------------------------------------------------- #
# Images — metadata readout + empty state
# --------------------------------------------------------------------- #
def test_images_metadata_readout_on_load(qapp):
    from gui.panels.images_panel import ImagesPanel
    panel = ImagesPanel(_state_for(EXTERNAL_AERODYNAMICS))
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "contour.png"
        pm = QPixmap(200, 100)
        pm.fill(Qt.white)
        assert pm.save(str(p))
        panel._load(p)
    assert panel._meta_file.text() == "contour.png"
    assert panel._meta_dims.text() == "200 x 100 px"
    assert panel._meta_size.text() != "—"
    assert panel.path_lbl.text() == str(p)


def test_images_empty_state_when_no_case(qapp):
    from gui.panels.images_panel import ImagesPanel
    panel = ImagesPanel(_state_for(EXTERNAL_AERODYNAMICS))
    panel.refresh()                      # no case selected → no dir
    assert panel._stack.currentIndex() == 1   # empty state
    panel._show_workspace()
    assert panel._stack.currentIndex() == 0
    # Public attributes preserved.
    for name in ("case_box", "list", "scene", "pix_item", "view", "path_lbl"):
        assert hasattr(panel, name)


# --------------------------------------------------------------------- #
# Console — presentation-only command surface
# --------------------------------------------------------------------- #
def test_console_public_api_and_commands(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    assert set(c.commands) == {"help", "open", "run", "stop", "reload",
                               "mock", "clear"}
    for name in ("text", "input"):
        assert hasattr(c, name)


def test_console_empty_input_does_nothing(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    c.input.setText("   ")
    c._run_command()
    assert c.text.toPlainText() == ""


def test_console_unknown_command_message(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    c.input.setText("frobnicate")
    c._run_command()
    out = c.text.toPlainText()
    assert "Unknown command: frobnicate" in out
    assert 'Type "help" for available commands.' in out


def test_console_clear_empties(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    c.append("hello")
    assert c.text.toPlainText() == "hello"
    c.clear()
    assert c.text.toPlainText() == ""


def test_console_mapped_command_emits_signal(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    fired = []
    c.runRequested.connect(lambda: fired.append(True))
    c.input.setText("run")
    c._run_command()
    assert fired == [True]
    assert "slipstream" in c.text.toPlainText()     # echoed the prompt


def test_console_mock_on_off_and_toggle(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    sets, toggles = [], []
    c.mockSet.connect(lambda on: sets.append(on))
    c.mockToggleRequested.connect(lambda: toggles.append(True))
    c.input.setText("mock on"); c._run_command()
    c.input.setText("mock off"); c._run_command()
    c.input.setText("mock"); c._run_command()
    assert sets == [True, False]
    assert toggles == [True]


def test_console_history_navigation(qapp):
    from gui.panels.console import ConsolePanel
    c = ConsolePanel()
    c.input.setText("help"); c._run_command()
    c.input.setText("clear"); c._run_command()
    c._history_move(Qt.Key_Up)
    assert c.input.text() == "clear"
    c._history_move(Qt.Key_Up)
    assert c.input.text() == "help"
    c._history_move(Qt.Key_Down)
    assert c.input.text() == "clear"
    c._history_move(Qt.Key_Down)            # past the newest → cleared
    assert c.input.text() == ""


# --------------------------------------------------------------------- #
# MainWindow — bottom-dock integration + wiring to real actions
# --------------------------------------------------------------------- #
def _window(monkeypatch):
    from gui.main_window import MainWindow
    monkeypatch.setattr(MainWindow, "_open_project_selector", lambda self: None)
    return MainWindow()


def test_console_dock_tabbed_with_log(qapp, monkeypatch):
    win = _window(monkeypatch)
    assert win._docks["Console"].widget() is win.console
    assert win._docks["Console"] in win.tabifiedDockWidgets(win._docks["Log"])


def test_console_mock_wires_to_real_mock_action(qapp, monkeypatch):
    win = _window(monkeypatch)
    win.console._cmd_mock("on")
    assert win.state.effective_mock is True
    win.console._cmd_mock("off")
    assert win.state.effective_mock is False


def test_console_run_state_lines(qapp, monkeypatch):
    win = _window(monkeypatch)
    win._console_run_state(True)
    assert "batch running" in win.console.text.toPlainText()
    win._console_run_state(False)
    assert "batch idle" in win.console.text.toPlainText()
