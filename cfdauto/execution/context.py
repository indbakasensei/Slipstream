"""ExecutionContext — everything an execution strategy needs to run a study
(Phase 7).

A single object carrying the configuration, the active template + its study,
the queued experiments, the on-disk paths, the run state (mesh cache /
lock), the mesh/solver adapters, the event bus, and the workbook manager.
It is the runtime environment a :class:`~cfdauto.execution.strategy.ExecutionStrategy`
operates within — passed to it per case, so the strategy never reaches back
into the orchestrator.

Pure data holder; no behaviour. Built by the orchestrator once per
``run()`` call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..events import EventBus
from ..excel_manager import ExcelManager
from ..models import Experiment
from ..platform import SimulationTemplate
from ..state import RunState
from .adapters import MeshBackend, SolverBackend


@dataclass
class ExecutionContext:
    """The runtime environment for executing one study."""

    config: Config
    template: SimulationTemplate
    state: RunState
    solver_backend: SolverBackend
    bus: EventBus
    excel: ExcelManager
    work_dir: Path
    mesh_backend: Optional[MeshBackend] = None
    experiments: List[Experiment] = field(default_factory=list)

    @property
    def study(self):
        """The active template's :class:`StudyDefinition` (may be None)."""
        return self.template.study_definition
