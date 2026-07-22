"""Slipstream main window — layout, wiring, and engine-worker ownership.

Layout (VS/Workbench-style)::

    ┌ toolbar ───────────────────────────────────────────────────────────┐
    │ ⚠ MOCK MODE banner (visible only when mock mode is active) ⚠       │
    ├──────────┬─────────────────────────────────────────┬───────────────┤
    │ Explorer │  Central tabs: Dashboard · Results · Charts · Images    │
    │ (dock L) │                                        │ Queue   (dock) │
    │          │                                        │ Params  (tab)  │
    │          │                                        │ Monitor (dock) │
    ├──────────┴───────────── Log · Statistics (tabbed bottom dock) ─────┤
    └ status bar ────────────────────────────────────────────────────────┘

Every panel renders from :class:`gui.state.AppState`; this class only routes
signals and owns the one :class:`gui.event_bridge.EngineWorker` at a time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QLabel, QMainWindow,
                               QMessageBox, QTabWidget, QVBoxLayout, QWidget)

import cfdauto
from cfdauto.error_formatting import format_error
from cfdauto.events import Event
from cfdauto.exceptions import CFDAutoError
from gui.event_bridge import EngineWorker
from gui.panels.charts_panel import ChartsPanel
from gui.panels.dashboard import DashboardPanel
from gui.panels.explorer import ExplorerPanel
from gui.panels.images_panel import ImagesPanel
from gui.panels.log_console import LogConsolePanel
from gui.panels.monitor import MonitorPanel
from gui.panels.params_panel import ParamsPanel
from gui.panels.queue_panel import QueuePanel
from gui.panels.results_table import ResultsTablePanel
from gui.panels.stats_panel import StatsPanel
from gui.state import AppState

log = logging.getLogger("gui.main")

BASE_TITLE = f"Slipstream — CFD Study Manager  v{cfdauto.__version__}"


class MainWindow(QMainWindow):
    def __init__(self, config_path: Optional[str] = None):
        super().__init__()
        self.setWindowTitle(BASE_TITLE)
        self.resize(1480, 900)
        self.setDockNestingEnabled(True)

        self.state = AppState()
        self.worker: Optional[EngineWorker] = None

        # -- panels -------------------------------------------------------#
        self.dashboard = DashboardPanel(self.state)
        self.results = ResultsTablePanel(self.state)
        self.charts = ChartsPanel(self.state)
        self.images = ImagesPanel(self.state)
        self.queue = QueuePanel(self.state)
        self.params = ParamsPanel(self.state)
        self.monitor = MonitorPanel()
        self.log_panel = LogConsolePanel()
        self.stats = StatsPanel(self.state)
        self.explorer = ExplorerPanel(self.state)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.results, "Results")
        self.tabs.addTab(self.charts, "Charts")
        self.tabs.addTab(self.images, "Images")

        # Wrap the tab widget with a mock-mode banner above it. The banner is
        # hidden by default and appears whenever mock is engaged.
        self.mock_banner = QLabel(
            "⚠  MOCK MODE — no ANSYS software will run · results are "
            "fabricated for pipeline testing only  ⚠")
        self.mock_banner.setAlignment(Qt.AlignCenter)
        self.mock_banner.setStyleSheet(
            "QLabel { background: #e8a33d; color: #1e1f22; "
            "font-weight: 700; font-size: 12px; padding: 6px 8px; "
            "border-bottom: 1px solid #b0771e; }")
        self.mock_banner.hide()

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.mock_banner)
        v.addWidget(self.tabs)
        self.setCentralWidget(central)

        self._docks = {}
        self._make_docks()
        self._make_menus_toolbar()
        self._make_statusbar()
        self._wire()

        if config_path and Path(config_path).exists():
            self._load(config_path)

    # ------------------------------------------------------------------ #
    # Docks / menus / status bar
    # ------------------------------------------------------------------ #
    def _dock(self, title: str, widget, area, tab_with: str | None = None):
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(widget)
        self.addDockWidget(area, d)
        if tab_with:
            self.tabifyDockWidget(self._docks[tab_with], d)
        self._docks[title] = d
        return d

    def _make_docks(self) -> None:
        self._dock("Explorer", self.explorer, Qt.LeftDockWidgetArea)
        q = self._dock("Queue", self.queue, Qt.RightDockWidgetArea)
        self._dock("Parameters", self.params, Qt.RightDockWidgetArea,
                   tab_with="Queue")
        q.raise_()
        self._dock("Monitor", self.monitor, Qt.RightDockWidgetArea)
        self.splitDockWidget(q, self._docks["Monitor"], Qt.Vertical)
        lg = self._dock("Log", self.log_panel, Qt.BottomDockWidgetArea)
        self._dock("Statistics", self.stats, Qt.BottomDockWidgetArea,
                   tab_with="Log")
        lg.raise_()
        self.resizeDocks([self._docks["Explorer"]], [250], Qt.Horizontal)
        self.resizeDocks([q, self._docks["Monitor"]], [430, 430], Qt.Horizontal)
        self.resizeDocks([lg], [190], Qt.Vertical)
        self._default_layout = self.saveState()

    def _make_menus_toolbar(self) -> None:
        # File
        m_file = self.menuBar().addMenu("&File")
        self.act_open = QAction("Open Project…", self,
                                shortcut=QKeySequence.Open,
                                triggered=self._open_dialog)
        self.act_reload = QAction("Reload Project", self, shortcut="Ctrl+R",
                                  triggered=self._reload)
        m_file.addActions([self.act_open, self.act_reload])
        m_file.addSeparator()
        m_file.addAction(QAction("Exit", self, shortcut="Ctrl+Q",
                                 triggered=self.close))
        # Run
        m_run = self.menuBar().addMenu("&Run")
        self.act_run = QAction("Run All", self, shortcut="F5",
                               triggered=lambda: self.start_run())
        self.act_stop = QAction("Stop after current case", self,
                                shortcut="Shift+F5", enabled=False,
                                triggered=self._stop)
        self.act_mock = QAction("Mock mode (no ANSYS)", self, checkable=True)
        self.act_mock.toggled.connect(self._on_mock_toggled)
        m_run.addActions([self.act_run, self.act_stop])
        m_run.addSeparator()
        m_run.addAction(self.act_mock)
        # View
        m_view = self.menuBar().addMenu("&View")
        for name, dock in self._docks.items():
            m_view.addAction(dock.toggleViewAction())
        m_view.addSeparator()
        m_view.addAction(QAction("Reset layout", self,
                                 triggered=lambda: self.restoreState(
                                     self._default_layout)))
        # Help
        m_help = self.menuBar().addMenu("&Help")
        m_help.addAction(QAction("About Slipstream", self,
                                 triggered=self._about))

        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.addActions([self.act_open, self.act_reload])
        tb.addSeparator()
        tb.addActions([self.act_run, self.act_stop])
        tb.addSeparator()
        tb.addAction(self.act_mock)
        self._toolbar = tb

    def _make_statusbar(self) -> None:
        self.sb_engine = QLabel("engine: idle")
        self.sb_engine.setStyleSheet("padding: 2px 8px;")
        self.sb_queue = QLabel("")
        self.statusBar().addWidget(self.sb_engine)
        self.statusBar().addWidget(QLabel("  ·  "))
        self.statusBar().addWidget(self.sb_queue)
        self.statusBar().addPermanentWidget(
            QLabel(f"Slipstream v{cfdauto.__version__}"))

    # ------------------------------------------------------------------ #
    # Wiring
    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        st = self.state
        self.queue.runRequested.connect(self.start_run)
        self.queue.stopRequested.connect(self._stop)
        self.dashboard.runAllRequested.connect(lambda: self.start_run())
        self.dashboard.openProjectRequested.connect(self._open_dialog)
        self.explorer.imageActivated.connect(self._open_image)
        st.datasetChanged.connect(self._update_queue_label)
        st.runStateChanged.connect(self._run_state_changed)
        st.projectLoaded.connect(self._sync_mock_ui)

    # ------------------------------------------------------------------ #
    # Mock-mode UI sync (toolbar highlight + banner + window title)
    # ------------------------------------------------------------------ #
    def _on_mock_toggled(self, checked: bool) -> None:
        """Fired when the user clicks the Mock toolbar/menu action."""
        self.state.mock_override = checked
        self._sync_mock_ui()

    def _sync_mock_ui(self) -> None:
        """Reflect the effective mock state everywhere the user might look:
        toolbar button (highlighted orange), workspace banner, window title."""
        is_mock = self.state.effective_mock
        self.act_mock.blockSignals(True)
        self.act_mock.setChecked(is_mock)
        self.act_mock.blockSignals(False)
        # Style the toolbar button widget directly.
        try:
            btn = self._toolbar.widgetForAction(self.act_mock)
            if btn is not None:
                if is_mock:
                    btn.setStyleSheet(
                        "background: #e8a33d; color: #1e1f22; "
                        "font-weight: 700; border-radius: 4px; "
                        "padding: 4px 10px;")
                else:
                    btn.setStyleSheet("")
        except Exception:
            pass
        # Persistent banner across the top of the workspace.
        self.mock_banner.setVisible(is_mock)
        # Window title also carries the badge (visible in taskbar / Alt+Tab).
        self.setWindowTitle(BASE_TITLE + ("   [MOCK MODE]" if is_mock else ""))

    @staticmethod
    def _safe_render(exc: BaseException) -> str:
        """format_error() is defensive already; this is a second fallback so
        a formatter bug can never break the "could not load project" dialog
        itself."""
        try:
            return format_error(exc).render_text()
        except Exception:
            return f"{type(exc).__name__}: {exc}"

    # ------------------------------------------------------------------ #
    # Project lifecycle
    # ------------------------------------------------------------------ #
    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Slipstream project config", "",
            "Config (*.yaml *.yml)")
        if path:
            self._load(path)

    def _load(self, path: str) -> None:
        try:
            self.state.load_project(path)
            # Reset any UI-only override so the freshly loaded config wins.
            self.state.mock_override = None
            self._sync_mock_ui()
            self.statusBar().showMessage(f"Project loaded: {path}", 5000)
        except CFDAutoError as exc:
            QMessageBox.critical(self, "Could not load project",
                                 self._safe_render(exc))
        except Exception as exc:                       # bad yaml etc.
            QMessageBox.critical(self, "Could not load project",
                                 self._safe_render(exc))

    def _reload(self) -> None:
        if self.state.config_path:
            self._load(str(self.state.config_path))

    # ------------------------------------------------------------------ #
    # Run control
    # ------------------------------------------------------------------ #
    def start_run(self, only_rows: Optional[Set[int]] = None,
                  retry_failed: bool = False, max_cases: int = 0) -> None:
        if self.state.running:
            return
        if not self.state.cfg:
            self._open_dialog()
            if not self.state.cfg:
                return
        self.state.cfg.runtime.mock = self.state.effective_mock
        self.worker = EngineWorker(self.state.cfg, self.state.excel,
                                   max_cases=max_cases,
                                   retry_failed=retry_failed,
                                   only_rows=only_rows, parent=self)
        self.worker.engineEvent.connect(self._on_event)
        self.worker.logLine.connect(self.log_panel.append)
        self.worker.batchFinished.connect(self._on_finished)
        self.worker.fatalError.connect(
            lambda msg: QMessageBox.critical(self, "Batch aborted", msg))
        self.worker.studySummaryReady.connect(self.dashboard.set_study_summary)
        self.state.set_running(True)
        self.sb_engine.setText(
            "engine: running" + ("  (MOCK)" if self.state.cfg.runtime.mock else ""))
        self.worker.start()

    def _stop(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self.sb_engine.setText("engine: stopping after current case…")

    def _on_event(self, evt: Event) -> None:
        self.state.apply_event(evt)
        self.monitor.handle_event(evt)
        self.dashboard.handle_event(evt)
        if evt.type == "case.started":
            d = evt.data
            self.sb_engine.setText(
                f'engine: case {d["index"]}/{d["total"]} — {d["case_id"]}')

    def _on_finished(self, ok: int, failed: int, stopped: bool) -> None:
        self.state.set_running(False)
        self.sb_engine.setText("engine: idle")
        if self.worker:
            self.worker.wait(2000)
            self.worker.deleteLater()
            self.worker = None
        # Ground truth back from the workbook now that the engine is idle.
        try:
            self.state.reload_dataset()
        except Exception:
            log.exception("Dataset reload after batch failed")
        note = " (stopped early — re-run to resume)" if stopped else ""
        self.statusBar().showMessage(
            f"Batch finished: {ok} ok, {failed} failed{note}", 8000)

    # ------------------------------------------------------------------ #
    def _run_state_changed(self, running: bool) -> None:
        self.act_run.setEnabled(not running)
        self.act_open.setEnabled(not running)
        self.act_reload.setEnabled(not running)
        self.act_mock.setEnabled(not running)
        self.act_stop.setEnabled(running)

    def _update_queue_label(self) -> None:
        df = self.state.df
        if not len(df):
            self.sb_queue.setText("no schedule loaded")
            return
        c = df["Status"].value_counts()
        self.sb_queue.setText(
            f'queue: {int(c.get("PENDING", 0))} pending · '
            f'{int(c.get("DONE", 0))} done · {int(c.get("FAILED", 0))} failed')

    def _open_image(self, path) -> None:
        self.tabs.setCurrentWidget(self.images)
        self.images.show_file(Path(path))

    def _about(self) -> None:
        QMessageBox.about(
            self, "About Slipstream",
            f"<b>Slipstream v{cfdauto.__version__}</b><br>"
            "Local-first CFD study manager for ANSYS Workbench + Fluent.<br>"
            "Engine: cfdauto · GUI: PySide6 + pyqtgraph.<br>"
            "Free · open source · no telemetry.")

    # ------------------------------------------------------------------ #
    def closeEvent(self, e) -> None:
        if self.state.running:
            r = QMessageBox.question(
                self, "Batch running",
                "A batch is running. Stop after the current case and exit?\n"
                "(Progress is resume-safe — re-running continues where it "
                "left off.)")
            if r != QMessageBox.Yes:
                e.ignore()
                return
            self._stop()
            if self.worker:
                self.worker.wait(15000)
        e.accept()
