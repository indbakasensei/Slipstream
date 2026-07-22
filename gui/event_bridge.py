"""Engine ↔ Qt bridge.

Two adapters live here, and together they are the *only* place where the
engine's world (threads, logging, EventBus) touches Qt's world (signals on
the UI thread):

* :class:`QtLogHandler` — a ``logging.Handler`` that re-emits every record as
  a queued Qt signal, feeding the Log Console panel with exactly what the
  terminal used to show.
* :class:`EngineWorker` — a ``QThread`` that runs one batch through the
  existing :class:`cfdauto.orchestrator.Orchestrator`, forwarding every
  :class:`cfdauto.events.Event` as a queued signal. Qt's cross-thread signal
  delivery gives us thread-safety for free: ``emit`` happens on the worker
  thread, slots run on the UI thread.

The worker deliberately *reuses the AppState's ExcelManager instance* so the
GUI and the engine never hold two openpyxl copies of the same workbook. While
a batch is running the UI locks all schedule editing (AppState.running).
"""

from __future__ import annotations

import logging
import threading
from typing import Optional, Set

from PySide6.QtCore import QThread, Signal

from cfdauto.config import Config
from cfdauto.error_formatting import format_error
from cfdauto.events import Event, EventBus
from cfdauto.excel_manager import ExcelManager
from cfdauto.exceptions import CFDAutoError
from cfdauto.orchestrator import Orchestrator, build_controllers

log = logging.getLogger("gui.bridge")


class QtLogHandler(logging.Handler):
    """Bridge stdlib logging → Qt signal (one line per record)."""

    def __init__(self, signal) -> None:
        super().__init__(level=logging.INFO)
        self._signal = signal
        self.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        try:
            self._signal.emit(record.levelno, self.format(record))
        except RuntimeError:
            pass  # window closing while a record is in flight


class EngineWorker(QThread):
    """Runs one batch in a background thread and streams events to the UI.

    Signals
    -------
    engineEvent(object)
        Every :class:`cfdauto.events.Event` from the pipeline, delivered on
        the UI thread (Qt queued connection).
    logLine(int, str)
        Formatted log records (level, text) for the console panel.
    batchFinished(int, int, bool)
        (ok, failed, stopped_early) — also emitted on framework errors with
        failed = number of queued cases that never ran.
    fatalError(str)
        A FrameworkError/ConfigError message — the batch did not run.
    studySummaryReady(object)
        Sprint 4 — the engine's ``Orchestrator.current_study_summary``
        (a :class:`cfdauto.study_analytics.StudySummary`, or ``None``),
        read *after* run() returns/raises and re-emitted unchanged — this
        worker never recomputes analytics, only relays the read-only
        property across the thread boundary.
    """

    engineEvent = Signal(object)
    logLine = Signal(int, str)
    batchFinished = Signal(int, int, bool)
    fatalError = Signal(str)
    studySummaryReady = Signal(object)

    def __init__(self, cfg: Config, excel: ExcelManager, *,
                 max_cases: int = 0, retry_failed: bool = False,
                 only_rows: Optional[Set[int]] = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.cfg = cfg
        self.excel = excel
        self.max_cases = max_cases
        self.retry_failed = retry_failed
        self.only_rows = only_rows
        self._stop = threading.Event()
        self._summary = (0, 0, False)          # (ok, failed, stopped)

    # -- controls ------------------------------------------------------- #
    def request_stop(self) -> None:
        """Finish the current case, then stop (graceful — resume-safe)."""
        self._stop.set()

    def stop_requested(self) -> bool:
        return self._stop.is_set()

    # -- thread body ---------------------------------------------------- #
    def run(self) -> None:  # noqa: D102 — QThread entry point
        bus = EventBus()
        bus.subscribe(self._forward)

        handler = QtLogHandler(self.logLine)
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)          # defensive: GUI may run before
        root.addHandler(handler)              # any setup_logging() call
        orch: Optional[Orchestrator] = None
        try:
            wb, fluent = build_controllers(self.cfg, bus=bus)
            orch = Orchestrator(self.cfg, self.excel, wb, fluent, bus=bus)
            orch.run(max_cases=self.max_cases,
                     retry_failed=self.retry_failed,
                     only_rows=self.only_rows,
                     should_stop=self._stop.is_set)
            # Summary captured from the engine's own batch.finished event;
            # this dedicated signal is what re-enables the UI reliably even
            # if an event subscriber misbehaved.
            self.batchFinished.emit(*self._summary)
        except CFDAutoError as exc:
            log.error("Batch aborted: %s", exc)
            self.fatalError.emit(self._safe_render(exc))
            self.batchFinished.emit(0, 0, False)
        except Exception as exc:  # pragma: no cover — surfaced, never swallowed
            log.exception("Unexpected engine error")
            self.fatalError.emit(self._safe_render(exc))
            self.batchFinished.emit(0, 0, False)
        finally:
            # Sprint 4: relay whatever the orchestrator's read-only property
            # holds — None if it never got far enough to populate one (see
            # Orchestrator.current_study_summary's docstring).
            self.studySummaryReady.emit(
                getattr(orch, "current_study_summary", None))
            logging.getLogger().removeHandler(handler)

    def _safe_render(self, exc: BaseException) -> str:
        """format_error() is defensive already; this is a second fallback so
        a formatter bug can never break fatal-error reporting itself."""
        try:
            log_path = self.cfg.work_dir() / "logs" / "cfdauto.log"
            return format_error(exc, log_path=log_path).render_text()
        except Exception:
            return str(exc) or "Unexpected engine error — see log console."

    def _forward(self, evt: Event) -> None:
        if evt.type == "batch.finished":
            d = evt.data
            self._summary = (int(d.get("ok", 0)), int(d.get("failed", 0)),
                             bool(d.get("stopped")))
        self.engineEvent.emit(evt)
