"""Study I/O layer — the mapping boundary between a study's spreadsheet
representation and the runtime model (Universal Platform, Phase 5).

Responsibilities:

* resolve which spreadsheet column carries each of a study's input
  parameters (template metadata + the project's ``ColumnMap``);
* interpret a raw spreadsheet row into a generic :class:`Experiment`
  (blank / partially-filled / unreadable rows handled exactly as before);
* expose the ordered import/export column metadata a workbook reader or
  generator iterates over;
* offer template-driven row validation via ``ExperimentDefinition``.

Design split (see ``docs/PLATFORM_ARCHITECTURE.md``):

* ``StudyDefinition`` (platform) — *owns* the input metadata.
* ``ExperimentDefinition`` (runtime) — *materializes* it (rows, values).
* ``StudyIO`` (this module) — *serializes* it: how a study maps to/from a
  spreadsheet. It performs no file I/O itself; :class:`ExcelManager` owns
  the openpyxl workbook and delegates the per-row mapping here, so there is
  exactly one place that knows the template↔spreadsheet correspondence.

Backward compatibility: a study parameter's ``name`` is also the attribute
name on ``config.ColumnMap`` for the two built-in inputs
(``aoa`` → ``ColumnMap.aoa`` → ``"AOA_deg"``; ``velocity`` →
``ColumnMap.velocity`` → ``"Velocity_m_s"``). Column resolution therefore
honours any user ``ColumnMap`` override while iterating the template — a
renamed column keeps working, and no header is hardcoded.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from .config import ColumnMap
from .experiment_definition import ExperimentDefinition
from .models import Experiment
from .simulation_context import SimulationContext

log = logging.getLogger(__name__)


class StudyIO:
    """Maps a study's template metadata to/from its spreadsheet columns."""

    def __init__(self, experiment_definition: ExperimentDefinition,
                 column_map: ColumnMap) -> None:
        self.exp_def = experiment_definition
        self.column_map = column_map

    @classmethod
    def default(cls, column_map: ColumnMap) -> "StudyIO":
        """Build for the registry-default study (External Aerodynamics). Kept
        for genuine defaults; project-aware callers should prefer
        :meth:`for_config`."""
        return cls(ExperimentDefinition.from_context(SimulationContext.default()),
                   column_map)

    @classmethod
    def for_config(cls, cfg) -> "StudyIO":
        """Build the study-I/O mapping for a **project** — its template's
        study definition, with the project's ``excel.columns`` overrides
        (Capability 3 — no default template assumption)."""
        return cls(ExperimentDefinition.for_config(cfg), cfg.excel.columns)

    # ------------------------------------------------------------------ #
    # Column resolution: study parameter -> actual spreadsheet header
    # ------------------------------------------------------------------ #
    def input_column_header(self, param_name: str) -> str:
        """The spreadsheet header carrying ``param_name`` — the project's
        ``ColumnMap`` value if it defines one (honours user renames), else
        the template's declared ``column_name``."""
        override = getattr(self.column_map, param_name, None)
        if override:
            return override
        sp = self.exp_def.study.parameter(param_name)
        return sp.column_name if sp is not None else param_name

    def input_parameter_names(self) -> List[str]:
        """Ordered study input parameter names (``["aoa", "velocity"]``)."""
        return [p.name for p in self.exp_def.study.ordered()]

    def input_column_headers(self) -> List[str]:
        """Ordered actual spreadsheet headers for the study's inputs."""
        return [self.input_column_header(name)
                for name in self.input_parameter_names()]

    # ------------------------------------------------------------------ #
    # Import: raw cell values -> Experiment (byte-identical skip rules)
    # ------------------------------------------------------------------ #
    def interpret_row(self, row: int, input_values: Dict[str, object],
                      wbp_values: Dict[str, object], status: str
                      ) -> Tuple[Optional[Experiment], Optional[str]]:
        """Turn one schedule row's raw cells into an :class:`Experiment`.

        ``input_values`` maps study parameter *name* → raw cell value;
        ``wbp_values`` maps WBP parameter name → raw cell value. Returns
        ``(experiment, warning)``; ``experiment`` is ``None`` when the row
        should be skipped (``warning`` is ``None`` for a blank spacer row,
        or a message for a partially-filled / unreadable row). This
        reproduces the original reader's behaviour exactly.
        """
        present = [v for v in input_values.values() if v is not None]
        if not present:
            return None, None                       # blank spacer row
        if len(present) != len(input_values):
            missing = [n for n, v in input_values.items() if v is None]
            return None, (f"Row {row} skipped: needs a value for every input "
                          f"({', '.join(missing)} missing).")
        try:
            values = {name: float(v) for name, v in input_values.items()}
            extra = {name: float(v) for name, v in wbp_values.items()
                     if v is not None}
        except (TypeError, ValueError) as exc:
            return None, f"Row {row} skipped (unreadable value): {exc}"

        exp = self.exp_def.build_experiment(row, values, status=status,
                                            extra_wb_params=extra)
        return exp, None

    # ------------------------------------------------------------------ #
    # Validation (template-driven; delegates to ExperimentDefinition)
    # ------------------------------------------------------------------ #
    def validate_row(self, values: Dict[str, object]) -> List[str]:
        """Validate a name→value input row against the template's parameter
        metadata (min/max/required/type). Returns every problem."""
        return self.exp_def.validate_row(values)

    # ------------------------------------------------------------------ #
    # Export metadata (for the workbook generator / round-trip)
    # ------------------------------------------------------------------ #
    def export_input_headers(self) -> List[str]:
        """Ordered input column headers for a freshly generated workbook —
        the template's own column names (generation default)."""
        return self.exp_def.column_names()

    def default_experiment_rows(self) -> List[Tuple[float, ...]]:
        """The default example sweep for a fresh workbook (materialized)."""
        return self.exp_def.default_experiment_rows()
