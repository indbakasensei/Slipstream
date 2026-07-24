"""Application state — the single source of truth every panel renders from.

Owns:
* the loaded :class:`~cfdauto.config.Config` and the *one* shared
  :class:`~cfdauto.excel_manager.ExcelManager` (GUI edits and the engine run
  must share the same workbook instance);
* the cached dataset (a pandas ``DataFrame`` of inputs + outputs per row);
* run status (``running``) and the currently selected case.

Panels never touch openpyxl or the engine directly; they read the DataFrame
and call the small mutation methods here, which enforce the "no schedule
edits while a batch is running" rule in exactly one place.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from PySide6.QtCore import QObject, Signal

from cfdauto.config import Config, load_config
from cfdauto.events import Event
from cfdauto.excel_manager import ExcelManager
from cfdauto.experiment_definition import ExperimentDefinition
from cfdauto.logging_setup import setup_logging
from cfdauto.simulation_context import SimulationContext

log = logging.getLogger("gui.state")

OUTPUT_COLS = ["CL", "CD", "L/D", "Lift_N", "Drag_N",
               "Iterations", "Converged", "Error", "CaseDir", "Duration_min"]


class AppState(QObject):
    """Qt-observable project state."""

    datasetChanged = Signal()          # table/charts/stats should refresh
    runStateChanged = Signal(bool)     # True while a batch is executing
    caseSelected = Signal(int)         # Excel row number (or -1)
    projectLoaded = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.config_path: Optional[Path] = None
        self.cfg: Optional[Config] = None
        self.excel: Optional[ExcelManager] = None
        self.df = pd.DataFrame()
        self.wbp_names: List[str] = []
        self.running = False
        self.selected_row = -1
        self.mock_override: Optional[bool] = None   # toolbar toggle
        # Phase 2: runtime metadata source of truth. Always External
        # Aerodynamics for now (resolved via the registry, not hardcoded);
        # panels read parameter/metric labels, units, and bounds from this
        # instead of duplicating literals.
        self.context = SimulationContext.default()
        # Phase 3B: runtime materialization of the study's input schema
        # (spreadsheet columns, editable/validation metadata, default rows).
        self.experiment_definition = ExperimentDefinition.from_context(self.context)

    # ------------------------------------------------------------------ #
    # Project lifecycle
    # ------------------------------------------------------------------ #
    def load_project(self, config_path: str | Path) -> None:
        """(Re)load config + workbook; raises ConfigError on bad input."""
        self.config_path = Path(config_path)
        self.cfg = load_config(self.config_path)
        # Refresh the runtime context with this project's identity (still
        # the External Aerodynamics template — Phase 2 is single-template).
        self.context = SimulationContext.default(project=self.config_path.stem)
        self.experiment_definition = ExperimentDefinition.from_context(self.context)
        # Same logging contract as the CLI: root at DEBUG, rotating file in
        # <work_dir>/logs. The Qt console handler attaches per-run on top.
        setup_logging(self.cfg.work_dir() / "logs")
        self.excel = ExcelManager(self.cfg.excel)
        self.wbp_names = self.excel.wbp_names()
        self.reload_dataset()
        log.info("Project loaded: %s  (%d experiments, WBP: %s)",
                 self.config_path, len(self.df),
                 ", ".join(self.wbp_names) or "none")
        self.projectLoaded.emit()

    @property
    def effective_mock(self) -> bool:
        if self.mock_override is not None:
            return self.mock_override
        return bool(self.cfg and self.cfg.runtime.mock)

    # ------------------------------------------------------------------ #
    # Dataset (inputs ⊕ outputs per schedule row)
    # ------------------------------------------------------------------ #
    def reload_dataset(self) -> None:
        """Full rebuild from the workbook (start-up and after each batch)."""
        assert self.excel is not None
        # Phase 5: the input columns (labels + order + values) come from the
        # active template's study definition, not hardcoded AOA/Velocity.
        study_params = self.experiment_definition.study.ordered()
        input_labels = [p.display_name for p in study_params]     # ["AOA","Velocity"]
        input_names = [p.name for p in study_params]              # ["aoa","velocity"]
        rows: List[Dict[str, object]] = []
        for exp in self.excel.read_experiments():
            out = self.excel.read_row_outputs(exp.row)
            rec: Dict[str, object] = {
                "Row": exp.row, "CaseID": exp.case_id,
                "Status": exp.status or "PENDING",
            }
            for label, name in zip(input_labels, input_names):
                pv = exp.parameter(name)
                rec[label] = pv.value if pv is not None else None
            for name in self.wbp_names:
                rec[name] = exp.extra_wb_params.get(name)
            rec.update({
                "CL": _num(out["cl"]), "CD": _num(out["cd"]),
                "L/D": _num(out["cl_cd"]),
                "Lift_N": _num(out["lift"]), "Drag_N": _num(out["drag"]),
                "Iterations": _num(out["iterations"]),
                "Converged": out["converged"] or "",
                "Error": out["error"] or "",
                "CaseDir": out["case_dir"] or "",
                "Duration_min": _num(out["duration"]),
            })
            rows.append(rec)
        cols = (["Row", "CaseID"] + input_labels + self.wbp_names
                + ["Status"] + OUTPUT_COLS)
        self.df = pd.DataFrame(rows, columns=cols)
        self.datasetChanged.emit()

    # -- live updates driven by engine events (no workbook reads) -------- #
    def apply_event(self, evt: Event) -> None:
        """Keep the cached dataset current while a batch runs."""
        d = evt.data
        if evt.type == "case.started":
            self._set(d["row"], Status="RUNNING", Error="")
        elif evt.type == "case.done":
            r = d.get("result", {})
            ld = r.get("cl_over_cd")
            if ld is None and r.get("cl") is not None and r.get("cd"):
                try:
                    ld = r["cl"] / r["cd"]
                except ZeroDivisionError:
                    ld = None
            self._set(d["row"], Status="DONE",
                      CL=r.get("cl"), CD=r.get("cd"), **{"L/D": ld},
                      Lift_N=r.get("lift_n"), Drag_N=r.get("drag_n"),
                      Iterations=r.get("iterations"),
                      Converged="YES" if r.get("converged") else "NO",
                      Error=r.get("error") or "",
                      CaseDir=r.get("artifact_dir") or "",
                      Duration_min=r.get("duration_min"))
        elif evt.type == "case.failed":
            self._set(d["row"], Status="FAILED", Error=d.get("error", ""))

    def _set(self, row: int, **values) -> None:
        idx = self.df.index[self.df["Row"] == row]
        if len(idx) == 0:
            return
        for col, val in values.items():
            if col in self.df.columns:
                self.df.loc[idx, col] = val
        self.datasetChanged.emit()

    # ------------------------------------------------------------------ #
    # Schedule mutations (blocked while running)
    # ------------------------------------------------------------------ #
    def _editable(self) -> ExcelManager:
        if self.running:
            raise RuntimeError("Schedule is locked while a batch is running.")
        assert self.excel is not None
        return self.excel

    def update_input(self, row: int, field: str, value: float) -> None:
        self._editable().update_input(row, field, value)
        self.reload_dataset()

    def update_inputs(self, row: int, values: Dict[str, float]) -> None:
        """Write several input cells of a row in one shot (keyed by parameter
        *name*). Reloads once, not per field."""
        excel = self._editable()
        for name, value in values.items():
            excel.update_input(row, name, value)
        self.reload_dataset()

    def add_experiment(self, values: Dict[str, float],
                       extra: Optional[Dict[str, float]] = None) -> int:
        """Append a new schedule row from a metadata-driven name→value mapping.

        This is the single UI→runtime *write* bridge: ``ExcelManager.append_
        experiment`` is still airfoil-shaped ``(aoa, velocity, extra)`` (its
        generalization is the documented Phase 8 per-project work), so the
        first two study inputs are mapped onto it positionally — no parameter
        name is hardcoded here, the order comes from the template's
        StudyDefinition. When ExcelManager becomes template-driven this
        collapses to a plain pass-through.
        """
        primary = [p.name for p in self.input_parameters()
                   if p.name not in self.wbp_names]
        aoa = float(values[primary[0]])
        velocity = float(values[primary[1]]) if len(primary) > 1 else 0.0
        r = self._editable().append_experiment(aoa, velocity, extra)
        self.reload_dataset()
        return r

    # ------------------------------------------------------------------ #
    # Template metadata accessors (panels render from these, never literals)
    # ------------------------------------------------------------------ #
    def input_parameters(self):
        """The active study's input parameters, in display order
        (:class:`~cfdauto.platform.study_definition.StudyParameter`)."""
        return self.experiment_definition.study.ordered()

    def primary_input(self):
        """The study's first input parameter (the natural x-axis / range
        headline). None if the study declares no inputs."""
        params = self.input_parameters()
        return params[0] if params else None

    def secondary_input(self):
        """The study's second input parameter (the natural colour/grouping
        variable). Falls back to the primary when only one input exists."""
        params = self.input_parameters()
        if not params:
            return None
        return params[1] if len(params) > 1 else params[0]

    def toggle_skip(self, row: int) -> None:
        cur = str(self.df.loc[self.df["Row"] == row, "Status"].iloc[0])
        new = "" if cur == "SKIP" else "SKIP"
        self._editable().set_status(row, new)
        self.reload_dataset()

    def requeue(self, row: int) -> None:
        """Clear a FAILED/DONE status so the row runs again."""
        self._editable().set_status(row, "")
        self.reload_dataset()

    # ------------------------------------------------------------------ #
    # Selection / run flags
    # ------------------------------------------------------------------ #
    def select_case(self, row: int) -> None:
        self.selected_row = row
        self.caseSelected.emit(row)

    def set_running(self, running: bool) -> None:
        if running != self.running:
            self.running = running
            self.runStateChanged.emit(running)

    def case_dir_for(self, row: int) -> Optional[Path]:
        m = self.df[self.df["Row"] == row]
        if m.empty:
            return None
        cd = str(m["CaseDir"].iloc[0] or "")
        if cd and Path(cd).exists():
            return Path(cd)
        # Fall back to the deterministic layout even before the case ran.
        if self.cfg:
            case_id = str(m["CaseID"].iloc[0])
            p = self.cfg.work_dir() / "cases" / case_id
            return p if p.exists() else None
        return None


def _num(v) -> Optional[float]:
    """Cell value → float or None (never NaN strings in the dataset)."""
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None
