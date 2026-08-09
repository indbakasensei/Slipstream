"""Slipstream main window — layout, wiring, and engine-worker ownership.

GUI Modernization (v1.0.0-rc2) layout::

    ┌ menu bar ────────────────────────────────────────────────────────────┐
    │ toolbar: Open Project · Reload · Run All · Stop · Mock mode          │
    ├──────────┬─────────────────────────────────────────┬─────────────────┤
    │          │  ⚠ MOCK MODE banner (only when active) ⚠                 │
    │  Brand   │  WorkspaceHeader (page · project ·      │                 │
    │  header  │   template · schedule)                  │                 │
    │ Sidebar  ├─────────────────────────────────────────┤                 │
    │ (nav +   │  Center workspace (QStackedWidget:       │ Queue           │
    │  project │   Dashboard / Results / Charts / Images) │ (persistent —   │
    │  tree)   │   — or the EmptyState page when no       │  not a dock)    │
    │          │     project is loaded                    │                 │
    ├──────────┴──────────────────────────────────────────┴─────────────────┤
    │ Log · Statistics · Console (tabbed bottom dock)                       │
    └ status bar: engine · queue · project · template · python · mode · ver ┘

Monitor and Parameters remain QDockWidgets, hidden by default and reachable
from the View menu — they no longer permanently compete with Queue for
screen space.

Every panel renders from :class:`gui.state.AppState`; this class only
routes signals/navigation and owns the one :class:`gui.event_bridge.EngineWorker`
at a time. ``self.tabs`` is kept as the attribute name for the center
workspace switcher (now a ``QStackedWidget``, not a ``QTabWidget``) so
existing code/tests that call ``self.tabs.count()`` / ``.setCurrentWidget()``
keep working unchanged — both methods exist on either widget type.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Set

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QDialog, QDockWidget, QFileDialog, QLabel,
                               QMainWindow, QMessageBox, QSplitter,
                               QStackedWidget, QVBoxLayout, QWidget)

import cfdauto
from cfdauto.error_formatting import format_error
from cfdauto.events import Event
from cfdauto.exceptions import CFDAutoError
from gui import theme
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
from gui.widgets import EmptyState, Sidebar, WorkspaceHeader, make_icon
from gui.widgets.sidebar import WORKSPACE_PAGES

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
        self.monitor = MonitorPanel(self.state.context)
        self.log_panel = LogConsolePanel()
        self.stats = StatsPanel(self.state)
        self.explorer = ExplorerPanel(self.state)

        self._docks: Dict[str, QDockWidget] = {}
        self._make_central()
        self._make_docks()
        self._make_menus_toolbar()
        self._make_statusbar()
        self._wire()

        self._refresh_workspace_chrome()

        if config_path and Path(config_path).exists():
            self._load(config_path)
        elif not self.state.cfg:
            # Friendlier first-run experience than a silent empty dashboard
            # — invite the user straight into the existing Project Selector
            # once the window has actually appeared (QTimer.singleShot(0, …)
            # defers this past .show(), rather than popping a modal dialog
            # in front of an invisible parent).
            QTimer.singleShot(0, self._open_project_selector)

    # ------------------------------------------------------------------ #
    # Central workspace: Sidebar | QStackedWidget | Queue (QSplitter)
    # ------------------------------------------------------------------ #
    def _make_central(self) -> None:
        # Center workspace pages — kept as ``self.tabs`` (a QStackedWidget)
        # purely for backward compatibility: .count()/.setCurrentWidget()
        # exist on both QTabWidget and QStackedWidget, so no caller/test
        # needs to know the widget type changed.
        self.tabs = QStackedWidget()
        self._nav_pages = {
            "dashboard": self.dashboard,
            "results": self.results,
            "charts": self.charts,
            "images": self.images,
        }
        for page in self._nav_pages.values():
            self.tabs.addWidget(page)

        # Neo (v2.1): workspace chrome above the page stack — page title +
        # project/template/schedule context line.
        self.workspace_header = WorkspaceHeader()
        center_content = QWidget()
        cv = QVBoxLayout(center_content)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        cv.addWidget(self.workspace_header)
        cv.addWidget(self.tabs, 1)

        # Empty-state page for the startup / no-project case ("No Project
        # Loaded — Open or Create a Project"). Purely presentational.
        self.empty_state = EmptyState(
            "No Project Loaded",
            "Open or create a Slipstream project to start your CFD study.",
            action_text="Open Project…")
        self.empty_state.actionClicked.connect(self._open_dialog)

        self._center_stack = QStackedWidget()
        self._center_stack.addWidget(self.empty_state)     # index 0
        self._center_stack.addWidget(center_content)       # index 1

        self.sidebar = Sidebar(self.explorer)
        self.sidebar.pageRequested.connect(self._navigate_to_page)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self._center_stack)
        self.splitter.addWidget(self.queue)
        # Sidebar and Queue hold their width; the center workspace absorbs
        # whatever space resizing adds or removes (stretch factors, not
        # fixed geometry — scales cleanly at 1080p/1440p/4K).
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        # Capability 3 responsive foundation: minimum widths (from the shared
        # design tokens) so no region collapses into an unreadable sliver when
        # the window is shrunk. The splitter still lets the user resize freely
        # above these floors; children never clip below them.
        self.sidebar.setMinimumWidth(theme.MIN_SIDEBAR_WIDTH)
        self.tabs.setMinimumWidth(theme.MIN_CENTER_WIDTH)
        self._center_stack.setMinimumWidth(theme.MIN_CENTER_WIDTH)
        self.queue.setMinimumWidth(theme.MIN_QUEUE_WIDTH)
        self.splitter.setChildrenCollapsible(False)
        # Initial proportions only (~230px sidebar, ~30% queue) — the user
        # can resize freely afterward; nothing here is a hard constraint.
        total = max(self.width(), 1480)
        queue_w = int(total * 0.30)
        self.splitter.setSizes([230, max(200, total - 230 - queue_w), queue_w])

        # Mock-mode banner sits above the splitter, spanning full width.
        # Presentation-only: styled from theme tokens (WARNING surface) via
        # the mockBanner QSS role instead of a hardcoded inline stylesheet.
        self.mock_banner = QLabel(
            "⚠  MOCK MODE — no ANSYS software will run · results are "
            "fabricated for pipeline testing only  ⚠")
        self.mock_banner.setAlignment(Qt.AlignCenter)
        self.mock_banner.setProperty("mockBanner", True)
        self.mock_banner.setAttribute(Qt.WA_StyledBackground, True)
        self.mock_banner.hide()

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.mock_banner)
        v.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

    def _navigate_to_page(self, page_id: str) -> None:
        page = self._nav_pages.get(page_id)
        if page is not None:
            self.tabs.setCurrentWidget(page)
        label = dict((p[0], p[1]) for p in WORKSPACE_PAGES).get(page_id, page_id)
        self.workspace_header.set_page(page_id, label)

    def _refresh_workspace_chrome(self) -> None:
        """Presentation-only: show the empty state vs. the workspace, keep the
        WorkspaceHeader context (project · template · schedule) and the status
        bar project/template/mode readouts in sync with the loaded state."""
        st = self.state
        has_project = st.cfg is not None
        self._center_stack.setCurrentIndex(1 if has_project else 0)
        if has_project:
            project = st.config_path.stem if st.config_path else ""
            template = ""
            schedule = ""
            try:
                tpl = getattr(st.context, "template", None)
                template = getattr(tpl, "name", "") if tpl is not None else ""
            except Exception:
                template = ""
            try:
                if st.cfg:
                    schedule = str(st.cfg.excel.file)
            except Exception:
                schedule = ""
            self.workspace_header.set_context(project, template, schedule)
            pid = self.sidebar.current_page() or "dashboard"
            label = dict((p[0], p[1]) for p in WORKSPACE_PAGES).get(pid, pid)
            self.workspace_header.set_page(pid, label)
        self._update_status_context()

    def _update_status_context(self) -> None:
        """Status-bar right-side readouts: project · template · python · mode."""
        st = self.state
        project = st.config_path.stem if st.config_path else "—"
        template = ""
        try:
            tpl = getattr(st.context, "template", None)
            template = getattr(tpl, "name", "") if tpl is not None else ""
        except Exception:
            template = ""
        self.sb_project.setText(f"Project: {project}")
        self.sb_template.setText(f"Template: {template}" if template
                                 else "Template: —")
        mode = "MOCK" if st.effective_mock else "LIVE"
        colour = theme.WARNING_TEXT if mode == "MOCK" else theme.SUCCESS_TEXT
        self.sb_mode.setText(mode)
        self.sb_mode.setStyleSheet(
            f"color: {colour}; background: rgba(0,0,0,0); "
            f"font-weight: 700; letter-spacing: 0.5px; padding: 2px 8px;")

    # ------------------------------------------------------------------ #
    # Docks: Monitor + Parameters (hidden by default) and the bottom
    # Log/Statistics/Console tab group (visible by default, as before).
    # ------------------------------------------------------------------ #
    def _dock(self, title: str, widget, area, tab_with: str | None = None,
             start_hidden: bool = False):
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(widget)
        self.addDockWidget(area, d)
        if tab_with:
            self.tabifyDockWidget(self._docks[tab_with], d)
        if start_hidden:
            d.setVisible(False)
        self._docks[title] = d
        return d

    def _make_docks(self) -> None:
        self._dock("Monitor", self.monitor, Qt.RightDockWidgetArea,
                  start_hidden=True)
        self._dock("Parameters", self.params, Qt.RightDockWidgetArea,
                  tab_with="Monitor", start_hidden=True)

        lg = self._dock("Log", self.log_panel, Qt.BottomDockWidgetArea)
        self._dock("Statistics", self.stats, Qt.BottomDockWidgetArea,
                  tab_with="Log")
        console_placeholder = QLabel(
            "Console — coming soon.\n\n"
            "A future release may add an embedded command console here.")
        console_placeholder.setAlignment(Qt.AlignCenter)
        console_placeholder.setProperty("hint", True)
        self._dock("Console", console_placeholder, Qt.BottomDockWidgetArea,
                  tab_with="Log")
        lg.raise_()

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
        self.act_projects = QAction("Projects…", self, shortcut="Ctrl+Shift+O",
                                    triggered=self._open_project_selector)
        m_file.addActions([self.act_open, self.act_reload, self.act_projects])
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

        # Toolbar: only the five primary actions — everything else lives
        # in menus (no duplicated Run buttons, no toolbar clutter). Neo
        # (v2.1): painted vector icons + a caption that groups the run
        # controls into one engineering cluster.
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(theme.TOOLBAR_ICON_SIZE, theme.TOOLBAR_ICON_SIZE))

        self.act_open.setIcon(make_icon("open", theme.TEXT))
        self.act_reload.setIcon(make_icon("reload", theme.TEXT))
        self.act_run.setIcon(make_icon("run", theme.ACCENT_TEXT))
        self.act_stop.setIcon(make_icon("stop", theme.WARNING))
        self.act_mock.setIcon(make_icon("mock", theme.TEXT))

        tb.addActions([self.act_open, self.act_reload])
        tb.addSeparator()
        sim_cap = QLabel("SIMULATION")
        sim_cap.setProperty("toolbarGroup", True)
        tb.addWidget(sim_cap)
        tb.addActions([self.act_run, self.act_stop])
        tb.addSeparator()
        tb.addAction(self.act_mock)
        self._toolbar = tb

        # Run = primary (accent fill), Stop = caution (warning tint). The
        # mock action keeps its own inline styling in _sync_mock_ui().
        run_btn = tb.widgetForAction(self.act_run)
        if run_btn is not None:
            run_btn.setProperty("toolbarAccent", True)
            run_btn.style().unpolish(run_btn)
            run_btn.style().polish(run_btn)
        stop_btn = tb.widgetForAction(self.act_stop)
        if stop_btn is not None:
            stop_btn.setProperty("toolbarWarning", True)
            stop_btn.style().unpolish(stop_btn)
            stop_btn.style().polish(stop_btn)

    def _make_statusbar(self) -> None:
        def _sep() -> QLabel:
            s = QLabel("·")
            s.setProperty("statusSep", True)
            return s

        sb = self.statusBar()
        # Left: live engine + queue readouts (names/text semantics preserved).
        self.sb_engine = QLabel("engine: idle")
        self.sb_engine.setProperty("statusInfo", True)
        self.sb_queue = QLabel("")
        self.sb_queue.setProperty("statusInfo", True)
        sb.addWidget(self.sb_engine)
        sb.addWidget(_sep())
        sb.addWidget(self.sb_queue)
        # Right: engineering context — project · template · python · mode · ver.
        self.sb_project = QLabel("Project: —")
        self.sb_project.setProperty("statusInfo", True)
        self.sb_template = QLabel("Template: —")
        self.sb_template.setProperty("statusInfo", True)
        self.sb_python = QLabel(
            f"Py {sys.version_info.major}.{sys.version_info.minor}")
        self.sb_python.setProperty("statusInfo", True)
        self.sb_mode = QLabel("LIVE")
        self.sb_mode.setProperty("statusInfo", True)
        self.sb_version = QLabel(f"Slipstream v{cfdauto.__version__}")
        self.sb_version.setProperty("statusInfo", True)
        for w in (self.sb_project, self.sb_template, self.sb_python,
                  self.sb_mode, self.sb_version):
            sb.addPermanentWidget(_sep())
            sb.addPermanentWidget(w)

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
                        f"background: {theme.WARNING_TEXT}; "
                        f"color: {theme.BG_PANEL}; "
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
        # Status-bar MOCK/LIVE chip follows the same effective state.
        self._update_status_context()

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
            self._refresh_workspace_chrome()
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

    def _open_project_selector(self) -> None:
        """Open Recent / Open Existing / Create New. Purely a front door to
        the existing config.yaml flow — a selected/created project hands
        off to the unchanged self._load(); nothing about how a study runs
        is touched here."""
        from gui.project_selector_dialog import ProjectSelectorDialog
        dlg = ProjectSelectorDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_project_root:
            root = dlg.selected_project_root
            cfg_path = root / "config" / "config.yaml"
            if cfg_path.exists():
                self._load(str(cfg_path))
            else:
                QMessageBox.information(
                    self, "Project created",
                    f"Project '{root.name}' was created successfully but "
                    f"still requires a config.yaml before it can be "
                    f"opened.\n\nAdd one at:\n{cfg_path}")

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
        self._navigate_to_page("images")
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
