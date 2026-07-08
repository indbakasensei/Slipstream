"""Data models shared across the framework.

Two objects travel through the pipeline:

* :class:`Experiment` — one row of the Excel schedule (the *inputs*).
* :class:`CaseResult` — everything the solver produced for that row (the *outputs*).

Keeping these as frozen-ish dataclasses (rather than passing dicts around) gives
us type safety, IDE support, and one obvious place to add new design variables
later (e.g. sideslip angle, Reynolds number, flap deflection).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional


# Status vocabulary written into the Excel "Status" column.
STATUS_PENDING = "PENDING"    # also: empty cell
STATUS_RUNNING = "RUNNING"    # set just before a case starts (crash marker)
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_SKIP = "SKIP"          # user can type this to exclude a row


@dataclass
class Experiment:
    """One row of the experiment schedule.

    Attributes
    ----------
    row:
        1-based Excel row number (used to write results back to the same row).
    aoa_deg:
        Angle of attack in degrees.
    velocity:
        Freestream / inlet velocity magnitude in m/s.
    status:
        Current value of the Status column ("" == pending).
    extra_wb_params:
        Any additional Workbench parameters coming from Excel columns named
        ``WBP:<ParameterName>`` (e.g. ``WBP:P3`` or ``WBP:FlapAngle``).  This is
        the extension point for future geometry variables — no code change
        needed, just add a column.
    """

    row: int
    aoa_deg: float
    velocity: float
    status: str = ""
    extra_wb_params: Dict[str, float] = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        """Filesystem-safe unique identifier, e.g. ``r05_aoa8.0_v30.0``."""
        base = f"r{self.row:03d}_aoa{self.aoa_deg:g}_v{self.velocity:g}"
        if self.extra_wb_params:
            extra = "_".join(f"{k}{v:g}" for k, v in sorted(self.extra_wb_params.items()))
            base += "_" + extra
        return re.sub(r"[^A-Za-z0-9._\-]+", "-", base)

    @property
    def geometry_key(self) -> str:
        """Key identifying a unique *geometry/mesh* configuration.

        Rows that share this key can reuse the same mesh (e.g. same AOA at
        several velocities), which avoids pointless Workbench re-meshing.
        """
        parts = [f"aoa={self.aoa_deg:.6f}"]
        parts += [f"{k}={v:.6f}" for k, v in sorted(self.extra_wb_params.items())]
        return "|".join(parts)

    def validate(self) -> None:
        if not math.isfinite(self.aoa_deg):
            raise ValueError(f"Row {self.row}: AOA is not a finite number")
        if not math.isfinite(self.velocity) or self.velocity <= 0:
            raise ValueError(f"Row {self.row}: velocity must be a positive number")


@dataclass
class CaseResult:
    """Everything extracted from one converged (or failed) Fluent run."""

    cl: Optional[float] = None
    cd: Optional[float] = None
    lift_n: Optional[float] = None
    drag_n: Optional[float] = None
    iterations: int = 0
    converged: bool = False
    error: str = ""
    started: Optional[datetime] = None
    finished: Optional[datetime] = None
    mesh_file: str = ""
    artifact_dir: str = ""

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
        d = asdict(self)
        d["cl_over_cd"] = self.cl_over_cd
        d["fl_over_fd"] = self.fl_over_fd
        d["duration_min"] = self.duration_min
        for key in ("started", "finished"):
            if d[key] is not None:
                d[key] = d[key].isoformat(timespec="seconds")
        return d
