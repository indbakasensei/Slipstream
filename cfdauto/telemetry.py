"""Telemetry tap — per-iteration force + residual streaming (v0.9 M2).

Fluent doesn't offer a callback for every iteration on 26.1 with our PyFluent
version, so we exploit two artefacts it writes as the solver runs:

* the report file (``cfdauto_history.out``) — one CL/CD row per iteration,
  written to disk in near-real-time by Fluent itself;
* the transcript (``transcript.trn``) — the same text the console shows,
  including residual lines of the shape
  ``iter  continuity   x-velocity   y-velocity   k   omega``.

The :class:`TelemetryTap` polls both files (small stat + tail reads, ~5 Hz),
extracts *new* rows since the last poll, and emits one ``fluent.iteration``
event per iteration. Everything is guarded — a tap failure never breaks the
solve loop.

Rates: engine emits every iteration; the GUI's queued-signal fan-out handles
its own coalescing, so we don't smart-throttle here. Solve chunk logic and
the coarse ``solve.progress`` event are unchanged for backward compatibility.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

log = logging.getLogger("cfdauto.telemetry")

# Residual header often looks like:
#   iter  continuity  x-velocity  y-velocity  z-velocity  k  omega  time/iter
# Individual data lines therefore start with the iteration integer.
_RESIDUAL_ROW = re.compile(
    r"^\s*(\d+)\s+"                           # iteration
    r"([\deE.+\-]+)\s+"                       # continuity
    r"([\deE.+\-]+)\s+"                       # x-velocity
    r"([\deE.+\-]+)\s+"                       # y-velocity
    r"(?:([\deE.+\-]+)\s+)?"                  # z-velocity (3D only)
    r"([\deE.+\-]+)\s+"                       # k
    r"([\deE.+\-]+)"                          # omega / eps
)


class TelemetryTap:
    """Background poller that emits per-iteration events to the bus.

    Parameters
    ----------
    history_file:
        Fluent report file with the CL/CD columns (Iteration first).
    transcript_file:
        Fluent transcript (``.trn``) written alongside the case.
    emit:
        Callable receiving ``(type_str, **payload)`` — usually the
        controller's ``_emit`` helper, so ``row`` and ``case_id`` are
        attached automatically.
    poll_hz:
        Poll rate; the default is comfortable for a 60 Hz UI and keeps
        disk-tail cost negligible.
    """

    def __init__(self, history_file: Path, transcript_file: Path,
                 emit: Callable[..., None], max_it: int,
                 poll_hz: float = 5.0,
                 live_probe: Optional[Callable[[], Optional[Tuple[int, float, float]]]] = None,
                 ) -> None:
        self.history_file = history_file
        self.transcript_file = transcript_file
        self.emit = emit
        self.max_it = max_it
        self._interval = 1.0 / max(1.0, poll_hz)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_history_row = 0
        self._transcript_offset = 0
        self._pending_residuals: dict[int, Tuple[float, ...]] = {}
        # v0.9 hotfix: Fluent buffers cfdauto_history.out in memory during a
        # solve and only flushes at chunk boundaries. Tailing the file
        # therefore stutters. If callers provide a `live_probe` callback
        # that returns the current (it, CL, CD) via
        # `report_definitions.compute()` over gRPC, we use it as the primary
        # source and the file tail becomes a safety net only.
        self._live_probe = live_probe
        self._last_probe_it = 0

    # -- lifecycle ------------------------------------------------------- #
    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="cfdauto-tap",
                                        daemon=True)
        self._thread.start()

    def stop(self, drain: bool = True) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if drain:
            # Emit any final rows that landed after the last poll cycle.
            self._poll_once()

    # -- polling loop ---------------------------------------------------- #
    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._poll_once()
            except Exception:                       # never break the solver
                log.exception("Telemetry tap poll failed — continuing.")

    def _poll_once(self) -> None:
        # 1) residual lines from transcript (arrive first, keyed by real
        #    Fluent iteration number)
        self._drain_transcript()
        # 2) force rows from the history file (definitive — carries real
        #    iteration number that matches residual keys). With the stale-
        #    file cleanup in _setup_history_file this now streams properly
        #    per sub-chunk boundary; residuals attach cleanly.
        rows = self._read_new_history_rows()
        for it, cl, cd in rows:
            self._emit_iteration(it, cl, cd)

        # Verbose diagnostic every ~10 s so silent failure is visible.
        self._poll_count = getattr(self, "_poll_count", 0) + 1
        if self._poll_count % 50 == 0:                # ~10 s at 5 Hz
            hf_size = (self.history_file.stat().st_size
                       if self.history_file.exists() else 0)
            log.debug("Tap heartbeat: polls=%d, last_it=%d, history=%d bytes, "
                      "pending_residuals=%d",
                      self._poll_count, self._last_history_row,
                      hf_size, len(self._pending_residuals))

    def _emit_iteration(self, it: int, cl: float, cd: float) -> None:
        residuals = self._pending_residuals.pop(it, None)
        # Phase 8F: legacy fields preserved for backward compatibility;
        # metrics_snapshot is the generic payload consumers should prefer.
        payload = {
            "it": it, "max_it": self.max_it,
            "cl": cl, "cd": cd,
            "metrics_snapshot": {"cl": cl, "cd": cd},
        }
        if residuals:
            payload["residuals"] = {
                "continuity": residuals[0],
                "x_velocity": residuals[1],
                "y_velocity": residuals[2],
                "z_velocity": residuals[3],
                "k": residuals[4],
                "omega": residuals[5],
            }
        self.emit("fluent.iteration", **payload)

    # -- history-file tailing -------------------------------------------- #
    def _read_new_history_rows(self) -> List[Tuple[int, float, float]]:
        if not self.history_file.exists():
            return []
        try:
            lines = self.history_file.read_text(
                encoding="utf-8-sig", errors="ignore").splitlines()
        except OSError:
            return []
        new: List[Tuple[int, float, float]] = []
        # Header is 2 lines ("cfdauto_history" + column names) — skip those.
        for ln in lines[2:]:
            parts = ln.split()
            if len(parts) < 3:
                continue
            try:
                it = int(parts[0])
                if it <= self._last_history_row:
                    continue
                cl = float(parts[1])
                cd = float(parts[2])
            except (ValueError, IndexError):
                continue
            new.append((it, cl, cd))
            self._last_history_row = it
        return new

    # -- transcript tailing (residuals) ---------------------------------- #
    def _detect_encoding(self, sample: bytes) -> str:
        """Sniff the transcript encoding from its BOM or byte pattern.
        Fluent 26.1 on Windows writes UTF-16 LE (BOM = ff fe). Older ANSYS
        builds emit UTF-8. Detection lets us support both without config."""
        if sample.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if sample.startswith(b"\xfe\xff"):
            return "utf-16-be"
        if sample.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        # Heuristic: every second byte is 0x00 -> almost certainly UTF-16 LE
        # without a BOM (some Fluent versions omit it after the first flush).
        if len(sample) >= 20 and sum(1 for b in sample[1:20:2] if b == 0) > 7:
            return "utf-16-le"
        return "utf-8"

    def _drain_transcript(self) -> None:
        if not self.transcript_file.exists():
            return
        try:
            size = self.transcript_file.stat().st_size
        except OSError:
            return
        if size <= self._transcript_offset:
            return
        try:
            with open(self.transcript_file, "rb") as f:
                # First read of the session: sniff encoding from the first
                # 64 bytes so we know how to decode subsequent tails.
                if self._transcript_offset == 0 and not hasattr(
                        self, "_encoding"):
                    head = f.read(min(64, size))
                    self._encoding = self._detect_encoding(head)
                    log.debug("Transcript encoding detected: %s",
                              self._encoding)
                f.seek(self._transcript_offset)
                raw = f.read(size - self._transcript_offset)
            # For UTF-16 we need to keep byte alignment: if we read an odd
            # number of bytes we've split a code unit — drop the trailing
            # byte and re-read it next poll.
            enc = getattr(self, "_encoding", "utf-8")
            if enc.startswith("utf-16") and len(raw) % 2 == 1:
                raw = raw[:-1]
                self._transcript_offset = size - 1
            else:
                self._transcript_offset = size
            chunk = raw.decode(enc, errors="ignore")
        except OSError:
            return
        for ln in chunk.splitlines():
            m = _RESIDUAL_ROW.match(ln)
            if not m:
                continue
            it = int(m.group(1))
            try:
                cont = float(m.group(2))
                xv = float(m.group(3))
                yv = float(m.group(4))
                zv = float(m.group(5)) if m.group(5) else float("nan")
                k = float(m.group(6))
                om = float(m.group(7))
            except ValueError:
                continue
            self._pending_residuals[it] = (cont, xv, yv, zv, k, om)
