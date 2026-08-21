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
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from PySide6.QtCore import QObject, Signal

from cfdauto.config import Config, load_config
from cfdauto.events import Event, MonitorMetric
from cfdauto.excel_manager import ExcelManager
from cfdauto.experiment_definition import ExperimentDefinition
from cfdauto.logging_setup import setup_logging
from cfdauto.simulation_context import SimulationContext
from cfdauto.study_analytics import StudySummary, analyze_study

log = logging.getLogger("gui.state")

# Phase 8F: bookkeeping columns are always the same; physics columns come
# from the template's output_columns().
_BOOKKEEPING_COLS = ["Iterations", "Converged", "Error", "CaseDir",
                      "Duration_min"]
# Legacy default for callers that read OUTPUT_COLS without a template context.
OUTPUT_COLS = ["CL", "CD", "L/D", "Lift_N", "Drag_N"] + _BOOKKEEPING_COLS


def _output_cols_for_template(template) -> list:
    """Build the DataFrame output column list from the active template.

    Returns the template's declared output column headers (in display order)
    followed by the universal bookkeeping columns.  Falls back to the legacy
    hardcoded list when the template does not declare any metrics.
    """
    if template is None:
        return list(OUTPUT_COLS)
    metric_cols = [header for _, header in template.output_columns()]
    if not metric_cols:
        return list(OUTPUT_COLS)
    return metric_cols + _BOOKKEEPING_COLS


class AppState(QObject):
    """Qt-observable project state."""

    datasetChanged = Signal()          # table/charts/stats should refresh
    runStateChanged = Signal(bool)     # True while a batch is executing
    caseSelected = Signal(int)         # Excel row number (or -1)
    projectLoaded = Signal()
    studySummaryReady = Signal(object)  # Phase 8E: StudySummary on load/reload

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
        # Phase 8E: post-batch analytics summary, hydrated on project load
        # and updated after every batch run.
        self.study_summary: Optional[StudySummary] = None
        # Phase 8F revision R1+R4: MonitorMetric view model list, built
        # from the template's supported_metrics and sorted by monitor_priority.
        # The MonitorPanel consumes these; it never imports SimulationTemplate.
        self.monitor_metrics: List[MonitorMetric] = []
        self._build_monitor_metrics()

    # ------------------------------------------------------------------ #
    # MonitorMetric view model (Phase 8F R1+R4)
    # ------------------------------------------------------------------ #
    def _build_monitor_metrics(self) -> None:
        """Build the sorted MonitorMetric list from the active template.

        Two bookkeeping tiles (``iterations``, ``residual``) are always
        prepended with negative priority so they appear first.  Physics
        metrics follow sorted by ``monitor_priority``.
        """
        tpl = self.context.template
        metrics: List[MonitorMetric] = [
            MonitorMetric(key="iterations", display_name="Iterations",
                          unit="", monitor_priority=-20),
            MonitorMetric(key="residual", display_name="Min residual",
                          unit="", monitor_priority=-10),
        ]
        for md in tpl.supported_metrics:
            # monitor_priority comes from the metric definition if present,
            # otherwise defaults to 100 + declaration order.
            pri = getattr(md, "monitor_priority", None)
            if pri is None:
                pri = 100 + len(metrics)
            metrics.append(MonitorMetric(
                key=md.name,
                display_name=md.display_name,
                unit=md.unit or "",
                monitor_priority=pri))
        metrics.sort(key=lambda m: m.monitor_priority)
        self.monitor_metrics = metrics

    # ------------------------------------------------------------------ #
    # Project lifecycle
    # ------------------------------------------------------------------ #
    def load_project(self, config_path: str | Path) -> None:
        """(Re)load config + workbook; raises ConfigError on bad input."""
        self.config_path = Path(config_path)
        self.cfg = load_config(self.config_path)
        # Capability 3: restore this project's *own* template (from
        # cfg.template_id()) — study definition, execution strategy, workbook
        # schema, and the dynamic UI all follow from it. An External
        # Aerodynamics project resolves exactly as before.
        self.context = SimulationContext.for_config(self.cfg,
                                                    project=self.config_path.stem)
        self.experiment_definition = ExperimentDefinition.from_context(self.context)
        self._build_monitor_metrics()
        # Same logging contract as the CLI: root at DEBUG, rotating file in
        # <work_dir>/logs. The Qt console handler attaches per-run on top.
        setup_logging(self.cfg.work_dir() / "logs")
        self.excel = ExcelManager.for_config(self.cfg)
        self.wbp_names = self.excel.wbp_names()
        self.reload_dataset()
        # Phase 8E: hydrate Dashboard Study Summary from completed rows
        # on project load — no batch run required.
        self._hydrate_study_summary()
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
                "Row": exp.row, "CaseID": _case_id(exp),
                "Status": exp.status or "PENDING",
            }
            for label, name in zip(input_labels, input_names):
                pv = exp.parameter(name)
                rec[label] = pv.value if pv is not None else None
            for name in self.wbp_names:
                rec[name] = exp.extra_wb_params.get(name)
            # Phase 8F: populate template-declared output columns + bookkeeping.
            out_metrics = {}
            for metric_name, col_header in self.context.template.output_columns():
                # Map known metric names to read_row_outputs keys.
                _key_map = {"cl": "cl", "cd": "cd", "l_over_d": "cl_cd",
                            "lift": "lift", "drag": "drag",
                            "pressure_drop": "pressure_drop",
                            "reynolds_number": "reynolds_number",
                            "friction_factor": "friction_factor"}
                out_key = _key_map.get(metric_name, metric_name)
                out_metrics[col_header] = _num(out.get(out_key))
            rec.update(out_metrics)
            rec.update({
                "Iterations": _num(out["iterations"]),
                "Converged": out["converged"] or "",
                "Error": out["error"] or "",
                "CaseDir": out["case_dir"] or "",
                "Duration_min": _num(out["duration"]),
            })
            rows.append(rec)
        out_cols = _output_cols_for_template(self.context.template)
        cols = (["Row", "CaseID"] + input_labels + self.wbp_names
                + ["Status"] + out_cols)
        self.df = pd.DataFrame(rows, columns=cols)
        self.datasetChanged.emit()
        # Phase 8F QA: ensure the Study Summary stays in sync with the
        # current workbook state — covers reload, post-batch reload, and
        # any other reload_dataset() caller.
        self._hydrate_study_summary()

    # Phase 8E: compute StudySummary from the current workbook state and
    # emit it so the Dashboard Study Summary panel hydrates immediately.
    def _hydrate_study_summary(self) -> None:
        """Recompute the analytics summary from the workbook's current state.

        Called after ``reload_dataset()`` on project load and after every
        batch run.  Never fatal — if analytics fails, the panel stays empty.
        Falls back to the persisted JSON summary when the workbook has no
        completed rows (Phase 8E).
        """
        if self.excel is None:
            return
        try:
            all_rows = [e.row for e in self.excel.read_experiments()]
            self.study_summary = analyze_study(
                self.excel, all_rows, template=self.context.template)
            # If the workbook has no completed rows, try loading the last
            # persisted summary from disk (Phase 8E).  The fallback fires
            # only when the workbook produced zero analytics — never when
            # it produced partial/stale data that might overwrite the
            # fresh workbook-derived summary.
            if (self.cfg is not None
                    and self.study_summary.total_cases == 0
                    and self.study_summary.successful_cases == 0):
                persisted = StudySummary.load_json(
                    self.cfg.work_dir() / "last_study_summary.json")
                if persisted is not None:
                    self.study_summary = persisted
        except Exception:
            log.debug("Study summary hydration failed — non-fatal",
                      exc_info=True)
            self.study_summary = None
        self.studySummaryReady.emit(self.study_summary)

    # -- live updates driven by engine events (no workbook reads) -------- #
    def apply_event(self, evt: Event) -> None:
        """Keep the cached dataset current while a batch runs."""
        d = evt.data
        if evt.type == "case.started":
            self._set(d["row"], Status="RUNNING", Error="")
        elif evt.type == "case.done":
            r = d.get("result", {})
            metrics = d.get("metrics", {})
            # Phase 8F QA: use template-declared columns generically.
            # Build a column→value map from the generic metrics dict,
            # keyed by display header (matching the DataFrame columns).
            values: Dict[str, object] = {
                "Status": "DONE",
                "Iterations": r.get("iterations"),
                "Converged": "YES" if r.get("converged") else "NO",
                "Error": r.get("error") or "",
                "CaseDir": r.get("artifact_dir") or "",
                "Duration_min": r.get("duration_min"),
            }
            # Map template metric names to display headers.
            for metric_name, col_header in self.context.template.output_columns():
                # Try the metrics dict first, then the result dict.
                val = metrics.get(metric_name)
                if val is None:
                    val = r.get(metric_name)
                values[col_header] = val
            self._set(d["row"], **values)
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

    def template_metrics(self) -> List[str]:
        """Display-name list of the template's output metric columns.

        Used by panels (StatsPanel, etc.) to render only the metrics
        relevant to the active template instead of hardcoded aero names.
        """
        tpl = self.context.template
        return [header for _, header in tpl.output_columns()]

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


def _case_id(exp) -> str:
    """The dataset's per-row case identifier.

    Prefers the model's own ``case_id`` (byte-identical for External
    Aerodynamics, including WBP extras). Studies that don't declare the
    legacy ``aoa``/``velocity`` slots (e.g. Internal Flow, built via the
    generic Phase-4 parameter path) can't form that airfoil-shaped id, so we
    fall back to a filesystem-safe id derived from the study's *own*
    parameters — metadata-driven, never a template branch.
    """
    try:
        return exp.case_id
    except KeyError:
        params = exp.parameters_dict()
        base = f"r{exp.row:03d}_" + "_".join(
            f"{name}{val:g}" for name, val in sorted(params.items()))
        return re.sub(r"[^A-Za-z0-9._\-]+", "-", base)
