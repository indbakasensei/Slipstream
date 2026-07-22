"""Orchestrator: the pipeline loop.

For every unfinished row of the Excel schedule::

    mark RUNNING → [geometry mode: cached mesh?  else Workbench update+mesh]
                 → Fluent solve → result.json → Excel row (DONE/FAILED) → next

Design points worth calling out
-------------------------------
* **Excel is the ledger.** The Status column is what makes the run resumable:
  kill the process at any moment, run the same command again, and only the
  unfinished rows execute. Rows left ``RUNNING`` by a crash are re-queued.
* **result.json is the authority.** Every case writes its result to its own
  artifact folder *before* touching the workbook, so even a permanently
  locked Excel file loses nothing.
* **Failures are per-case.** A diverged solve or a meshing failure marks that
  row FAILED (with the reason in the Error column) and the batch continues —
  exactly what you want when leaving 200 cases running overnight. Framework
  errors (bad config, missing project) abort immediately instead.
* **Mesh caching.** Rows sharing a geometry (same AOA + same extra WB
  parameters) reuse one mesh; Workbench runs once per geometry, not once per
  row. Velocity-only sweeps therefore skip Workbench entirely after the
  first case.
"""

from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import List, Optional, Protocol

from .config import Config
from .error_formatting import format_error
from .events import EventBus
from .excel_manager import ExcelManager
from .exceptions import CaseError, ExcelWriteError, FrameworkError
from .ledger import Ledger
from .logging_setup import add_case_file_handler, remove_handler
from .models import (
    STATUS_DONE,
    STATUS_FAILED,
    CaseResult,
    Experiment,
)
from .state import RunState
from .study_analytics import StudySummary, analyze_study

log = logging.getLogger("cfdauto.orchestrator")


# --------------------------------------------------------------------------- #
# Controller contracts (structural typing — mocks and real classes both fit)
# --------------------------------------------------------------------------- #
class MeshBackend(Protocol):
    def prepare_mesh(self, exp: Experiment, case_dir: Path) -> Path: ...


class SolverBackend(Protocol):
    def run_case(self, exp: Experiment, mesh_file: Optional[Path],
                 case_dir: Path) -> CaseResult: ...


def build_controllers(cfg: Config, bus: Optional[EventBus] = None
                      ) -> tuple[MeshBackend, SolverBackend]:
    """Factory: real ANSYS controllers, or mocks for --mock / CI."""
    if cfg.runtime.mock:
        from .mocks import MockFluentController, MockWorkbenchController
        log.warning("MOCK MODE — no ANSYS software will be launched; results "
                    "are fabricated for pipeline testing only.")
        return MockWorkbenchController(cfg, bus=bus), MockFluentController(cfg, bus=bus)
    from .fluent_controller import FluentController
    from .workbench_controller import WorkbenchController
    wb = (WorkbenchController(cfg, bus=bus)
          if cfg.fluent.aoa_method == "geometry" else None)
    return wb, FluentController(cfg, bus=bus)  # wb unused in velocity_vector mode


class Orchestrator:
    def __init__(self, cfg: Config, excel: ExcelManager,
                 wb: Optional[MeshBackend], fluent: SolverBackend,
                 bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.excel = excel
        self.wb = wb
        self.fluent = fluent
        self.bus = bus or EventBus()
        self.state = RunState(cfg.work_dir())

        # v0.9-M3: SQLite ledger — dual-write beside Excel for provenance and
        # per-iteration telemetry storage. Never fatal — Excel remains the
        # source of truth if this fails.
        self.ledger: Optional[Ledger] = None
        self._batch_id: Optional[int] = None
        self._current_case_pk: Optional[int] = None

        # Sprint 3: Study Analytics.
        #
        # ``_retries_used`` counts retry attempts across the *current*
        # run() call only — reset to 0 at the start of every run() so a
        # count can never leak from one study into the next.
        #
        # ``_current_study_summary`` always reflects the most recently
        # *completed call* to run(): reset to None at the start of every
        # run(), then populated at every non-raising return point (full
        # completion, an early "Stop after current case", the
        # license-lockout cascade halt, or the trivial "nothing to do"
        # case) — in the early-stop cases this is a deliberately *partial*
        # summary, with StudyWarning entries flagging rows that never
        # finished. It is left as None only if run() raises before
        # reaching its own bookkeeping (e.g. a FrameworkError abort from
        # bad config/environment) — in that scenario the raised exception
        # itself is the caller's signal that no analytics are available.
        self._retries_used: int = 0
        self._current_study_summary: Optional[StudySummary] = None
        try:
            self.ledger = Ledger(cfg.work_dir() / "slipstream.db")
            # Route fluent.iteration events into the DB in real time.
            self.bus.subscribe(self._on_bus_event)
        except Exception as exc:
            log.warning("SQLite ledger disabled (%s) — Excel-only mode.", exc)
            self.ledger = None

    def _on_bus_event(self, evt) -> None:
        """Persist per-iteration telemetry into the DB as it streams from
        the tap. Silent on failure; the plot still works either way."""
        if (self.ledger is None or self._current_case_pk is None
                or evt.type != "fluent.iteration"):
            return
        d = evt.data
        try:
            self.ledger.record_iteration(
                self._current_case_pk,
                int(d["it"]), float(d["cl"]), float(d["cd"]),
                d.get("residuals"))
        except Exception:
            log.debug("record_iteration failed — non-fatal", exc_info=True)

    # ------------------------------------------------------------------ #
    def run(self, max_cases: int = 0, retry_failed: bool = False,
            only_rows: Optional[set[int]] = None,
            should_stop: Optional[callable] = None) -> int:
        """Execute all pending experiments; return the number of failures.

        Parameters added in v0.8 for GUI control:

        only_rows:
            Restrict the queue to these Excel row numbers ("Run Selected").
        should_stop:
            Zero-arg callable polled *between* cases; return True to finish
            the current case and stop ("Stop after current case").
        """
        # Sprint 3: never let a retry count or summary leak between studies.
        self._retries_used = 0
        self._current_study_summary = None

        todo = self.excel.pending(retry_failed=retry_failed,
                                  rerun_stale_running=self.cfg.runtime.rerun_stale_running)
        if only_rows is not None:
            todo = [e for e in todo if e.row in only_rows]
        if not todo:
            log.info("Nothing to do — every row is DONE or SKIP. "
                     "(Use --retry-failed to re-run FAILED rows.)")
            self._current_study_summary = self._finalize_study_summary([])
            self.bus.emit("batch.finished", ok=0, failed=0, stopped=False)
            return 0
        if max_cases > 0:
            todo = todo[:max_cases]

        log.info("=== %d case(s) queued ===", len(todo))
        # v0.9-M3: register this batch in the ledger with a config hash.
        if self.ledger is not None:
            try:
                study_id = self.ledger.ensure_study(
                    self.cfg.runtime.study_name,
                    workbook_path=str(self.cfg.excel.file))
                cfg_hash = self.ledger.record_config(self.cfg)
                from cfdauto import __version__ as _ver
                self._batch_id = self.ledger.start_batch(
                    study_id, cfg_hash, total=len(todo),
                    slipstream_version=_ver)
                log.info("Batch %d opened in ledger (study='%s', "
                         "config=%s)", self._batch_id,
                         self.cfg.runtime.study_name, cfg_hash[:12])
            except Exception as exc:
                log.warning("Ledger batch start failed (%s) — continuing "
                            "with Excel only.", exc)
                self._batch_id = None
        self.bus.emit("batch.started", total=len(todo),
                      rows=[e.row for e in todo])
        self.state.acquire_lock()
        failures = 0
        stopped = False
        ran = 0
        # v0.9 M2 hotfix: cascade detector. When Fluent's gRPC server refuses
        # to come up on N consecutive cases it's almost always the ANSYS
        # Student licence being stuck for 30-60 min after a crashed session.
        # Blindly running the next 24 rows just piles more failures and
        # wastes 30+ minutes of wall clock. We halt the batch, kill any
        # orphaned Fluent processes, and tell the user what to do.
        consecutive_launch_failures = 0
        MAX_LAUNCH_FAILURES = 3
        try:
            for i, exp in enumerate(todo, start=1):
                if should_stop is not None and should_stop():
                    log.warning("Stop requested — halting before case %d/%d. "
                                "Re-run to resume the remaining rows.",
                                i, len(todo))
                    stopped = True
                    break
                log.info("--- Case %d/%d: row %d  (AOA=%g deg, V=%g m/s) ---",
                         i, len(todo), exp.row, exp.aoa_deg, exp.velocity)
                self.bus.emit("case.started", row=exp.row, case_id=exp.case_id,
                              index=i, total=len(todo), aoa=exp.aoa_deg,
                              velocity=exp.velocity, extra=dict(exp.extra_wb_params))
                ok = self._run_one(exp)
                # _run_one recorded the error already; check the ledger to
                # decide whether it was a Fluent-launch failure specifically.
                launch_failed = (not ok) and self._last_error_was_fluent_launch(exp)
                ran += 1
                failures += 0 if ok else 1
                if not ok and self.cfg.runtime.stop_on_failure:
                    log.error("stop_on_failure=true — aborting the batch.")
                    break
                # Track consecutive Fluent-launch failures and halt on cascade.
                if launch_failed:
                    consecutive_launch_failures += 1
                    if consecutive_launch_failures >= MAX_LAUNCH_FAILURES:
                        log.error(
                            "%d consecutive Fluent launch failures — halting "
                            "the batch. This is almost always the ANSYS "
                            "Student licence stuck after a crashed session. "
                            "Kill any orphaned Fluent processes, wait 5-10 "
                            "minutes for tokens to release, then re-run with "
                            "--retry-failed to resume.",
                            consecutive_launch_failures)
                        _cleanup_orphaned_fluent()
                        stopped = True
                        break
                elif ok:
                    consecutive_launch_failures = 0     # reset on success
        finally:
            self.state.release_lock()

        done = ran - failures
        log.info("=== Batch finished: %d ok, %d failed%s ===",
                 done, failures, " (stopped early)" if stopped else "")
        if failures:
            log.info("Failed rows keep their error message in the workbook; "
                     "fix the cause and re-run with --retry-failed.")
        # v0.9-M3: finalize the ledger batch and close the connection.
        if self.ledger is not None and self._batch_id is not None:
            try:
                self.ledger.finish_batch(self._batch_id, done, failures, stopped)
                log.info("Ledger batch %d finalized in %s",
                         self._batch_id,
                         self.cfg.work_dir() / "slipstream.db")
            except Exception:
                log.debug("ledger.finish_batch failed", exc_info=True)
            try:
                self.ledger.close()
            except Exception:
                pass
        self.bus.emit("batch.finished", ok=done, failed=failures, stopped=stopped)
        self._current_study_summary = self._finalize_study_summary([e.row for e in todo])
        return failures

    # ------------------------------------------------------------------ #
    def _finalize_study_summary(self, rows: List[int]) -> StudySummary:
        """Compute (and log) the Sprint 3 analytics summary for this run()
        call. study_analytics.analyze_study() is purely computational and
        never logs anything itself — this is the one place that decides
        what to do with its result, matching every other auxiliary system
        in this class (ledger, telemetry): never fatal to the batch."""
        try:
            summary = analyze_study(self.excel, rows, retries=self._retries_used)
        except Exception:
            log.debug("Study analytics failed — non-fatal", exc_info=True)
            return StudySummary(total_cases=len(set(rows)), retries=self._retries_used)

        log.info(
            "Study summary: %d/%d succeeded, %d failed, %d retry attempt(s)%s",
            summary.successful_cases, summary.total_cases, summary.failed_cases,
            summary.retries,
            (f", best L/D={summary.best_l_over_d:.3f} (row {summary.best_l_over_d_row})"
             if summary.best_l_over_d is not None else ""))
        for w in summary.warnings:
            log.warning("Study analytics [%s]: %s", w.code.value, w.message)
        return summary

    # ------------------------------------------------------------------ #
    def _run_one(self, exp: Experiment) -> bool:
        """One experiment end-to-end. Returns True on success."""
        try:
            exp.validate()
        except ValueError as exc:
            self._record_failure(exp, CaseResult(error=str(exc)), str(exc))
            return False

        case_dir = self.state.case_dir(exp)
        # v0.9-M3: register case in ledger before running.
        if self.ledger is not None and self._batch_id is not None:
            try:
                self._current_case_pk = self.ledger.start_case(
                    self._batch_id, exp.row, exp.case_id,
                    exp.aoa_deg, exp.velocity, dict(exp.extra_wb_params))
            except Exception:
                log.debug("ledger.start_case failed", exc_info=True)
                self._current_case_pk = None
        case_handler = add_case_file_handler(case_dir)   # per-case log file
        try:
            self.excel.mark_running(exp, str(case_dir))

            attempts = 1 + max(0, self.cfg.runtime.retries_per_case)
            last_err: Optional[BaseException] = None
            for attempt in range(1, attempts + 1):
                if attempt > 1:
                    self._retries_used += 1   # Sprint 3: batch-wide retry count
                    log.warning("Retry %d/%d for row %d...",
                                attempt - 1, attempts - 1, exp.row)
                try:
                    res = self._attempt(exp, case_dir)
                    self._record_success(exp, res)
                    self._ledger_finish_case(STATUS_DONE, res, case_dir)
                    return True
                except CaseError as exc:
                    last_err = exc
                    log.error("Case failed (attempt %d/%d): %s",
                              attempt, attempts, exc)
                except FrameworkError:
                    raise                                  # config etc. → abort
                except Exception as exc:                   # unexpected bug
                    last_err = exc
                    log.error("Unexpected error (attempt %d/%d):\n%s",
                              attempt, attempts, traceback.format_exc())

            msg = f"{type(last_err).__name__}: {last_err}"
            if last_err is not None:
                try:
                    log.error("Row %d failed permanently:\n%s", exp.row,
                              format_error(last_err, case_dir=case_dir).render_text())
                except Exception:
                    log.debug("format_error failed for row %d", exp.row, exc_info=True)
            failure_res = CaseResult(error=msg, artifact_dir=str(case_dir))
            self._record_failure(exp, failure_res, msg)
            self._ledger_finish_case(STATUS_FAILED, failure_res, case_dir,
                                     error=msg)
            return False
        finally:
            remove_handler(case_handler)
            self._current_case_pk = None

    def _ledger_finish_case(self, status: str, res: CaseResult,
                            case_dir: Path,
                            error: Optional[str] = None) -> None:
        """Best-effort ledger update at case completion."""
        if self.ledger is None or self._current_case_pk is None:
            return
        try:
            payload = {"cl": res.cl, "cd": res.cd,
                       "lift_n": res.lift_n, "drag_n": res.drag_n,
                       "iterations": res.iterations,
                       "converged": res.converged}
            self.ledger.finish_case(self._current_case_pk, status,
                                    result=payload, error=error,
                                    artifact_dir=str(case_dir))
        except Exception:
            log.debug("ledger.finish_case failed", exc_info=True)

    def _attempt(self, exp: Experiment, case_dir: Path) -> CaseResult:
        """Mesh phase (with cache) + solver phase for a single attempt."""
        mesh: Optional[Path] = None
        if self.cfg.fluent.aoa_method == "geometry":
            mesh = self._mesh_for(exp, case_dir)
        else:
            log.info("velocity_vector mode — skipping Workbench, flow will be "
                     "rotated at the inlet instead.")
        res = self.fluent.run_case(exp, mesh, case_dir)
        return res

    def _mesh_for(self, exp: Experiment, case_dir: Path) -> Path:
        if self.cfg.runtime.reuse_mesh_per_geometry:
            cached = self.state.cached_mesh(exp.geometry_key)
            if cached:
                log.info("Mesh cache hit for geometry '%s' → %s "
                         "(Workbench skipped).", exp.geometry_key, cached.name)
                self.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                              stage="mesh", state="cached")
                self.bus.emit("mesh.ready", row=exp.row, case_id=exp.case_id,
                              path=str(cached), cache_hit=True)
                return cached
        if self.wb is None:                               # defensive
            raise FrameworkError("geometry mode requires a Workbench backend")
        fresh = self.wb.prepare_mesh(exp, case_dir)
        # Copy out of the WB project tree (WB overwrites it on the next case).
        stored = self.state.store_mesh(exp.geometry_key, fresh, exp)
        return stored

    # ------------------------------------------------------------------ #
    # Result recording — json first (authoritative), Excel second (ledger)
    # ------------------------------------------------------------------ #
    def _record_success(self, exp: Experiment, res: CaseResult) -> None:
        self.state.write_result_json(exp, {"status": STATUS_DONE,
                                           "experiment": vars(exp) | {},
                                           **res.to_json_dict()})
        self._write_excel(exp, res, STATUS_DONE)
        self.bus.emit("case.done", row=exp.row, case_id=exp.case_id,
                      result=res.to_json_dict())
        log.info("Row %d DONE: CL=%.5f CD=%.5f L/D=%.3f Lift=%.2fN Drag=%.2fN "
                 "(%d it, converged=%s)",
                 exp.row, res.cl or float("nan"), res.cd or float("nan"),
                 res.cl_over_cd or float("nan"), res.lift_n or float("nan"),
                 res.drag_n or float("nan"), res.iterations, res.converged)

    def _record_failure(self, exp: Experiment, res: CaseResult, msg: str) -> None:
        res.error = res.error or msg
        try:
            self.state.write_result_json(exp, {"status": STATUS_FAILED,
                                               "experiment": vars(exp) | {},
                                               **res.to_json_dict()})
        except Exception:
            log.debug("Could not write result.json for failed row %d", exp.row)
        self._write_excel(exp, res, STATUS_FAILED)
        self.bus.emit("case.failed", row=exp.row, case_id=exp.case_id,
                      error=str(res.error or msg)[:500])

    def _write_excel(self, exp: Experiment, res: CaseResult, status: str) -> None:
        try:
            self.excel.write_result(exp, res, status)
        except ExcelWriteError:
            recovery = self.cfg.work_dir() / "recovery_results.csv"
            self.excel.dump_recovery_csv(recovery, exp, res, status)

    def _last_error_was_fluent_launch(self, exp: Experiment) -> bool:
        """Read the row's Error cell we just wrote — if it mentions Fluent
        failing to launch, this was a licence/RPC issue, not a physics one."""
        try:
            row = self.excel.read_row_outputs(exp.row)
            err = str(row.get("Error") or "").lower()
            return ("fluent failed to launch" in err
                    or "rpc" in err
                    or "unavailable" in err
                    or "connection refused" in err)
        except Exception:
            return False


# --------------------------------------------------------------------------- #
def _cleanup_orphaned_fluent() -> None:
    """Kill any leftover Fluent/fl_mpi/cx processes on Windows.

    Called after a launch-failure cascade so the next `--retry-failed` run
    starts with a clean process table. Silent on non-Windows platforms.
    """
    import os
    import subprocess
    if os.name != "nt":
        return
    killed: list[str] = []
    for name in ("fluent.exe", "fl_mpi.exe", "cx.exe", "cxhost.exe"):
        try:
            r = subprocess.run(["taskkill", "/F", "/IM", name],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                killed.append(name)
        except Exception:
            pass
    if killed:
        log.info("Killed orphaned Fluent processes: %s", ", ".join(killed))
    else:
        log.info("No orphaned Fluent processes found.")


# --------------------------------------------------------------------------- #
def summarize_schedule(excel: ExcelManager) -> str:
    """Human-readable dry-run summary of the workbook state."""
    experiments = excel.read_experiments()
    by_status: dict[str, int] = {}
    for e in experiments:
        by_status[e.status or "PENDING"] = by_status.get(e.status or "PENDING", 0) + 1
    lines = [f"{len(experiments)} experiment row(s):"]
    lines += [f"  {k:8s} {v}" for k, v in sorted(by_status.items())]
    geoms = {e.geometry_key for e in experiments}
    lines.append(f"  unique geometries (mesh runs needed at most): {len(geoms)}")
    return "\n".join(lines)


def write_summary_json(cfg: Config, failures: int, queued: int) -> None:
    payload = {"queued": queued, "failures": failures}
    try:
        (cfg.work_dir() / "last_run_summary.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass
