"""Excel schedule handling.

Design decision: **the workbook itself is the run database.**  The Status
column is the state machine (PENDING → RUNNING → DONE/FAILED), which gives
resume-after-interruption for free — restart the tool and it simply picks the
first row that is not DONE/SKIP.  Every result is *also* mirrored to a JSON
file per case, so even if the workbook is locked by the user the data is never
lost.

openpyxl (not pandas) is used for writing so the user's formatting, extra
columns and hand-written formulas are preserved untouched.
"""

from __future__ import annotations

import csv
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .config import ExcelConfig
from .exceptions import ConfigError, ExcelWriteError
from .models import (Experiment, CaseResult, STATUS_DONE, STATUS_FAILED,
                     STATUS_PENDING, STATUS_RUNNING, STATUS_SKIP)

log = logging.getLogger(__name__)

WB_PARAM_PREFIX = "WBP:"          # extra Workbench-parameter columns
_HEADER_FONT = Font(bold=True)


class ExcelManager:
    """Owns the workbook: column mapping, experiment parsing, result writing."""

    def __init__(self, cfg: ExcelConfig):
        self.cfg = cfg
        self.path = cfg.path()
        self.wb = load_workbook(self.path)
        if cfg.sheet not in self.wb.sheetnames:
            raise ConfigError(
                f"Sheet '{cfg.sheet}' not found in {self.path}. "
                f"Available sheets: {self.wb.sheetnames}"
            )
        self.ws: Worksheet = self.wb[cfg.sheet]
        self._col: Dict[str, int] = {}          # header text -> column index
        self._wbp_cols: Dict[str, int] = {}     # WB param name -> column index
        self._map_columns()

    # ------------------------------------------------------------------ #
    # Column discovery
    # ------------------------------------------------------------------ #
    def _map_columns(self) -> None:
        hdr_row = self.cfg.header_row
        for cell in self.ws[hdr_row]:
            if cell.value is None:
                continue
            name = str(cell.value).strip()
            self._col[name] = cell.column
            if name.upper().startswith(WB_PARAM_PREFIX):
                self._wbp_cols[name[len(WB_PARAM_PREFIX):].strip()] = cell.column

        c = self.cfg.columns
        for required in (c.aoa, c.velocity):
            if required not in self._col:
                raise ConfigError(
                    f"Required input column '{required}' not found in header row "
                    f"{hdr_row} of sheet '{self.cfg.sheet}'. Found: {sorted(self._col)}"
                )

        # Create any missing output columns at the right-hand edge (headers
        # only — never reorders or touches the user's existing layout).
        created = []
        for name in c.output_names():
            if name not in self._col:
                col_idx = self.ws.max_column + 1
                cell = self.ws.cell(row=hdr_row, column=col_idx, value=name)
                cell.font = _HEADER_FONT
                self.ws.column_dimensions[get_column_letter(col_idx)].width = max(10, len(name) + 2)
                self._col[name] = col_idx
                created.append(name)
        if created:
            log.info("Added missing result columns to the schedule: %s", ", ".join(created))
            self.save()

    def _cell(self, row: int, header: str):
        return self.ws.cell(row=row, column=self._col[header])

    # ------------------------------------------------------------------ #
    # Reading the schedule
    # ------------------------------------------------------------------ #
    def read_experiments(self) -> List[Experiment]:
        """Parse every schedule row that has both inputs filled in."""
        c = self.cfg.columns
        experiments: List[Experiment] = []
        for row in range(self.cfg.header_row + 1, self.ws.max_row + 1):
            aoa = self._cell(row, c.aoa).value
            vel = self._cell(row, c.velocity).value
            if aoa is None and vel is None:
                continue  # blank spacer row
            if aoa is None or vel is None:
                log.warning("Row %d skipped: needs both AOA and velocity.", row)
                continue
            try:
                exp = Experiment(
                    row=row,
                    aoa_deg=float(aoa),
                    velocity=float(vel),
                    status=str(self._cell(row, c.status).value or "").strip().upper(),
                    extra_wb_params={
                        name: float(self.ws.cell(row=row, column=col).value)
                        for name, col in self._wbp_cols.items()
                        if self.ws.cell(row=row, column=col).value is not None
                    },
                )
            except (TypeError, ValueError) as exc:
                # Cell content that cannot even be parsed as a number.
                log.warning("Row %d skipped (unreadable value): %s", row, exc)
                continue
            # NOTE: value *validation* (e.g. velocity > 0) is deliberately NOT
            # done here — the orchestrator validates and marks such rows
            # FAILED in the workbook, which is far more visible to the user
            # than a console warning.
            experiments.append(exp)
        return experiments

    def pending(self, retry_failed: bool, rerun_stale_running: bool) -> List[Experiment]:
        """Rows that still need to run, honouring resume semantics."""
        todo: List[Experiment] = []
        for exp in self.read_experiments():
            s = exp.status
            if s in ("", STATUS_PENDING):
                todo.append(exp)
            elif s == STATUS_RUNNING and rerun_stale_running:
                log.warning("Row %d was left RUNNING by a previous session — re-queuing.", exp.row)
                todo.append(exp)
            elif s == STATUS_FAILED and retry_failed:
                todo.append(exp)
            elif s not in (STATUS_DONE, STATUS_SKIP, STATUS_FAILED, STATUS_RUNNING):
                log.warning("Row %d has unknown status '%s' — treating as pending.", exp.row, s)
                todo.append(exp)
        return todo

    # ------------------------------------------------------------------ #
    # Writing results
    # ------------------------------------------------------------------ #
    def mark_running(self, exp: Experiment, case_dir: str) -> None:
        c = self.cfg.columns
        self._cell(exp.row, c.status).value = STATUS_RUNNING
        self._cell(exp.row, c.error).value = ""
        self._cell(exp.row, c.case_dir).value = case_dir
        self.save()

    def write_result(self, exp: Experiment, res: CaseResult, status: str) -> None:
        """Write one complete result row.  Numeric values (not formulas) are
        written so the sheet is immediately valid for pandas / resume logic."""
        c = self.cfg.columns

        def put(header: str, value, fmt: Optional[str] = None):
            cell = self._cell(exp.row, header)
            cell.value = value
            if fmt and value is not None:
                cell.number_format = fmt

        put(c.status, status)
        put(c.cl, res.cl, "0.00000")
        put(c.cd, res.cd, "0.00000")
        put(c.cl_cd, None if res.cl_over_cd is None else round(res.cl_over_cd, 4), "0.0000")
        put(c.lift, res.lift_n, "0.000")
        put(c.drag, res.drag_n, "0.000")
        put(c.fl_fd, None if res.fl_over_fd is None else round(res.fl_over_fd, 4), "0.0000")
        put(c.iterations, res.iterations)
        put(c.converged, "YES" if res.converged else "NO")
        put(c.error, (res.error or "")[:500])
        put(c.started, res.started.strftime("%Y-%m-%d %H:%M:%S") if res.started else None)
        put(c.finished, res.finished.strftime("%Y-%m-%d %H:%M:%S") if res.finished else None)
        put(c.duration, res.duration_min, "0.00")
        put(c.case_dir, res.artifact_dir)
        self.save()

    # ------------------------------------------------------------------ #
    # GUI-facing helpers (v0.8) — small, additive, reuse the column map
    # ------------------------------------------------------------------ #
    def wbp_names(self) -> List[str]:
        """Names of the extra Workbench-parameter columns (``WBP:`` prefix)."""
        return sorted(self._wbp_cols)

    def read_row_outputs(self, row: int) -> Dict[str, object]:
        """Raw output-cell values for one row (for the dataset table/charts).

        Keys are canonical (cl, cd, cl_cd, lift, drag, iterations, converged,
        error, duration, case_dir) — independent of the user's header names.
        """
        c = self.cfg.columns
        out: Dict[str, object] = {}
        for key, header in (("cl", c.cl), ("cd", c.cd), ("cl_cd", c.cl_cd),
                            ("lift", c.lift), ("drag", c.drag),
                            ("iterations", c.iterations),
                            ("converged", c.converged), ("error", c.error),
                            ("duration", c.duration), ("case_dir", c.case_dir)):
            col = self._col.get(header)
            out[key] = self.ws.cell(row=row, column=col).value if col else None
        return out

    def update_input(self, row: int, field: str, value: float) -> None:
        """Edit one input cell of a *not-yet-run* row.

        ``field`` is ``"aoa"``, ``"velocity"``, or a WBP parameter name.
        The GUI is responsible for only offering this on PENDING/FAILED/SKIP
        rows; the manager just writes and saves.
        """
        c = self.cfg.columns
        if field == "aoa":
            col = self._col[c.aoa]
        elif field == "velocity":
            col = self._col[c.velocity]
        elif field in self._wbp_cols:
            col = self._wbp_cols[field]
        else:
            raise KeyError(f"Unknown input field '{field}'")
        self.ws.cell(row=row, column=col).value = float(value)
        self.save()

    def set_status(self, row: int, status: str) -> None:
        """Directly set the Status cell (e.g. toggle SKIP, clear to re-queue)."""
        self._cell(row, self.cfg.columns.status).value = status or None
        self.save()

    def append_experiment(self, aoa: float, velocity: float,
                          extra: Optional[Dict[str, float]] = None) -> int:
        """Add a new schedule row after the last populated one; returns its
        row number. Copies the input-cell number format from the row above so
        the sheet keeps looking hand-made."""
        c = self.cfg.columns
        last = self.cfg.header_row
        col_aoa, col_vel = self._col[c.aoa], self._col[c.velocity]
        for r in range(self.cfg.header_row + 1, self.ws.max_row + 1):
            if (self.ws.cell(row=r, column=col_aoa).value is not None
                    or self.ws.cell(row=r, column=col_vel).value is not None):
                last = r
        row = last + 1
        for col, value in ((col_aoa, float(aoa)), (col_vel, float(velocity))):
            cell = self.ws.cell(row=row, column=col, value=value)
            above = self.ws.cell(row=max(self.cfg.header_row + 1, row - 1),
                                 column=col)
            if above.number_format and above.number_format != "General":
                cell.number_format = above.number_format
        for name, value in (extra or {}).items():
            if name in self._wbp_cols:
                self.ws.cell(row=row, column=self._wbp_cols[name],
                             value=float(value))
        self.save()
        return row

    # ------------------------------------------------------------------ #
    # Crash-safe saving
    # ------------------------------------------------------------------ #
    def save(self) -> None:
        """Atomic save with retries.

        Two real-world failure modes are handled:
        * process killed mid-write  → write to a temp file, then ``os.replace``
          (atomic on the same filesystem), so the workbook is never truncated;
        * user has the file open in Excel (Windows write lock) → retry with a
          countdown message; after the retry budget, raise ExcelWriteError.
          Results are additionally persisted as JSON per case by the
          orchestrator, so nothing is lost either way.
        """
        tmp = self.path.with_suffix(".xlsx.tmp")
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.cfg.save_retries + 1):
            try:
                self.wb.save(tmp)
                os.replace(tmp, self.path)
                return
            except PermissionError as exc:
                last_exc = exc
                log.warning(
                    "Workbook is locked (open in Excel?). Retry %d/%d in %.0fs — "
                    "please close '%s'.",
                    attempt, self.cfg.save_retries, self.cfg.save_retry_wait_s, self.path.name,
                )
                time.sleep(self.cfg.save_retry_wait_s)
            except Exception as exc:  # disk full, sync drive weirdness, ...
                last_exc = exc
                log.error("Workbook save failed (attempt %d): %s", attempt, exc)
                time.sleep(1.0)
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise ExcelWriteError(f"Could not save {self.path}: {last_exc}")

    # ------------------------------------------------------------------ #
    def dump_recovery_csv(self, path: Path, exp: Experiment, res: CaseResult, status: str) -> None:
        """Last-resort sidecar written when the workbook stays locked."""
        new = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if new:
                w.writerow(["row", "aoa_deg", "velocity", "status", "cl", "cd",
                            "cl_cd", "lift_n", "drag_n", "fl_fd", "iterations",
                            "converged", "error"])
            w.writerow([exp.row, exp.aoa_deg, exp.velocity, status, res.cl, res.cd,
                        res.cl_over_cd, res.lift_n, res.drag_n, res.fl_over_fd,
                        res.iterations, res.converged, res.error])
        log.error("Result for row %d written to recovery file %s — merge it into the "
                  "workbook manually or rerun after closing Excel.", exp.row, path)
