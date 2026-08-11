"""Data models shared across the framework.

Two objects travel through the pipeline:

* :class:`Experiment` — one row of the Excel schedule (the *inputs*).
* :class:`CaseResult` — everything the solver produced for that row (the *outputs*).

Generic experiment model (Universal Platform, Phase 4)
------------------------------------------------------
Both objects now store their engineering quantities generically:

* :class:`Experiment` stores :class:`ParameterValue` objects in
  ``.parameters`` (keyed by parameter name — ``"aoa"``, ``"velocity"``,
  and any ``WBP:*`` extras). It has *no* airfoil-specific fields.
* :class:`CaseResult` stores :class:`MetricValue` objects in ``.metrics``
  (``"cl"``, ``"cd"``, ``"lift_n"``, ``"drag_n"``).

The legacy attributes (``experiment.aoa_deg``, ``experiment.velocity``,
``result.cl``, ``result.cd``, …) are preserved as **compatibility
accessors** that route to the generic stores — there is one source of
truth (the dict), never duplicate storage. Construction, iteration,
serialization, and every existing caller keep working unchanged; the
result-JSON produced is byte-identical to before. See
``docs/PLATFORM_ARCHITECTURE.md`` for the migration plan and the eventual
removal of the legacy accessors.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


# Status vocabulary written into the Excel "Status" column.
STATUS_PENDING = "PENDING"    # also: empty cell
STATUS_RUNNING = "RUNNING"    # set just before a case starts (crash marker)
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_SKIP = "SKIP"          # user can type this to exclude a row


# --------------------------------------------------------------------------- #
# Generic runtime value containers (Phase 4)
# --------------------------------------------------------------------------- #
@dataclass
class ParameterValue:
    """One runtime input value — the generic replacement for an
    airfoil-specific field like ``aoa_deg``.

    ``parameter_id`` matches the parameter's ``name`` in the active
    template (see :mod:`cfdauto.platform`); the runtime never needs a new
    field to carry a new parameter (RPM, pressure, …), only a new entry.
    """

    parameter_id: str
    value: float
    source: str = "schedule"      # schedule | wbp | derived | override
    status: str = "set"           # set | pending | invalid


# Units for the four standard result metrics — a MetricValue carries its
# own unit so display code never has to special-case which metric it is.
_METRIC_UNITS = {"cl": "", "cd": "", "lift_n": "N", "drag_n": "N"}


@dataclass
class MetricValue:
    """One computed runtime result — the generic replacement for an
    airfoil-specific output field like ``cl``.

    ``metric_id`` matches the metric's ``name`` in the active template.
    """

    metric_id: str
    value: Optional[float] = None
    unit: str = ""
    status: str = "computed"      # computed | pending | failed


# --------------------------------------------------------------------------- #
# Experiment — inputs (parameters authoritative; legacy fields are accessors)
# --------------------------------------------------------------------------- #
class Experiment:
    """One row of the experiment schedule.

    Parameters are stored generically in ``self.parameters`` (a dict of
    :class:`ParameterValue` keyed by parameter name). The ``aoa_deg`` /
    ``velocity`` / ``extra_wb_params`` attributes are compatibility
    accessors over that dict — the dict is the single source of truth.

    Construction keeps its legacy signature
    (``Experiment(row=, aoa_deg=, velocity=, status=, extra_wb_params=)``)
    so every existing caller and test is unaffected; a ``parameters=``
    keyword is also accepted for template-driven construction, and a
    ``template=`` may be attached (Phase 8A) — when present, identity,
    geometry, validation, and serialization are *derived from the template's
    declared contract* instead of the legacy airfoil shape; when absent, the
    legacy behavior is kept byte-identical.
    """

    def __init__(self, row: int, aoa_deg: Optional[float] = None,
                 velocity: Optional[float] = None, status: str = "",
                 extra_wb_params: Optional[Dict[str, float]] = None, *,
                 parameters: Optional[Dict[str, "ParameterValue"]] = None,
                 metadata: Optional[Dict[str, Any]] = None,
                 template: Optional[Any] = None) -> None:
        self.row = row
        self.status = status
        self.metadata: Dict[str, Any] = dict(metadata) if metadata else {}
        # Phase 8A: the template this experiment was built for (None keeps
        # the legacy airfoil identity/validation byte-identical).
        self.template = template
        self.parameters: Dict[str, ParameterValue] = {}
        if parameters is not None:
            for name, pv in parameters.items():
                self.parameters[name] = (pv if isinstance(pv, ParameterValue)
                                         else ParameterValue(name, float(pv)))
        else:
            if aoa_deg is not None:
                self.parameters["aoa"] = ParameterValue("aoa", float(aoa_deg))
            if velocity is not None:
                self.parameters["velocity"] = ParameterValue("velocity",
                                                             float(velocity))
            for name, value in (extra_wb_params or {}).items():
                self.parameters[name] = ParameterValue(name, float(value),
                                                       source="wbp")

    # -- legacy compatibility accessors (route to self.parameters) ------ #
    @property
    def aoa_deg(self) -> float:
        return self.parameters["aoa"].value

    @aoa_deg.setter
    def aoa_deg(self, value: float) -> None:
        self.parameters["aoa"] = ParameterValue("aoa", float(value))

    @property
    def velocity(self) -> float:
        return self.parameters["velocity"].value

    @velocity.setter
    def velocity(self, value: float) -> None:
        self.parameters["velocity"] = ParameterValue("velocity", float(value))

    @property
    def extra_wb_params(self) -> Dict[str, float]:
        """The non-standard (WBP) parameters as a plain name→value dict."""
        return {name: pv.value for name, pv in self.parameters.items()
                if name not in ("aoa", "velocity")}

    # -- generic accessors (Phase 4) ------------------------------------ #
    def parameter(self, name: str) -> Optional[ParameterValue]:
        """The :class:`ParameterValue` for ``name`` (None if absent)."""
        return self.parameters.get(name)

    def parameters_dict(self) -> Dict[str, float]:
        """All input parameters as a plain name→value dict."""
        return {name: pv.value for name, pv in self.parameters.items()}

    # -- identity / validation (Phase 8A: template-driven, legacy fallback) - #
    def _wb_extras(self, excluded: Tuple[str, ...] = ()) -> Dict[str, float]:
        """The runtime's workbench extras (``source="wbp"``) as a plain
        name→value dict, minus any names in ``excluded``. This is the
        generic "extra parameters" marker — independent of parameter names,
        so an experiment never needs an AOA/velocity field to have extras."""
        return {name: pv.value for name, pv in self.parameters.items()
                if pv.source == "wbp" and name not in excluded}

    @property
    def case_id(self) -> str:
        """Filesystem-safe unique identifier, e.g. ``r05_aoa8_v30``.

        With a template attached, derived from the template's declared
        identity parameters (+ workbench extras); without one, the legacy
        airfoil-shaped identifier is reproduced byte-identically.
        """
        if self.template is None:
            base = f"r{self.row:03d}_aoa{self.aoa_deg:g}_v{self.velocity:g}"
            if self.extra_wb_params:
                extra = "_".join(f"{k}{v:g}" for k, v in sorted(self.extra_wb_params.items()))
                base += "_" + extra
            return re.sub(r"[^A-Za-z0-9._\-]+", "-", base)

        names = self.template.identity_parameter_names()
        parts = [f"r{self.row:03d}"]
        parts += [f"{self.template.identity_label(n)}"
                  f"{self.parameters[n].value:g}" for n in names]
        parts += [f"{k}{v:g}" for k, v in sorted(self._wb_extras(names).items())]
        return re.sub(r"[^A-Za-z0-9._\-]+", "-", "_".join(parts))

    @property
    def geometry_key(self) -> str:
        """Key identifying a unique *geometry/mesh* configuration.

        Rows that share this key can reuse the same mesh (e.g. same AOA at
        several velocities), which avoids pointless Workbench re-meshing.
        With a template attached, derived from the template's declared
        geometry parameters (+ workbench extras); without one, the legacy
        AOA-based key is reproduced byte-identically.
        """
        if self.template is None:
            parts = [f"aoa={self.aoa_deg:.6f}"]
            parts += [f"{k}={v:.6f}" for k, v in sorted(self.extra_wb_params.items())]
            return "|".join(parts)

        names = self.template.geometry_parameter_names()
        parts = [f"{n}={self.parameters[n].value:.6f}" for n in names]
        parts += [f"{k}={v:.6f}" for k, v in sorted(self._wb_extras(names).items())]
        return "|".join(parts)

    def validate(self) -> None:
        """Reject invalid inputs by raising ``ValueError`` (the contract the
        orchestrator relies on). Template-driven when a template is attached
        (its declared validation policy — parameter definitions); otherwise
        the legacy airfoil checks run unchanged."""
        if self.template is None:
            if not math.isfinite(self.aoa_deg):
                raise ValueError(f"Row {self.row}: AOA is not a finite number")
            if not math.isfinite(self.velocity) or self.velocity <= 0:
                raise ValueError(f"Row {self.row}: velocity must be a positive number")
            return

        problems = self.template.experiment_validation_problems(self)
        if problems:
            raise ValueError(f"Row {self.row}: " + "; ".join(problems))

    # -- serialization -------------------------------------------------- #
    def to_json_dict(self) -> Dict[str, Any]:
        """A JSON-ready dict of this experiment.

        Template-less experiments keep the legacy shape byte-identically
        (the former ``vars(exp)`` — same keys, same order). Template-driven
        experiments serialize generically: the template id, the parameter
        values, and any metadata — no domain field is implied.
        """
        if self.template is None:
            return {
                "row": self.row,
                "aoa_deg": self.aoa_deg,
                "velocity": self.velocity,
                "status": self.status,
                "extra_wb_params": self.extra_wb_params,
            }
        return {
            "row": self.row,
            "status": self.status,
            "template": self.template.id,
            "parameters": {name: pv.value
                           for name, pv in sorted(self.parameters.items())},
            "metadata": dict(self.metadata),
        }

    def __repr__(self) -> str:
        """Self-describing, domain-free: names the template and the actual
        parameter set rather than implying AOA/velocity."""
        if self.template is None:
            return (f"Experiment(row={self.row}, aoa_deg={self.aoa_deg:g}, "
                    f"velocity={self.velocity:g}, status={self.status!r})")
        params = ", ".join(f"{name}={pv.value:g}"
                           for name, pv in sorted(self.parameters.items()))
        return (f"Experiment(row={self.row}, template={self.template.id!r}, "
                f"status={self.status!r}, parameters={{{params}}})")


# --------------------------------------------------------------------------- #
# CaseResult — outputs (metrics authoritative; legacy fields are accessors)
# --------------------------------------------------------------------------- #
class CaseResult:
    """Everything extracted from one converged (or failed) Fluent run.

    The physical result quantities (``cl``, ``cd``, ``lift_n``, ``drag_n``)
    are stored generically in ``self.metrics`` (a dict of
    :class:`MetricValue`); the same-named attributes are compatibility
    accessors over that dict. Run bookkeeping (``iterations``,
    ``converged``, ``error``, timestamps, paths) stays as plain attributes —
    it is not a physical metric.
    """

    def __init__(self, cl: Optional[float] = None, cd: Optional[float] = None,
                 lift_n: Optional[float] = None, drag_n: Optional[float] = None,
                 iterations: int = 0, converged: bool = False, error: str = "",
                 started: Optional[datetime] = None,
                 finished: Optional[datetime] = None, mesh_file: str = "",
                 artifact_dir: str = "", *,
                 metrics: Optional[Dict[str, "MetricValue"]] = None) -> None:
        self.metrics: Dict[str, MetricValue] = {}
        if metrics is not None:
            for name, mv in metrics.items():
                self.metrics[name] = (mv if isinstance(mv, MetricValue)
                                      else MetricValue(name, mv,
                                                       _METRIC_UNITS.get(name, "")))
        else:
            # setters populate self.metrics (always present, value maybe None)
            self.cl = cl
            self.cd = cd
            self.lift_n = lift_n
            self.drag_n = drag_n
        self.iterations = iterations
        self.converged = converged
        self.error = error
        self.started = started
        self.finished = finished
        self.mesh_file = mesh_file
        self.artifact_dir = artifact_dir

    # -- legacy compatibility accessors (route to self.metrics) --------- #
    def _metric_value(self, name: str) -> Optional[float]:
        mv = self.metrics.get(name)
        return mv.value if mv is not None else None

    def _set_metric(self, name: str, value: Optional[float]) -> None:
        self.metrics[name] = MetricValue(name, value, _METRIC_UNITS.get(name, ""))

    @property
    def cl(self) -> Optional[float]:
        return self._metric_value("cl")

    @cl.setter
    def cl(self, value: Optional[float]) -> None:
        self._set_metric("cl", value)

    @property
    def cd(self) -> Optional[float]:
        return self._metric_value("cd")

    @cd.setter
    def cd(self, value: Optional[float]) -> None:
        self._set_metric("cd", value)

    @property
    def lift_n(self) -> Optional[float]:
        return self._metric_value("lift_n")

    @lift_n.setter
    def lift_n(self, value: Optional[float]) -> None:
        self._set_metric("lift_n", value)

    @property
    def drag_n(self) -> Optional[float]:
        return self._metric_value("drag_n")

    @drag_n.setter
    def drag_n(self, value: Optional[float]) -> None:
        self._set_metric("drag_n", value)

    # -- generic accessors (Phase 4) ------------------------------------ #
    def metric(self, name: str) -> Optional[MetricValue]:
        """The :class:`MetricValue` for ``name`` (None if absent)."""
        return self.metrics.get(name)

    def metrics_dict(self) -> Dict[str, Optional[float]]:
        """All result metrics as a plain name→value dict."""
        return {name: mv.value for name, mv in self.metrics.items()}

    # ------------------------------------------------------------------ #
    # Derived quantities.  Note: with a single set of reference values,
    # FL/FD is mathematically identical to CL/CD — both are written out
    # because the experiment sheet asks for both.
    # ------------------------------------------------------------------ #
    @property
    def cl_over_cd(self) -> Optional[float]:
        if self.cl is None or self.cd in (None, 0):
            return None
        return self.cl / self.cd

    @property
    def fl_over_fd(self) -> Optional[float]:
        if self.lift_n is None or self.drag_n in (None, 0):
            return None
        return self.lift_n / self.drag_n

    @property
    def duration_min(self) -> Optional[float]:
        if self.started and self.finished:
            return round((self.finished - self.started).total_seconds() / 60.0, 2)
        return None

    def to_json_dict(self) -> Dict[str, Any]:
        """Byte-identical to the former ``asdict(self)`` + derived fields:
        same keys, same order."""
        d: Dict[str, Any] = {
            "cl": self.cl, "cd": self.cd,
            "lift_n": self.lift_n, "drag_n": self.drag_n,
            "iterations": self.iterations, "converged": self.converged,
            "error": self.error,
            "started": self.started, "finished": self.finished,
            "mesh_file": self.mesh_file, "artifact_dir": self.artifact_dir,
        }
        d["cl_over_cd"] = self.cl_over_cd
        d["fl_over_fd"] = self.fl_over_fd
        d["duration_min"] = self.duration_min
        for key in ("started", "finished"):
            if d[key] is not None:
                d[key] = d[key].isoformat(timespec="seconds")
        return d

    def __repr__(self) -> str:
        return (f"CaseResult(cl={self.cl}, cd={self.cd}, "
                f"iterations={self.iterations}, converged={self.converged})")
