"""Configuration: YAML file → validated, typed dataclasses.

Everything site-specific (paths, zone names, parameter names, solver limits)
lives in ``config/config.yaml``.  Nothing in the Python code should ever need
editing to move the framework to a new project — that is the litmus test used
when deciding whether something belongs here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .exceptions import ConfigError


# --------------------------------------------------------------------------- #
# Section dataclasses
# --------------------------------------------------------------------------- #
@dataclass
class AnsysConfig:
    version: str = "252"                 # AWP_ROOT suffix, e.g. 242 / 251 / 252
    awp_root: str = ""                   # optional explicit override
    runwb2: str = ""                     # optional explicit path to RunWB2

    def resolve_awp_root(self) -> Path:
        if self.awp_root:
            root = Path(self.awp_root)
        else:
            env = os.environ.get(f"AWP_ROOT{self.version}", "")
            if env:
                root = Path(env)
            else:
                # Auto-discover common install locations (commercial + Student).
                # Student editions use a different path from commercial installs.
                probes = [
                    Path(f"C:/Program Files/ANSYS Inc/v{self.version}"),         # commercial
                    Path(f"C:/Program Files/Ansys Inc/Ansys Student/v{self.version}"),  # Student
                    Path(f"C:/Program Files/Ansys Inc/v{self.version}"),         # sometimes cased
                ]
                root = next((p for p in probes if p.exists()), None)
                if root is None:
                    raise ConfigError(
                        f"Cannot locate ANSYS: AWP_ROOT{self.version} is not set, "
                        f"ansys.awp_root is empty, and none of the standard install "
                        f"locations exist. Checked: {[str(p) for p in probes]}. "
                        f"Set ansys.awp_root explicitly in config.yaml."
                    )
        if not root.exists():
            raise ConfigError(f"ANSYS installation folder does not exist: {root}")
        return root

    def resolve_runwb2(self) -> Path:
        if self.runwb2:
            p = Path(self.runwb2)
            if not p.exists():
                raise ConfigError(f"ansys.runwb2 points to a missing file: {p}")
            return p
        root = self.resolve_awp_root()
        candidates = [
            root / "Framework" / "bin" / "Win64" / "RunWB2.exe",   # Windows
            root / "Framework" / "bin" / "Linux64" / "runwb2",     # Linux
        ]
        for c in candidates:
            if c.exists():
                return c
        raise ConfigError(
            "Could not find the Workbench batch executable. Looked for:\n  "
            + "\n  ".join(str(c) for c in candidates)
            + "\nSet ansys.runwb2 explicitly in the config."
        )


@dataclass
class WorkbenchConfig:
    project_file: str = ""               # absolute path to the .wbpj
    system_name: str = "FFF"             # internal system name (see `wb-info`)
    aoa_parameter: str = "P1"            # WB parameter name or display text
    aoa_expression: str = "{value} [degree]"  # how the value is written into WB
    update_geometry: bool = True
    refresh_setup: bool = True           # forces the Fluent .msh transfer file
    save_project: bool = True
    mesh_file_glob: str = ""             # override auto discovery if needed
    timeout_s: int = 3600                # hard cap for one geometry+mesh update

    def project_path(self) -> Path:
        p = Path(self.project_file)
        if not self.project_file:
            raise ConfigError("workbench.project_file is empty — set the .wbpj path.")
        if not p.exists():
            raise ConfigError(f"Workbench project not found: {p}")
        return p


@dataclass
class ReferenceValues:
    density: float = 1.225               # kg/m^3
    viscosity: float = 1.7894e-05        # kg/m-s (only used for Re reporting)
    area: float = 1.0                    # m^2 (planform; 2D: chord * 1 m depth)
    length: float = 1.0                  # m   (chord — used for moments/Re)
    depth: float = 1.0                   # m   (2D cases)
    temperature: float = 288.16          # K
    pressure: float = 0.0                # Pa gauge


@dataclass
class FluentConfig:
    baseline_case: str = ""              # .cas.h5 exported once from the tuned setup
    dimension: int = 3                   # 2 or 3
    precision: str = "double"
    processor_count: int = 4
    product_version: str = ""            # e.g. "25.2.0" — empty = pyfluent default
    ui_mode: str = "no_gui"              # no_gui | hidden_gui | gui (debugging)
    inlet_zone: str = "inlet"
    inlet_type: str = "velocity_inlet"   # velocity_inlet supported natively
    wall_zones: List[str] = field(default_factory=lambda: ["wing"])
    aoa_method: str = "geometry"         # geometry | velocity_vector
    base_flow_axis: str = "+x"
    base_lift_axis: str = "+y"
    reference: ReferenceValues = field(default_factory=ReferenceValues)
    launch_timeout_s: int = 600
    capture_images: bool = False         # EXPERIMENTAL: save pressure/velocity
                                         # contour PNGs per case (version-fragile;
                                         # failures are logged, never fatal)

    def baseline_case_path(self) -> Path:
        if not self.baseline_case:
            raise ConfigError(
                "fluent.baseline_case is empty. Export your tuned setup once from "
                "Fluent (File ▸ Write ▸ Case) and point the config at that .cas.h5."
            )
        p = Path(self.baseline_case)
        if not p.exists():
            raise ConfigError(f"Baseline case file not found: {p}")
        return p


@dataclass
class SolveConfig:
    max_iterations: int = 1500
    check_interval: int = 100            # iterate in chunks of this size
    min_iterations: int = 300            # never declare convergence before this
    convergence_window: int = 50         # trailing samples examined
    cl_tolerance: float = 1e-3           # max abs spread of CL over the window
    cd_tolerance: float = 1e-4           # max abs spread of CD over the window
    initialization: str = "hybrid"       # hybrid | standard
    accept_unconverged: bool = True      # write results anyway, Converged=False
    save_case_data: bool = False         # archive .cas.h5/.dat.h5 per case (big!)
    crosscheck_tolerance: float = 0.03   # CL↔Lift consistency warning threshold


@dataclass
class ColumnMap:
    aoa: str = "AOA_deg"
    velocity: str = "Velocity_m_s"
    status: str = "Status"
    cl: str = "CL"
    cd: str = "CD"
    cl_cd: str = "CL/CD"
    lift: str = "Lift_N"
    drag: str = "Drag_N"
    fl_fd: str = "FL/FD"
    iterations: str = "Iterations"
    converged: str = "Converged"
    error: str = "Error"
    started: str = "Started"
    finished: str = "Finished"
    duration: str = "Duration_min"
    case_dir: str = "CaseDir"

    def output_names(self) -> List[str]:
        return [self.status, self.cl, self.cd, self.cl_cd, self.lift, self.drag,
                self.fl_fd, self.iterations, self.converged, self.error,
                self.started, self.finished, self.duration, self.case_dir]


@dataclass
class ExcelConfig:
    file: str = "experiments.xlsx"
    sheet: str = "Experiments"
    header_row: int = 1
    columns: ColumnMap = field(default_factory=ColumnMap)
    save_retries: int = 10
    save_retry_wait_s: float = 6.0       # user probably has the file open — wait

    def path(self) -> Path:
        p = Path(self.file)
        if not p.exists():
            raise ConfigError(
                f"Experiment schedule not found: {p}\n"
                f"Create one with:  python main.py init-template {p}"
            )
        return p


@dataclass
class RuntimeConfig:
    work_dir: str = "runs"
    retries_per_case: int = 1            # extra attempts after the first failure
    stop_on_failure: bool = False
    reuse_mesh_per_geometry: bool = True # cache meshes across velocities
    rerun_stale_running: bool = True     # rows left RUNNING by a crash
    mock: bool = False                   # exercised by tests / --mock


@dataclass
class Config:
    ansys: AnsysConfig = field(default_factory=AnsysConfig)
    workbench: WorkbenchConfig = field(default_factory=WorkbenchConfig)
    fluent: FluentConfig = field(default_factory=FluentConfig)
    solve: SolveConfig = field(default_factory=SolveConfig)
    excel: ExcelConfig = field(default_factory=ExcelConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    # ------------------------------------------------------------------ #
    def work_dir(self) -> Path:
        p = Path(self.runtime.work_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def validate_static(self) -> List[str]:
        """Checks that need no ANSYS installation (safe in --dry-run/--mock)."""
        problems: List[str] = []
        if self.fluent.aoa_method not in ("geometry", "velocity_vector"):
            problems.append("fluent.aoa_method must be 'geometry' or 'velocity_vector'")
        if self.fluent.dimension not in (2, 3):
            problems.append("fluent.dimension must be 2 or 3")
        if self.solve.check_interval <= 0 or self.solve.max_iterations <= 0:
            problems.append("solve.check_interval and solve.max_iterations must be > 0")
        if self.solve.convergence_window < 5:
            problems.append("solve.convergence_window should be at least 5 samples")
        if not self.fluent.wall_zones:
            problems.append("fluent.wall_zones must list at least one wing wall zone")
        if "{value}" not in self.workbench.aoa_expression:
            problems.append("workbench.aoa_expression must contain the placeholder {value}")
        return problems


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #
_SECTION_TYPES = {
    "ansys": AnsysConfig,
    "workbench": WorkbenchConfig,
    "fluent": FluentConfig,
    "solve": SolveConfig,
    "excel": ExcelConfig,
    "runtime": RuntimeConfig,
}
_NESTED = {
    (FluentConfig, "reference"): ReferenceValues,
    (ExcelConfig, "columns"): ColumnMap,
}


def _build(cls, data: Dict[str, Any], path: str):
    """Instantiate a dataclass from a dict, rejecting unknown keys loudly."""
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config section '{path}' must be a mapping, got {type(data).__name__}")
    known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
    unknown = set(data) - known
    if unknown:
        raise ConfigError(
            f"Unknown key(s) in config section '{path}': {sorted(unknown)}. "
            f"Valid keys: {sorted(known)}"
        )
    kwargs = {}
    for key, value in data.items():
        nested = _NESTED.get((cls, key))
        kwargs[key] = _build(nested, value, f"{path}.{key}") if nested else value
    try:
        return cls(**kwargs)
    except TypeError as exc:  # wrong value types etc.
        raise ConfigError(f"Invalid values in config section '{path}': {exc}") from exc


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file not found: {p}")
    with open(p, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Top level of the config file must be a mapping.")

    unknown = set(raw) - set(_SECTION_TYPES)
    if unknown:
        raise ConfigError(f"Unknown top-level config section(s): {sorted(unknown)}")

    cfg = Config(**{
        name: _build(cls, raw.get(name, {}), name)
        for name, cls in _SECTION_TYPES.items()
    })

    # Environment escape hatch used by the test-suite / demos.
    if os.environ.get("CFDAUTO_MOCK", "").lower() in ("1", "true", "yes"):
        cfg.runtime.mock = True

    problems = cfg.validate_static()
    if problems:
        raise ConfigError("Config validation failed:\n  - " + "\n  - ".join(problems))
    return cfg
