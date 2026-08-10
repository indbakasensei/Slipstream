"""Visual verification capture for Neo UI v2.2 (Workspace Revolution).

Renders the redesigned shell offscreen and saves PNGs of every milestone
surface: Startup (empty state), Dashboard, Sidebar, Queue, Monitor, Charts,
and the Stage 3 Parameters / Images / Console panels plus a full workspace
shot. Runs the mock engine so the panels are fully populated with real data.

Robustness (v2): every wait is bounded and *best-effort* — a predicate that
never becomes true logs ``TIMEOUT`` and we capture whatever state we reached,
rather than aborting the whole run. Progress is streamed to stderr so a
supervised run stays observable.

Usage:  python _screens/capture.py
Output: _screens/*.png (next to this file)
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt                         # noqa: E402
from PySide6.QtGui import QFontDatabase               # noqa: E402
from PySide6.QtWidgets import QApplication            # noqa: E402

from gui.main_window import MainWindow                # noqa: E402
from gui.theme import apply_theme                     # noqa: E402
from tools.make_experiment_template import build_template  # noqa: E402


def _load_offscreen_fonts() -> None:
    """Load system fonts from disk for offscreen rendering.

    The Qt offscreen QPA cannot enumerate system fonts, so every glyph
    renders as □.  Loading the actual .ttf files via
    ``QFontDatabase.addApplicationFont`` makes the same typefaces
    (Segoe UI, Arial, Cascadia Code) available for capture without
    changing the application's own font configuration.  This is a
    capture-time fix only — the running app on a real display never
    needs it.
    """
    import glob as _glob
    import sys as _sys
    candidates = {
        "Segoe UI": ["segoeui.ttf"],
        "Arial":    ["arial.ttf"],
        "Cascadia Code": ["CascadiaCode.ttf", "CascadiaCode-Regular.ttf"],
    }
    if _sys.platform == "win32":
        font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    elif _sys.platform == "darwin":
        font_dir = "/Library/Fonts"
    else:
        font_dir = "/usr/share/fonts"
    for _family, names in candidates.items():
        for name in names:
            path = os.path.join(font_dir, name)
            if os.path.isfile(path):
                QFontDatabase.addApplicationFont(path)
                break

# A config-less MainWindow defers a *modal* project-selector dialog via
# QTimer.singleShot(0, self._open_project_selector) — the bound method is
# captured at construction, so patching the instance later does nothing.
# Neutralize the class method BEFORE building any window, exactly as
# tests/test_ui_foundation.py does, or the modal exec() blocks the offscreen
# pump forever once the first processEvents() fires the timer.
MainWindow._open_project_selector = lambda self: None

OUT = Path(__file__).resolve().parent
OUT.mkdir(exist_ok=True)

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


def log(msg: str) -> None:
    print(f"[capture] {msg}", file=sys.stderr, flush=True)


def _pump_until(app, pred, timeout_s=90.0, label="wait") -> bool:
    """Pump the event loop until ``pred()`` is true or timeout. Never raises —
    returns True on success, False on timeout (caller captures anyway)."""
    t0 = time.monotonic()
    while not pred():
        app.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout_s:
            log(f"TIMEOUT after {timeout_s:.0f}s: {label} — continuing anyway")
            return False
    log(f"OK ({time.monotonic() - t0:.1f}s): {label}")
    return True


def _save(widget, name: str) -> None:
    try:
        pm = widget.grab()
        path = OUT / f"{name}.png"
        ok = pm.save(str(path))
        log(f"{'saved' if ok else 'FAILED'}  {name}.png "
            f"({widget.width()}x{widget.height()})")
    except Exception as exc:                                    # pragma: no cover
        log(f"ERROR saving {name}.png: {exc}")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    _load_offscreen_fonts()
    apply_theme(app)

    # -- 1. Startup / no-project (empty state) ----------------------------
    log("--- capture 1/6: startup empty state ---")
    win0 = MainWindow()
    win0.resize(1480, 900)
    _pump_until(app, lambda: win0._center_stack.currentIndex() == 0,
                label="startup center stack at empty state")
    _save(win0, "startup_empty_state")

    # -- 2. Loaded project, run a full mock batch -------------------------
    log("--- capture 2/6: loaded project + mock batch ---")
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="neov2_capture_"))
    xlsx = tmp / "experiments.xlsx"
    build_template(xlsx)
    cfg = tmp / "config.yaml"
    cfg.write_text(CONFIG_TPL.format(xlsx=xlsx.as_posix(),
                                     work=(tmp / "runs").as_posix()))

    win = MainWindow(config_path=str(cfg))
    win.resize(1480, 900)
    _pump_until(app,
                lambda: win.state.cfg is not None and win.state.df.shape[0] > 0,
                label="project loaded (df populated)")

    log("starting mock batch...")
    win.start_run()
    # Bounded: wait until the worker thread has fully finished (either the
    # running flag clears or the thread exits), then give the UI a moment to
    # settle before the final dataset reload.
    deadline = time.monotonic() + 240.0
    while time.monotonic() < deadline:
        app.processEvents()
        if win.state.running is False and (win.worker is None
                                           or not win.worker.isRunning()):
            break
        time.sleep(0.01)
    log(f"batch done in {time.monotonic() - deadline + 240.0:.1f}s, "
        f"running={win.state.running}, "
        f"done_rows={int(win.state.df['Status'].eq('DONE').sum()) if len(win.state.df) else 0}")
    if win.worker:
        win.worker.wait(2000)
    app.processEvents()
    _pump_until(app, lambda: win.state.df["Status"].eq("DONE").all(),
                timeout_s=30.0, label="all rows DONE")

    _save(win, "main_dashboard")

    # sidebar close-up
    log("--- capture 3/6: sidebar ---")
    win.sidebar.resize(230, 900)
    _save(win.sidebar, "sidebar")

    # queue close-up
    log("--- capture 4/6: queue ---")
    win.queue.resize(420, 900)
    _save(win.queue, "queue")

    # monitor (populated) — grab the panel itself at a generous size
    log("--- capture 5/6: monitor ---")
    win.monitor.resize(560, 860)
    _save(win.monitor, "monitor")

    # charts page
    log("--- capture 6/8: charts ---")
    win._navigate_to_page("charts")
    win.charts.refresh()
    _pump_until(app, lambda: win.charts.point_count() == 8,
                timeout_s=30.0, label="charts 8 series")
    _save(win, "main_charts")

    # v2.2: close-up queue screenshot
    log("--- capture 7/8: queue v2.2 ---")
    win._navigate_to_page("dashboard")
    _pump_until(app, lambda: True, label="settle")
    _save(win.queue, "queue_v22")

    # v2.2: close-up charts screenshot
    log("--- capture 8/8: charts v2.2 ---")
    win._navigate_to_page("charts")
    win.charts.refresh()
    _pump_until(app, lambda: win.charts.point_count() == 8,
                timeout_s=30.0, label="charts 8 series v2.2")
    _save(win.charts, "charts_v22")

    # v2.2 Stage 3: parameters dock close-up (with a real row loaded)
    log("--- capture 9/12: parameters v2.2 ---")
    win._docks["Parameters"].show()
    win._docks["Parameters"].raise_()
    win.state.select_case(1)
    _pump_until(app, lambda: True, label="settle params")
    win.params.resize(360, 700)
    _save(win.params, "parameters_v22")

    # v2.2 Stage 3: images workspace close-up
    log("--- capture 10/12: images v2.2 ---")
    win._navigate_to_page("images")
    win.images.refresh()
    _pump_until(app, lambda: True, label="settle images")
    win.images.resize(820, 680)
    _save(win.images, "images_v22")

    # v2.2 Stage 3: console dock close-up (populated with a help command)
    log("--- capture 11/12: console v2.2 ---")
    win.console.input.setText("help")
    win.console._run_command()
    win.console.append("batch idle · 8 cases finished")
    win._docks["Console"].show()
    win._docks["Console"].raise_()
    win.resizeDocks([win._docks["Console"]], [300], Qt.Vertical)
    _pump_until(app, lambda: True, label="settle console")
    _save(win.console, "console_v22")

    # v2.2 Stage 3: full workspace — dashboard + queue + monitor + bottom dock
    log("--- capture 12/12: workspace v2.2 ---")
    win._navigate_to_page("dashboard")
    win.dashboard.refresh()
    win._docks["Monitor"].show()
    win._docks["Monitor"].raise_()
    win.resize(1480, 900)
    _pump_until(app, lambda: True, label="settle workspace")
    _save(win, "workspace_v22")

    log("capture complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
