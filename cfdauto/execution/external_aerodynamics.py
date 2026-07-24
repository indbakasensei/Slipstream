"""ExternalAerodynamicsExecutionStrategy — the existing workflow, verbatim
(Phase 7).

This is the External Aerodynamics execution workflow lifted **unchanged**
out of ``Orchestrator._attempt`` / ``_mesh_for`` /
``_last_error_was_fluent_launch`` / ``_cleanup_orphaned_fluent``: in
geometry mode, generate/cache the mesh via the Workbench adapter, then solve
via the Fluent adapter; in velocity_vector mode, skip Workbench. The
Fluent-specific launch-failure detection and orphaned-process cleanup (the
ANSYS Student licence-lockout resilience) live here too — they are Fluent
assumptions, so they belong to this strategy, not the generic loop.

Behaviour is byte-for-byte identical to the pre-Phase-7 orchestrator; only
the *home* of the code changed (``self.cfg`` → ``context.config``,
``self.wb`` → ``context.mesh_backend``, ``self.fluent`` →
``context.solver_backend``, ``self.state``/``self.bus``/``self.excel`` →
the context's).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..exceptions import FrameworkError
from ..models import CaseResult, Experiment
from .context import ExecutionContext
from .strategy import ExecutionStrategy

log = logging.getLogger("cfdauto.execution.external_aerodynamics")


class ExternalAerodynamicsExecutionStrategy(ExecutionStrategy):
    strategy_id = "external-aerodynamics"

    # -- per-case workflow (was Orchestrator._attempt) ------------------ #
    def execute_case(self, experiment: Experiment, context: ExecutionContext,
                     case_dir: Path) -> CaseResult:
        """Mesh phase (with cache) + solver phase for a single attempt."""
        mesh: Optional[Path] = None
        if context.config.fluent.aoa_method == "geometry":
            mesh = self._mesh_for(experiment, context, case_dir)
        else:
            log.info("velocity_vector mode — skipping Workbench, flow will be "
                     "rotated at the inlet instead.")
        return context.solver_backend.run_case(experiment, mesh, case_dir)

    # -- mesh phase (was Orchestrator._mesh_for) ------------------------ #
    def _mesh_for(self, exp: Experiment, context: ExecutionContext,
                  case_dir: Path) -> Path:
        if context.config.runtime.reuse_mesh_per_geometry:
            cached = context.state.cached_mesh(exp.geometry_key)
            if cached:
                log.info("Mesh cache hit for geometry '%s' → %s "
                         "(Workbench skipped).", exp.geometry_key, cached.name)
                context.bus.emit("stage", row=exp.row, case_id=exp.case_id,
                                 stage="mesh", state="cached")
                context.bus.emit("mesh.ready", row=exp.row, case_id=exp.case_id,
                                 path=str(cached), cache_hit=True)
                return cached
        if context.mesh_backend is None:                  # defensive
            raise FrameworkError("geometry mode requires a Workbench backend")
        fresh = context.mesh_backend.prepare_mesh(exp, case_dir)
        # Copy out of the WB project tree (WB overwrites it on the next case).
        stored = context.state.store_mesh(exp.geometry_key, fresh, exp)
        return stored

    # -- cascade hooks (were Orchestrator._last_error... / module fn) --- #
    def is_launch_failure(self, experiment: Experiment,
                          context: ExecutionContext) -> bool:
        """Read the row's Error cell we just wrote — if it mentions Fluent
        failing to launch, this was a licence/RPC issue, not a physics one."""
        try:
            row = context.excel.read_row_outputs(experiment.row)
            err = str(row.get("Error") or "").lower()
            return ("fluent failed to launch" in err
                    or "rpc" in err
                    or "unavailable" in err
                    or "connection refused" in err)
        except Exception:
            return False

    def cleanup_after_cascade(self, context: ExecutionContext) -> None:
        """Kill any leftover Fluent/fl_mpi/cx processes on Windows.

        Called after a launch-failure cascade so the next ``--retry-failed``
        run starts with a clean process table. Silent on non-Windows
        platforms.
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
