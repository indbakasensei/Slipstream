"""Adapter protocols — the seams a solver/mesher plugs into (Phase 7).

These structural-typing protocols are the "adapters" the execution
framework talks to: the Workbench controller is a :class:`MeshBackend`, the
Fluent controller is a :class:`SolverBackend`, and the mock controllers fit
both. They lived in ``orchestrator.py`` until Phase 7; they move here so the
execution layer can reference them without importing the orchestrator
(keeping the dependency one-way: ``orchestrator`` → ``execution``).

Behaviour is unchanged — these are the same protocols, structurally
satisfied by the same, untouched ``WorkbenchController`` / ``FluentController``
/ mock classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

from ..models import CaseResult, Experiment


class MeshBackend(Protocol):
    """Owns geometry/mesh generation (the ANSYS Workbench adapter)."""

    def prepare_mesh(self, exp: Experiment, case_dir: Path) -> Path: ...


class SolverBackend(Protocol):
    """Owns the solve (the Fluent adapter)."""

    def run_case(self, exp: Experiment, mesh_file: Optional[Path],
                 case_dir: Path) -> CaseResult: ...
