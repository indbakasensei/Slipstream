"""Run state on disk.

Layout created under ``runtime.work_dir`` (default ``runs/``)::

    runs/
      cfdauto.lock              one process at a time (a wbpj can't be shared)
      mesh_cache.json           geometry_key -> cached mesh file (survives restarts)
      meshes/                   copies of every generated Fluent mesh
      cases/
        r05_aoa8_v30/           per-case artifacts:
          wb_update.wbjn        exact journal that was executed
          wb_status.json        what happened inside Workbench
          transcript.trn        Fluent transcript
          cl_history.out ...    monitor histories used for convergence
          result.json           authoritative copy of the extracted results
          case.log              full debug log for just this case
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from .exceptions import FrameworkError
from .models import Experiment

log = logging.getLogger(__name__)


class RunState:
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.cases_dir = work_dir / "cases"
        self.meshes_dir = work_dir / "meshes"
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        self.meshes_dir.mkdir(parents=True, exist_ok=True)
        self._lock_path = work_dir / "cfdauto.lock"
        self._mesh_cache_path = work_dir / "mesh_cache.json"
        self._mesh_cache: Dict[str, str] = self._load_mesh_cache()

    # ------------------------------------------------------------------ #
    # Single-instance lock — two runs updating one .wbpj is data corruption.
    # ------------------------------------------------------------------ #
    def acquire_lock(self) -> None:
        if self._lock_path.exists():
            stale_pid = self._lock_path.read_text(encoding="utf-8").strip()
            if _pid_alive(stale_pid):
                raise FrameworkError(
                    f"Another run (PID {stale_pid}) already owns {self._lock_path}. "
                    f"If that process is truly dead, delete the lock file and retry."
                )
            log.warning("Removing stale lock left by dead PID %s.", stale_pid)
            self._lock_path.unlink()
        self._lock_path.write_text(str(os.getpid()), encoding="utf-8")

    def release_lock(self) -> None:
        try:
            if self._lock_path.exists():
                self._lock_path.unlink()
        except OSError:  # pragma: no cover
            log.warning("Could not remove lock file %s", self._lock_path)

    # ------------------------------------------------------------------ #
    # Per-case artifact directories
    # ------------------------------------------------------------------ #
    def case_dir(self, exp: Experiment) -> Path:
        d = self.cases_dir / exp.case_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_result_json(self, exp: Experiment, payload: dict) -> Path:
        p = self.case_dir(exp) / "result.json"
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return p

    # ------------------------------------------------------------------ #
    # Mesh cache: geometry_key -> stable copy of the Fluent mesh.
    # Workbench overwrites FFF.msh on every update, so meshes are copied out
    # to runs/meshes/ before the next geometry variant runs.
    # ------------------------------------------------------------------ #
    def _load_mesh_cache(self) -> Dict[str, str]:
        if self._mesh_cache_path.exists():
            try:
                text = self._mesh_cache_path.read_text(encoding="utf-8-sig").strip()
                data = json.loads(text) if text else {}
                if not isinstance(data, dict):
                    raise ValueError("cache root is not an object")
                return data
            except (json.JSONDecodeError, ValueError, OSError) as exc:
                log.warning("mesh_cache.json unreadable (%s) — starting a "
                            "fresh cache.", exc)
        return {}

    def _save_mesh_cache(self) -> None:
        self._mesh_cache_path.write_text(
            json.dumps(self._mesh_cache, indent=2), encoding="utf-8"
        )

    def cached_mesh(self, geometry_key: str) -> Optional[Path]:
        raw = self._mesh_cache.get(geometry_key)
        if raw and Path(raw).exists():
            return Path(raw)
        if raw:
            log.warning("Cached mesh for %s vanished from disk — will remesh.", geometry_key)
            self._mesh_cache.pop(geometry_key, None)
            self._save_mesh_cache()
        return None

    def store_mesh(self, geometry_key: str, source: Path, exp: Experiment) -> Path:
        """Copy the freshly generated mesh into the cache and register it."""
        suffix = "".join(source.suffixes)  # keeps .msh / .msh.h5 intact
        target = self.meshes_dir / f"{exp.case_id}{suffix}"
        shutil.copy2(source, target)
        self._mesh_cache[geometry_key] = str(target)
        self._save_mesh_cache()
        log.debug("Mesh cached: %s -> %s", geometry_key, target)
        return target


def _pid_alive(pid_text: str) -> bool:
    try:
        pid = int(pid_text)
    except ValueError:
        return False
    try:
        os.kill(pid, 0)   # signal 0: existence check (works on Windows too)
    except OSError:
        return False
    return True
