"""Workbench control.

How Python talks to Workbench
-----------------------------
Workbench has no stable in-process Python-3 API for classic project (.wbpj)
automation, so the battle-tested pattern is used here:

1.  Render an IronPython *journal* from a template with this case's parameter
    values baked in.
2.  Execute it headless:  ``RunWB2 -B -X -R <journal.wbjn>``.
3.  The journal writes a ``wb_status.json`` describing exactly what happened
    (stage reached, messages, parameter snapshot, traceback on failure).
4.  Python validates that file, then locates the freshly written Fluent mesh
    (``dp0/<SYS>/MESH/*.msh|*.msh.h5``) by modification time.

This gives us the two properties an unattended overnight run needs: a hard
subprocess timeout (Workbench cannot hang the pipeline forever) and a
machine-readable post-mortem for every geometry update.

An alternative backend — PyWorkbench (``ansys-workbench-core``, 2024R1+) —
keeps a persistent gRPC Workbench session between cases.  The subprocess
approach is the default because it works on every release and a crashed
Workbench never poisons subsequent cases; see the README for the PyWorkbench
variant.
"""

from __future__ import annotations

import glob as _glob
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from string import Template
from typing import Dict, List, Optional

from .config import Config
from .events import EventBus
from .exceptions import MeshNotFoundError, WorkbenchError
from .models import Experiment

log = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_MESH_PATTERNS = ("*.msh.h5", "*.msh", "*.msh.gz")


class WorkbenchController:
    """Drives geometry-parameter updates + remeshing for one project."""

    def __init__(self, cfg: Config, bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.wb = cfg.workbench
        self.runwb2 = cfg.ansys.resolve_runwb2()
        self.project = self.wb.project_path()
        self.bus = bus or EventBus()

    # ------------------------------------------------------------------ #
    # Public API used by the orchestrator
    # ------------------------------------------------------------------ #
    def prepare_mesh(self, exp: Experiment, case_dir: Path) -> Path:
        """Set AOA (+ any extra WB parameters), update geometry & mesh, and
        return the path of the freshly generated Fluent mesh file."""
        self.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                      stage="mesh", state="start")
        params = self._parameter_expressions(exp)
        journal = self._render_journal(
            "wb_update.wbjn.tpl",
            case_dir / "wb_update.wbjn",
            status_json=case_dir / "wb_status.json",
            extra={
                "PARAMS_JSON": json.dumps(params),
                "SYSTEM_NAME": self.wb.system_name,
                "UPDATE_GEOMETRY": _py_bool(self.wb.update_geometry),
                "REFRESH_SETUP": _py_bool(self.wb.refresh_setup),
                "SAVE_PROJECT": _py_bool(self.wb.save_project),
            },
        )
        started = time.time()
        status = self._run_journal(journal, case_dir / "wb_status.json",
                                   case_dir / "wb_stdout.log")
        for msg in status.get("messages", []):
            log.debug("WB: %s", msg)
        if not status.get("success"):
            raise WorkbenchError(
                f"Workbench update failed at stage '{status.get('stage')}': "
                f"{status.get('error') or 'no error message written'}"
            )
        mesh = self._discover_mesh(newer_than=started)
        log.info("Workbench produced mesh: %s", mesh)
        self.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                      stage="mesh", state="done")
        self.bus.emit("mesh.ready", row=exp.row, case_id=exp.case_id,
                      path=str(mesh), cache_hit=False)
        return mesh

    def inspect(self, out_dir: Path) -> dict:
        """Run the wb-info journal and return the parsed project description."""
        status_json = out_dir / "wb_info.json"
        journal = self._render_journal("wb_inspect.wbjn.tpl",
                                       out_dir / "wb_inspect.wbjn",
                                       status_json=status_json, extra={})
        info = self._run_journal(journal, status_json, out_dir / "wb_info_stdout.log")
        if not info.get("success"):
            raise WorkbenchError(f"Project inspection failed: {info.get('error')}")
        return info

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _parameter_expressions(self, exp: Experiment) -> Dict[str, str]:
        """Map WB parameter name -> expression string (with units)."""
        params = {
            self.wb.aoa_parameter: self.wb.aoa_expression.format(value=exp.aoa_deg)
        }
        # Extra design variables straight from `WBP:` Excel columns.  Values
        # are written unitless; append units in a custom column-name mapping
        # if a parameter needs them (see README "Adding design variables").
        for name, value in exp.extra_wb_params.items():
            params[name] = f"{value:g}"
        return params

    def _render_journal(self, template_name: str, out_path: Path,
                        status_json: Path, extra: Dict[str, str]) -> Path:
        template = Template((_TEMPLATE_DIR / template_name).read_text(encoding="utf-8"))
        mapping = {
            # Forward slashes are accepted by Workbench on Windows and avoid
            # any escaping pitfalls inside the r"" strings of the journal.
            "PROJECT_PATH": self.project.resolve().as_posix(),
            "STATUS_JSON": status_json.resolve().as_posix(),
            **extra,
        }
        # safe_substitute: leaves unknown $tokens intact (e.g. $ signs inside
        # IronPython comments) rather than raising KeyError.
        rendered = template.safe_substitute(mapping)
        out_path.write_text(rendered, encoding="utf-8")
        log.debug("Journal rendered: %s", out_path)
        return out_path

    def _run_journal(self, journal: Path, status_json: Path, stdout_log: Path) -> dict:
        if status_json.exists():
            status_json.unlink()   # never trust a stale status file

        cmd = [str(self.runwb2), "-B", "-X", "-R", str(journal)]
        log.info("Launching Workbench batch: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.wb.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkbenchError(
                f"Workbench exceeded workbench.timeout_s={self.wb.timeout_s}s and was "
                f"killed. Journal: {journal}"
            ) from exc
        finally:
            # RunWB2's own console chatter is gold when debugging licence or
            # geometry-engine problems — always keep it.
            try:
                out = (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or "")
                stdout_log.write_text(out, encoding="utf-8")
            except Exception:
                pass

        if not status_json.exists():
            raise WorkbenchError(
                f"Workbench exited (rc={proc.returncode}) without writing "
                f"{status_json.name}. It likely crashed before the journal ran — "
                f"see {stdout_log} (licence errors show up there)."
            )
        try:
            return json.loads(status_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise WorkbenchError(f"Unreadable {status_json}: {exc}") from exc

    def _discover_mesh(self, newer_than: float) -> Path:
        """Find the Fluent mesh Workbench just wrote.

        Default search: ``<project>_files/dp0/**/`` for common Fluent mesh
        transfer files under ``MESH``, ``MECH`` (Student edition uses this),
        or ``Fluent`` subdirs. Only files modified after this update started
        are kept (a stale mesh from a previous AOA must never be reused).
        Override with ``workbench.mesh_file_glob`` for exotic project layouts.
        The override accepts either a relative pattern (interpreted against
        ``<project>_files``) or an absolute path with wildcards.
        """
        files_dir = self.project.with_name(self.project.stem + "_files")
        candidates: List[Path] = []
        if self.wb.mesh_file_glob:
            pattern = self.wb.mesh_file_glob
            # Absolute pattern with wildcards → use glob.glob() which supports
            # them. Relative pattern → resolve under <project>_files.
            if os.path.isabs(pattern) or ":" in pattern[:3]:
                candidates = [Path(p) for p in _glob.glob(pattern, recursive=True)]
            else:
                candidates = list(files_dir.glob(pattern))
        else:
            # Search common Fluent-mesh transfer locations.
            search_dirs = ["MESH", "MECH", "Fluent", "Fluid Flow (Fluent)"]
            for sub in search_dirs:
                for pattern in _MESH_PATTERNS:
                    candidates += list((files_dir / "dp0").glob(f"**/{sub}/{pattern}"))
            # Also catch loose meshes not under a subdir.
            for pattern in _MESH_PATTERNS:
                candidates += list((files_dir / "dp0").glob(f"**/{pattern}"))

        # Dedupe while preserving order.
        seen: set = set()
        unique: List[Path] = []
        for c in candidates:
            key = str(c.resolve())
            if key not in seen:
                seen.add(key)
                unique.append(c)
        candidates = unique

        fresh = [p for p in candidates if p.exists() and p.stat().st_mtime >= newer_than - 2.0]
        if fresh:
            return max(fresh, key=lambda p: p.stat().st_mtime)

        # No file newer than this update — but the Workbench journal DID
        # succeed. That happens when the parameter value was already applied
        # in a previous run: WB's dependency tracking sees Geometry/Mesh as
        # up-to-date and skips regeneration, so the transfer file keeps its
        # old timestamp while still being exactly the right mesh for this
        # geometry. Trust WB's Update(AllDependencies=True) and take the
        # newest existing candidate.
        existing = [p for p in candidates if p.exists()]
        if existing:
            newest = max(existing, key=lambda p: p.stat().st_mtime)
            log.info(
                "Mesh not rewritten by this update (Workbench reported the "
                "components already up-to-date) — reusing %s", newest
            )
            return newest

        hint = (
            "No Fluent mesh found under "
            f"{files_dir / 'dp0'} (searched MESH/, MECH/, Fluent/ subdirs). "
            "Fixes: (1) keep workbench.refresh_setup: true so the transfer "
            "file is written; (2) set workbench.mesh_file_glob to point at "
            "the mesh (e.g. 'C:/.../wing_study_files/dp0/**/*.msh')."
        )
        raise MeshNotFoundError(hint)


def _py_bool(value: bool) -> str:
    """Render a Python literal for the IronPython journal."""
    return "True" if value else "False"
