"""Visual verification capture — Neo v2.2 Stage 5 (Adaptive Workspace).

Renders the adaptive-workspace states offscreen and saves PNGs for every
required sample (Prompt.txt §10):

    stage5_normal / stage5_queue_collapsed / stage5_queue_restored
    stage5_charts_normal / stage5_charts_focus
    stage5_images_normal / stage5_images_focus
    stage5_monitor_dock / stage5_monitor_focus
    stage5_parameters
    stage5_stress_layout / stage5_focus_restore

Runs a full mock batch first so every panel (Queue, Charts, Images, Monitor,
Parameters) is populated with real data, then walks each layout state and
captures it. Uses the same bounded best-effort wait harness as capture.py.

Usage:  python _screens/capture_stage5.py
Output: _screens/stage5_*.png
"""

from __future__ import annotations

import os
import sys
import tempfile
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
    """Load system fonts from disk for offscreen rendering (Qt's offscreen QPA
    cannot enumerate fonts; every glyph would render as □ otherwise)."""
    import glob as _glob
    candidates = {
        "Segoe UI": ["segoeui.ttf"],
        "Arial": ["arial.ttf"],
        "Cascadia Code": ["CascadiaCode.ttf", "CascadiaCode-Regular.ttf"],
    }
    if sys.platform == "win32":
        font_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    elif sys.platform == "darwin":
        font_dir = "/Library/Fonts"
    else:
        font_dir = "/usr/share/fonts"
    for family, names in candidates.items():
        for name in names:
            path = os.path.join(font_dir, name)
            if os.path.isfile(path):
                QFontDatabase.addApplicationFont(path)
                break


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
    print(f"[stage5] {msg}", file=sys.stderr, flush=True)


def _pump_until(app, pred, timeout_s=60.0, label="wait") -> bool:
    t0 = time.monotonic()
    while not pred():
        app.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout_s:
            log(f"TIMEOUT: {label} — continuing anyway")
            return False
    return True


def _save(widget, name: str) -> None:
    pm = widget.grab()
    path = OUT / f"{name}.png"
    ok = pm.save(str(path))
    log(f"{'saved' if ok else 'FAILED'}  {name}.png ({widget.width()}x{widget.height()})")


def _settle(app, win) -> None:
    app.processEvents()
    time.sleep(0.05)
    app.processEvents()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    _load_offscreen_fonts()
    apply_theme(app)

    # -- loaded project + full mock batch --------------------------------- #
    tmp = Path(tempfile.mkdtemp(prefix="stage5_capture_"))
    xlsx = tmp / "experiments.xlsx"
    build_template(xlsx)
    cfg = tmp / "config.yaml"
    cfg.write_text(CONFIG_TPL.format(xlsx=xlsx.as_posix(),
                                     work=(tmp / "runs").as_posix()))

    win = MainWindow(config_path=str(cfg))
    win.resize(1480, 900)
    # Show the window: Focus Mode's state save/restore snapshots widget
    # visibility, which only reports meaningful values for a shown window.
    win.show()
    _pump_until(app, lambda: win.state.cfg is not None and len(win.state.df) > 0,
                label="project loaded")

    log("starting mock batch…")
    win.start_run()
    deadline = time.monotonic() + 240.0
    while time.monotonic() < deadline:
        app.processEvents()
        if win.state.running is False and (win.worker is None
                                           or not win.worker.isRunning()):
            break
        time.sleep(0.01)
    if win.worker:
        win.worker.wait(2000)
    app.processEvents()
    _pump_until(app, lambda: win.state.df["Status"].eq("DONE").all(),
                timeout_s=30.0, label="all rows DONE")
    win.dashboard.refresh()
    win.charts.refresh()
    win.images.refresh()
    _settle(app, win)
    log("batch complete — capturing stage 5 states…")

    # ---- SAMPLE A — NORMAL WORKSPACE (queue visible) -------------------- #
    win._navigate_to_page("dashboard")
    win.resize(1480, 900)
    _settle(app, win)
    _save(win, "stage5_normal")

    # ---- SAMPLE B — QUEUE COLLAPSED ------------------------------------- #
    win.toggle_queue()
    _settle(app, win)
    _save(win, "stage5_queue_collapsed")

    # ---- SAMPLE C — QUEUE RESTORED -------------------------------------- #
    win.toggle_queue()
    _settle(app, win)
    _save(win, "stage5_queue_restored")

    # ---- SAMPLE D — CHARTS NORMAL --------------------------------------- #
    win._navigate_to_page("charts")
    win.charts.refresh()
    _pump_until(app, lambda: win.charts.point_count() == 8,
                timeout_s=30.0, label="charts populated")
    _settle(app, win)
    _save(win, "stage5_charts_normal")

    # ---- SAMPLE E — CHARTS FOCUS ---------------------------------------- #
    win.toggle_focus_mode()
    _settle(app, win)
    _save(win, "stage5_charts_focus")
    win.toggle_focus_mode()
    _settle(app, win)

    # ---- SAMPLE F — IMAGES NORMAL --------------------------------------- #
    win._navigate_to_page("images")
    win.images.refresh()
    _settle(app, win)
    _save(win, "stage5_images_normal")

    # ---- SAMPLE G — IMAGES FOCUS ---------------------------------------- #
    win.toggle_focus_mode()
    _settle(app, win)
    _save(win, "stage5_images_focus")
    win.toggle_focus_mode()
    _settle(app, win)

    # ---- SAMPLE H — MONITOR WITH DOCK ----------------------------------- #
    win._navigate_to_page("dashboard")
    win._docks["Monitor"].show()
    win._docks["Monitor"].raise_()
    win.resize(1480, 900)
    _settle(app, win)
    _save(win, "stage5_monitor_dock")

    # ---- SAMPLE I — MONITOR FOCUS --------------------------------------- #
    win.toggle_focus_mode()
    _settle(app, win)
    _save(win, "stage5_monitor_focus")
    win.toggle_focus_mode()
    _settle(app, win)

    # ---- SAMPLE J — PARAMETERS + MAIN WORKSPACE -------------------------- #
    win._docks["Monitor"].hide()
    win._docks["Parameters"].show()
    win._docks["Parameters"].raise_()
    win.state.select_case(1)
    _settle(app, win)
    _save(win, "stage5_parameters")

    # ---- SAMPLE K — MULTIPLE SECONDARY PANELS (stress) ------------------- #
    win._docks["Parameters"].show()
    win._docks["Monitor"].show()
    win._docks["Console"].show()
    win.resize(1480, 900)
    _settle(app, win)
    _save(win, "stage5_stress_layout")

    # ---- SAMPLE L — FOCUS FROM STRESS STATE ------------------------------ #
    win.toggle_focus_mode()
    _settle(app, win)
    _save(win, "stage5_focus_restore")
    win.toggle_focus_mode()
    _settle(app, win)
    log("post-focus-exit dock visibility: "
        f"{ {n: d.isVisible() for n, d in win._docks.items()} }")

    log("stage5 capture complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
