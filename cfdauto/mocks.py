"""Mock Workbench + Fluent controllers.

Purpose
-------
* Validate the *entire* orchestration layer (Excel resume, mesh caching,
  status columns, retries, artifacts, logging) on any machine — no ANSYS.
* Serve as executable documentation of the controller interfaces: the
  orchestrator depends only on ``prepare_mesh(exp, case_dir) -> Path`` and
  ``run_case(exp, mesh_file, case_dir) -> CaseResult``, so a future backend
  (PyWorkbench, Fluent Meshing, an HPC queue) only has to implement these.

Activated by ``runtime.mock: true`` in the config, the ``--mock`` CLI flag,
or the ``CFDAUTO_MOCK=1`` environment variable.

The fabricated aerodynamics are intentionally plausible (thin-airfoil-ish
lift slope, parabolic drag polar, mild stall) so downstream plots and the
CL↔Lift cross-check behave like a real study.
"""

from __future__ import annotations

import logging
import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Tuple

import struct
import zlib

from . import aero
from .config import Config
from .events import EventBus
from .models import CaseResult, Experiment

log = logging.getLogger("cfdauto.mock")


class MockWorkbenchController:
    """Pretends to rotate the wing and remesh; emits a dummy mesh file."""

    def __init__(self, cfg: Config, bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.bus = bus or EventBus()

    def prepare_mesh(self, exp: Experiment, case_dir: Path) -> Path:
        self.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                      stage="mesh", state="start")
        log.info("[mock] Workbench: set AOA=%.3f deg (+%d extra params), "
                 "update geometry, regenerate mesh...",
                 exp.aoa_deg, len(exp.extra_wb_params))
        time.sleep(0.05)                                   # simulate some work
        mesh = case_dir / "FFF.msh.h5"
        mesh.write_text(
            f"MOCK MESH — geometry_key={exp.geometry_key}\n"
            f"generated={datetime.now().isoformat(timespec='seconds')}\n"
        )
        self.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                      stage="mesh", state="done")
        self.bus.emit("mesh.ready", row=exp.row, case_id=exp.case_id,
                      path=str(mesh), cache_hit=False)
        return mesh

    def inspect(self, out_dir: Path) -> dict:
        return {
            "success": True,
            "systems": [{"name": "FFF", "display_text": "Fluid Flow (Fluent)"}],
            "parameters": [{"name": "P1", "display_text": "AOA", "value": "0 [degree]"}],
        }


class MockFluentController:
    """Returns physically plausible CL/CD/forces for a generic wing."""

    #: Simple model constants (roughly a moderate-AR wing).
    CL0 = 0.25            # zero-AOA lift coefficient (cambered section)
    CL_SLOPE = 0.095      # per degree (< 2*pi/rad due to finite span)
    STALL_DEG = 14.0
    CD0 = 0.012
    K_INDUCED = 0.055     # CD = CD0 + k*CL^2

    def __init__(self, cfg: Config, bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.bus = bus or EventBus()
        self.rng = random.Random(20260702)   # deterministic across runs

    def _emit(self, exp: Experiment, type_: str, **data) -> None:
        self.bus.emit(type_, row=exp.row, case_id=exp.case_id, **data)

    def _stage(self, exp: Experiment, stage: str, state: str = "start") -> None:
        self._emit(exp, "stage", stage=stage, state=state)

    def run_case(self, exp: Experiment, mesh_file: Optional[Path],
                 case_dir: Path) -> CaseResult:
        res = CaseResult(started=datetime.now(),
                         mesh_file=str(mesh_file or ""),
                         artifact_dir=str(case_dir))
        log.info("[mock] Fluent: baseline case, %s, V=%.2f m/s, init, solve...",
                 ("replace mesh " + Path(res.mesh_file).name) if mesh_file
                 else "reuse baseline mesh", exp.velocity)
        for stg in ("fluent_launch", "read_case", "replace_mesh",
                    "setup", "initialize"):
            self._stage(exp, stg); time.sleep(0.01); self._stage(exp, stg, "done")
        self._emit(exp, "fluent.launched", cores=self.cfg.fluent.processor_count)
        self._stage(exp, "solve")

        a = exp.aoa_deg
        cl = self.CL0 + self.CL_SLOPE * a
        if abs(a) > self.STALL_DEG:                        # soft stall roll-off
            cl *= max(0.55, 1.0 - 0.06 * (abs(a) - self.STALL_DEG))
        cd = self.CD0 + self.K_INDUCED * cl * cl
        cl *= 1.0 + self.rng.uniform(-0.004, 0.004)        # solver "noise"
        cd *= 1.0 + self.rng.uniform(-0.004, 0.004)

        ref = self.cfg.fluent.reference
        res.cl, res.cd = round(cl, 5), round(cd, 5)
        res.lift_n = round(aero.force_from_coefficient(cl, ref.density,
                                                       exp.velocity, ref.area), 3)
        res.drag_n = round(aero.force_from_coefficient(cd, ref.density,
                                                       exp.velocity, ref.area), 3)
        res.iterations = int(400 + 30 * abs(a) + self.rng.uniform(0, 60))
        # v0.9 M2: stream one fluent.iteration event per iteration so the
        # Monitor's live plot demonstrates the smooth per-iteration behaviour
        # of the telemetry tap. Coarse solve.progress events are kept for
        # backward compatibility with older subscribers.
        step = max(1, res.iterations // 200)     # cap event volume for demos
        for it in range(step, res.iterations + 1, step):
            f = 1 - math.exp(-it / 80)
            cl_now = round(cl * f + self.rng.uniform(-0.001, 0.001), 6)
            cd_now = round(cd * f + self.rng.uniform(-0.0002, 0.0002), 6)
            # Fabricate plausible residuals that decay as the solve settles.
            base = math.exp(-it / 120)
            self._emit(exp, "fluent.iteration", it=it,
                       max_it=self.cfg.solve.max_iterations,
                       cl=cl_now, cd=cd_now,
                       residuals={
                           "continuity": max(1e-6, 1e-2 * base
                                             + self.rng.uniform(0, 1e-4)),
                           "x_velocity": max(1e-7, 3e-3 * base),
                           "y_velocity": max(1e-7, 3e-3 * base),
                           "z_velocity": max(1e-7, 2e-3 * base),
                           "k": max(1e-7, 5e-3 * base),
                           "omega": max(1e-7, 5e-3 * base),
                       })
            if it % 100 == 0:
                self._emit(exp, "solve.progress", it=it,
                           max_it=self.cfg.solve.max_iterations,
                           cl=cl_now, cd=cd_now)
            time.sleep(0.002)
        self._emit(exp, "solve.converged", it=res.iterations)
        self._stage(exp, "solve", "done")
        res.converged = True
        res.finished = datetime.now()

        self._stage(exp, "extract")
        # Placeholder result pictures so the Images panel is demonstrable
        # without ANSYS (tiny dependency-free PNG writer below).
        for fname, hue in (("geometry.png", 0), ("mesh.png", 1),
                           ("pressure_contour.png", 2),
                           ("velocity_contour.png", 3)):
            try:
                _write_demo_png(case_dir / fname, kind=hue,
                                label_seed=exp.row)
            except Exception:
                pass
        self._stage(exp, "extract", "done")

        # Leave the same artifacts a real run would, so downstream tooling
        # (plots, result.json consumers) can be developed against mock output.
        (case_dir / "cfdauto_history.out").write_text(
            '"cfdauto_history"\n"Iteration" "cfdauto_cl" "cfdauto_cd"\n'
            + "".join(f"{i} {cl * (1 - math.exp(-i / 80)):.6e} "
                      f"{cd * (1 - math.exp(-i / 80)):.6e}\n"
                      for i in range(1, res.iterations + 1, 10))
        )
        return res


# --------------------------------------------------------------------------- #
# Minimal PNG writer (no Pillow/matplotlib): 8-bit RGB, zlib-compressed.
# Produces small synthetic "contour-like" gradients so the GUI's image
# browser has real files to show in mock/demo mode.
# --------------------------------------------------------------------------- #
def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def _write_demo_png(path: Path, kind: int = 0, label_seed: int = 0,
                    w: int = 240, h: int = 150) -> None:
    palettes: Tuple[Tuple[Tuple[int, int, int], ...], ...] = (
        ((40, 44, 52), (120, 130, 150)),            # geometry: greys
        ((30, 34, 40), (90, 200, 250)),             # mesh: cyan grid feel
        ((20, 30, 120), (250, 60, 40)),             # pressure: blue→red
        ((15, 60, 30), (250, 240, 80)),             # velocity: green→yellow
    )
    lo, hi = palettes[kind % len(palettes)]
    rows = bytearray()
    for y in range(h):
        rows.append(0)                               # filter type 0 per row
        for x in range(w):
            # radial-ish field with a per-case phase → images differ per row
            t = 0.5 + 0.5 * math.sin(0.05 * x + 0.09 * y
                                     + 0.7 * (label_seed % 7))
            if kind == 1 and (x % 12 < 1 or y % 12 < 1):   # mesh grid lines
                t = 1.0
            r = int(lo[0] + (hi[0] - lo[0]) * t)
            g = int(lo[1] + (hi[1] - lo[1]) * t)
            b = int(lo[2] + (hi[2] - lo[2]) * t)
            rows += bytes((r, g, b))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    data = (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
            + _png_chunk(b"IEND", b""))
    Path(path).write_bytes(data)
