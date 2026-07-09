"""``slipstream doctor`` — one-command environment diagnosis.

Checks everything that has ever broken a run in the field, in dependency
order, and prints a PASS/WARN/FAIL/SKIP table. Exit code 0 when nothing
FAILed, 1 otherwise — so it can gate CI or a pre-flight script.

Covers (each of these cost real debugging time at least once):
paths to RunWB2/Fluent (incl. the ANSYS *Student* install layout), the
Workbench project and baseline case, the Excel workbook and its headers,
stale lockfiles from crashed runs, corrupt mesh caches, orphaned Fluent
processes holding Student licence tokens, and the Python dependency stack.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .config import Config, ConfigError, load_config

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
_ICON = {PASS: "✓", WARN: "!", FAIL: "✗", SKIP: "-"}


@dataclass
class CheckResult:
    status: str
    label: str
    detail: str = ""


def _check(fn: Callable[[], Tuple[str, str]], label: str) -> CheckResult:
    try:
        status, detail = fn()
        return CheckResult(status, label, detail)
    except Exception as exc:                      # a check must never crash
        return CheckResult(FAIL, label, f"{type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def _py_stack() -> Tuple[str, str]:
    import openpyxl
    import pandas
    import yaml  # noqa: F401
    bits = [f"python {sys.version.split()[0]}",
            f"pandas {pandas.__version__}",
            f"openpyxl {openpyxl.__version__}"]
    try:
        import ansys.fluent.core as pf
        bits.append(f"pyfluent {pf.__version__}")
    except ImportError:
        return WARN, ", ".join(bits) + " — ansys-fluent-core NOT installed"
    return PASS, ", ".join(bits)


def _gui_stack() -> Tuple[str, str]:
    try:
        import PySide6
        import pyqtgraph
        return PASS, (f"PySide6 {PySide6.__version__}, "
                      f"pyqtgraph {pyqtgraph.__version__}")
    except ImportError as exc:
        return WARN, f"GUI extras missing ({exc.name}) — CLI still works"


def _path_exists(p: Path, kind: str) -> Tuple[str, str]:
    return (PASS, str(p)) if p.exists() else (FAIL, f"{kind} not found: {p}")


def _fluent_exe(cfg: Config) -> Tuple[str, str]:
    if os.name != "nt":
        return SKIP, "Fluent executable check is Windows-only"
    root = Path(cfg.ansys.awp_root)
    exe = root / "fluent" / "ntbin" / "win64" / "fluent.exe"
    return _path_exists(exe, "fluent.exe")


def _excel_check(cfg: Config) -> Tuple[str, str]:
    from .excel_manager import ExcelManager
    mgr = ExcelManager(cfg.excel)
    exps = mgr.read_experiments()
    wbp = mgr.wbp_names()
    detail = (f"{len(exps)} rows, sheet '{cfg.excel.sheet}'"
              + (f", WBP columns: {', '.join(wbp)}" if wbp else ""))
    return (PASS, detail) if exps else (WARN, detail + " — schedule is empty")


def _lock_check(cfg: Config) -> Tuple[str, str]:
    lock = cfg.work_dir() / "cfdauto.lock"
    if not lock.exists():
        return PASS, "no lockfile"
    pid = lock.read_text(encoding="utf-8").strip()
    if _pid_alive(pid):
        return FAIL, (f"lock held by LIVE pid {pid} — a batch is running "
                      "(or kill that process first)")
    return WARN, (f"stale lock from dead pid {pid} — will be reclaimed "
                  "automatically on the next run")


def _version_consistency(cfg: Config) -> Tuple[str, str]:
    """ansys.version ('261') must agree with fluent.product_version ('26.1.0')
    or PyFluent will look up the wrong AWP_ROOT<ver> env var at launch."""
    v = cfg.ansys.version.strip()
    pv = (cfg.fluent.product_version or "").strip()
    if not pv:
        return WARN, (f"fluent.product_version is empty — PyFluent will guess. "
                      f"Set it to match ansys.version={v!r} (e.g. '26.1.0').")
    # Extract the first two digits from product_version ('26.1.0' → '261')
    digits = "".join(c for c in pv if c.isdigit())
    canon = digits[:3] if len(digits) >= 3 else digits
    if canon != v:
        return FAIL, (f"ansys.version={v!r} but fluent.product_version={pv!r} "
                      f"(implies v{canon}). Fluent will try AWP_ROOT{canon} "
                      f"instead of AWP_ROOT{v} and fail to launch.")
    return PASS, f"ansys v{v}  ⇄  fluent {pv}  (consistent)"


def _awp_env_check(cfg: Config) -> Tuple[str, str]:
    """The AWP_ROOT<version> environment variable PyFluent will look up."""
    v = cfg.ansys.version.strip()
    key = f"AWP_ROOT{v}"
    val = os.environ.get(key)
    if val:
        p = Path(val)
        if p.exists():
            return PASS, f"{key}={val}"
        return WARN, f"{key}={val}  (path does not exist)"
    # PyFluent falls back to cfg.ansys.awp_root here, so a missing env var
    # is only a problem when the config's awp_root is empty too.
    if not cfg.ansys.awp_root:
        return FAIL, (f"{key} not set AND ansys.awp_root is empty — Fluent "
                      "will not know where ANSYS lives.")
    return WARN, (f"{key} not set; PyFluent will use ansys.awp_root="
                  f"{cfg.ansys.awp_root} as fallback.")


def _pid_alive(pid: str) -> bool:
    try:
        p = int(pid)
    except (TypeError, ValueError):
        return False
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {p}"],
                             capture_output=True, text=True, timeout=10)
        return str(p) in out.stdout
    try:
        os.kill(p, 0)
        return True
    except OSError:
        return False


def _mesh_cache_check(cfg: Config) -> Tuple[str, str]:
    path = cfg.work_dir() / "mesh_cache.json"
    if not path.exists():
        return PASS, "no cache yet"
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return WARN, "cache file empty — will be rebuilt (harmless)"
    data = json.loads(text)
    live = sum(1 for v in data.values() if Path(v).exists())
    return PASS, f"{len(data)} entries, {live} mesh files present"


def _orphan_fluent() -> Tuple[str, str]:
    """Orphaned Fluent processes hold the Student licence token hostage."""
    names: List[str] = []
    try:
        import psutil  # optional dependency
        for proc in psutil.process_iter(["name"]):
            n = (proc.info["name"] or "").lower()
            if "fluent" in n or "fl_mpi" in n:
                names.append(f"{proc.info['name']}({proc.pid})")
    except ImportError:
        if os.name != "nt":
            return SKIP, "process scan needs psutil or Windows"
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             timeout=15)
        names = [ln.split()[0] for ln in out.stdout.splitlines()
                 if "fluent" in ln.lower() or "fl_mpi" in ln.lower()]
    if names:
        return WARN, ("orphaned Fluent processes: " + ", ".join(names[:6])
                      + " — kill them and wait ~5 min for licence tokens")
    return PASS, "no orphaned Fluent processes"


def _linter_check(cfg: Config) -> Tuple[str, str]:
    from . import linter
    from .excel_manager import ExcelManager
    exps = ExcelManager(cfg.excel).read_experiments()
    findings = linter.lint(cfg, exps)
    warns = sum(1 for f in findings if f.level == "WARN")
    if not findings:
        return PASS, "no findings"
    detail = "; ".join(f.code for f in findings)
    return (WARN if warns else PASS), f"{len(findings)} finding(s): {detail}"


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_doctor(config_path: str, printer=print) -> int:
    printer("Slipstream doctor — environment diagnosis")
    printer("=" * 62)

    results: List[CheckResult] = []
    cfg: Optional[Config] = None

    def add(fn, label):
        results.append(_check(fn, label))

    # Config first — everything else depends on it.
    try:
        cfg = load_config(Path(config_path))
        results.append(CheckResult(PASS, "config", str(config_path)))
    except (ConfigError, OSError, Exception) as exc:  # noqa: BLE001
        results.append(CheckResult(FAIL, "config", str(exc)))

    add(_py_stack, "python stack")
    add(_gui_stack, "gui stack")

    if cfg is not None:
        mock = cfg.runtime.mock
        if mock:
            results.append(CheckResult(SKIP, "ansys paths",
                                       "mock mode — ANSYS not required"))
        else:
            add(lambda: _version_consistency(cfg), "ansys version pairing")
            add(lambda: _path_exists(Path(cfg.ansys.awp_root), "AWP root"),
                "ansys awp_root")
            add(lambda: _awp_env_check(cfg), "AWP_ROOT env var")
            add(lambda: _path_exists(Path(cfg.ansys.resolve_runwb2()),
                                     "RunWB2.exe"), "ansys runwb2")
            add(lambda: _fluent_exe(cfg), "fluent executable")
            if cfg.fluent.aoa_method == "geometry":
                add(lambda: _path_exists(cfg.workbench.project_path(),
                                         "project"), "workbench project")
            add(lambda: _path_exists(cfg.fluent.baseline_case_path(),
                                     "baseline case"), "fluent baseline case")
        add(lambda: _excel_check(cfg), "excel schedule")
        add(lambda: (PASS, str(cfg.work_dir().resolve()))
            if os.access(cfg.work_dir().parent, os.W_OK)
            else (FAIL, "work_dir parent not writable"), "work_dir writable")
        add(lambda: _lock_check(cfg), "run lock")
        add(lambda: _mesh_cache_check(cfg), "mesh cache")
        add(lambda: _linter_check(cfg), "physics linter")
    add(_orphan_fluent, "fluent processes")

    # -- print table -------------------------------------------------------
    width = max(len(r.label) for r in results) + 2
    for r in results:
        printer(f" [{r.status}] {_ICON[r.status]} {r.label.ljust(width)}"
                f"{r.detail}")
    fails = sum(1 for r in results if r.status == FAIL)
    warns = sum(1 for r in results if r.status == WARN)
    printer("=" * 62)
    printer(f"{len(results)} checks: "
            f"{sum(1 for r in results if r.status == PASS)} pass, "
            f"{warns} warn, {fails} fail")
    if fails:
        printer("Fix the FAIL items before running a real batch.")
    return 1 if fails else 0
