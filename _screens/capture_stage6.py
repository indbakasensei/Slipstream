"""Visual verification capture — Neo v2.2 Stage 6 (Responsive Workspace).

Renders the Stage 6 stress matrix offscreen and saves PNGs for every sample
the spec's Task 6 requires:

    stage6_normal               normal desktop (1480×900)
    stage6_narrow               narrow desktop (1000×700)
    stage6_short                short-height desktop (1400×520)
    stage6_narrow_short         narrow + short (1000×520)
    stage6_queue_parameters     Queue + Parameters dock
    stage6_queue_monitor        Queue + Monitor dock
    stage6_parameters_monitor   Parameters + Monitor
    stage6_all_panels           all utility panels
    stage6_charts_narrow        Charts under constrained width
    stage6_images_narrow        Images under constrained width
    stage6_dashboard_narrow     Dashboard under constrained width
    stage6_focus_narrow         Focus Mode under constrained width

The 12 samples use a default 8-row External Aerodynamics study run to
completion as a **mock batch** (Task 6: "Use realistic mock study data") so
every panel — Queue, Charts, Images, Monitor, Parameters — is populated by
the live path, including real case-dir image artefacts.

Task 7's sample-data variety is captured separately from stage6_samples.py:
    stage6_medium_aero          24-row sweep + WBP:FlapAngle
    stage6_large_queue          64-row sweep (Queue genuinely scrolls)
    stage6_mixed_status         DONE / PENDING / FAILED / SKIP mix
    stage6_internal_flow        Internal Flow template (metadata-driven)

Usage:  python _screens/capture_stage6.py
Output: _screens/stage6_*.png
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
sys.path.insert(0, str(Path(__file__).resolve().parent))   # for stage6_samples

from PySide6.QtGui import QFontDatabase                     # noqa: E402
from PySide6.QtWidgets import QApplication                  # noqa: E402

import stage6_samples                                       # noqa: E402

from gui.main_window import MainWindow                      # noqa: E402
from gui.theme import apply_theme                           # noqa: E402


def _load_offscreen_fonts() -> None:
    """Load system fonts from disk for offscreen rendering (Qt's offscreen QPA
    cannot enumerate fonts; every glyph would render as □ otherwise)."""
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


def log(msg: str) -> None:
    print(f"[stage6] {msg}", file=sys.stderr, flush=True)


def _pump_until(app, pred, timeout_s=90.0, label="wait") -> bool:
    t0 = time.monotonic()
    while not pred():
        app.processEvents()
        time.sleep(0.01)
        if time.monotonic() - t0 > timeout_s:
            log(f"TIMEOUT: {label} — continuing anyway")
            return False
    return True


def _save(win, name: str) -> None:
    pm = win.grab()
    path = OUT / f"{name}.png"
    ok = pm.save(str(path))
    log(f"{'saved' if ok else 'FAILED'}  {name}.png "
        f"({win.width()}x{win.height()})")


def _settle(app, win, times: int = 6) -> None:
    for _ in range(times):
        app.processEvents()
    time.sleep(0.03)
    app.processEvents()


def _window(app, cfg_path: str, size=(1480, 900)):
    win = MainWindow(config_path=cfg_path)
    win.resize(*size)
    win.show()
    _pump_until(app, lambda: win.state.cfg is not None and len(win.state.df) > 0,
                label="project loaded")
    _settle(app, win)
    return win


def _close_docks(win) -> None:
    app = QApplication.instance()
    for d in win._docks.values():
        if d.isVisible():
            d.hide()
    _settle(app, win)


def _hide_bottom_group(win) -> None:
    """Close the bottom Log/Statistics/Console tab group (the Stage 5 default
    is visible; a user on a short screen closes it to free vertical space).
    This is the app's real minimum-height behaviour: with the group closed the
    window can reach ~555px, otherwise it clamps at ~773px. Both states are
    captured so the screenshots show the actual reachable sizes."""
    app = QApplication.instance()
    for n in ("Log", "Statistics", "Console"):
        win._docks[n].hide()
    _settle(app, win)


def _restore_bottom_group(win) -> None:
    app = QApplication.instance()
    for n in ("Log", "Statistics", "Console"):
        win._docks[n].show()
    win._docks["Log"].raise_()
    _settle(app, win)


def _run_mock_batch(app, win) -> None:
    log("running mock batch…")
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
    log("batch complete")


def _capture_t6(app, win) -> None:
    """The twelve required Task 6 samples on the mock-run demo study."""
    # ---- 1 normal desktop ----------------------------------------------- #
    win._navigate_to_page("dashboard")
    win.resize(1480, 900)
    _settle(app, win)
    _save(win, "stage6_normal")

    # ---- 2 narrow desktop ----------------------------------------------- #
    win.resize(1000, 700)
    _settle(app, win)
    _save(win, "stage6_narrow")

    # ---- 3 short-height desktop ----------------------------------------- #
    # The bottom Log group is the app's default-visible chrome and pins the
    # minimum window height to ~773px. A user on a short screen closes it to
    # gain vertical space — that is the honest "short height" state, and with
    # it closed the window reaches ~555px. Qt clamps any request below the
    # usable minimum rather than rendering a broken layout.
    _hide_bottom_group(win)
    win.resize(1400, 520)
    _settle(app, win)
    _save(win, "stage6_short")

    # ---- 4 narrow + short ----------------------------------------------- #
    win.resize(1000, 520)
    _settle(app, win)
    _save(win, "stage6_narrow_short")

    # ---- 5 Queue + Parameters ------------------------------------------- #
    _restore_bottom_group(win)
    win.resize(1480, 900)
    win._docks["Parameters"].show()
    win._docks["Parameters"].raise_()
    _settle(app, win)
    _save(win, "stage6_queue_parameters")

    # ---- 6 Queue + Monitor ---------------------------------------------- #
    win._docks["Parameters"].hide()
    win._docks["Monitor"].show()
    win._docks["Monitor"].raise_()
    _settle(app, win)
    _save(win, "stage6_queue_monitor")

    # ---- 7 Parameters + Monitor ----------------------------------------- #
    win._docks["Parameters"].show()
    _settle(app, win)
    _save(win, "stage6_parameters_monitor")

    # ---- 8 all utility panels ------------------------------------------- #
    win._docks["Console"].show()
    _settle(app, win)
    _save(win, "stage6_all_panels")
    _close_docks(win)
    _restore_bottom_group(win)

    # ---- 9 Charts under constrained width ------------------------------- #
    win._navigate_to_page("charts")
    win.charts.refresh()
    win.resize(1000, 700)
    _settle(app, win)
    _pump_until(app, lambda: win.charts.point_count() > 0,
                timeout_s=30.0, label="charts populated")
    _save(win, "stage6_charts_narrow")

    # ---- 10 Images under constrained width ------------------------------ #
    win._navigate_to_page("images")
    win.images.refresh()
    win.resize(1000, 700)
    _settle(app, win)
    _save(win, "stage6_images_narrow")

    # ---- 11 Dashboard under constrained width --------------------------- #
    win._navigate_to_page("dashboard")
    win.resize(1000, 700)
    _settle(app, win)
    _save(win, "stage6_dashboard_narrow")

    # ---- 12 Focus Mode under constrained width -------------------------- #
    win.resize(1000, 700)
    win.toggle_focus_mode()
    _settle(app, win)
    _save(win, "stage6_focus_narrow")
    win.toggle_focus_mode()
    _settle(app, win)


def _capture_extras(app, tmp) -> None:
    """Task 7 sample-data variety — each config rendered on the dashboard."""
    for name in ("medium-aero", "large-queue", "mixed-status",
                 "internal-flow"):
        cfg = stage6_samples.build(name, tmp)
        win = _window(app, str(cfg))
        win._navigate_to_page("dashboard")
        _settle(app, win)
        _save(win, f"stage6_{name}")
        win.close()


def main() -> int:
    app = QApplication.instance() or QApplication([])
    _load_offscreen_fonts()
    apply_theme(app)

    tmp = Path(tempfile.mkdtemp(prefix="stage6_capture_"))

    # Primary study: default External Aero run to completion as a mock batch.
    demo_cfg = stage6_samples.build("demo", tmp)
    win = _window(app, str(demo_cfg))
    try:
        _run_mock_batch(app, win)
        _capture_t6(app, win)
    finally:
        win.close()

    _capture_extras(app, tmp)

    log("stage6 capture complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
