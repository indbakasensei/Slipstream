"""Physics linter — pre-flight sanity checks on a study before it runs.

Every rule here exists because it burned real compute time at least once:

* AOA beyond ~±12–14° → steady RANS stalls (CL/CD freeze for 1500 iterations
  while the physics is unresolved vortex shedding).
* V > ~102 m/s at sea level → Mach 0.3, the edge of incompressible validity.
* reference area/length left at the 1.0 defaults → CL/CD normalised wrong.
* processor_count above the Student edition's 4-core cap → licence refusal.

The linter never blocks a run (engineers overrule tools); it prints loudly in
``--dry-run``, logs warnings at batch start, and the GUI shows the same
findings in the Log panel. Rules are deliberately cheap — no ANSYS calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from .config import Config
from .models import Experiment

log = logging.getLogger("cfdauto.linter")

# Speed of sound at 288.16 K sea-level standard air [m/s].
_A_SOUND = 340.3
_MACH_LIMIT = 0.3
_RANS_AOA_LIMIT_DEG = 12.0


@dataclass
class Finding:
    level: str          # "WARN" | "INFO"
    code: str           # short machine-readable id
    message: str        # human explanation, already aggregated
    rows: List[int] = field(default_factory=list)

    def __str__(self) -> str:
        rows = f"  (rows {_compact(self.rows)})" if self.rows else ""
        return f"[{self.level}] {self.code}: {self.message}{rows}"


def _compact(rows: List[int]) -> str:
    """[2,3,4,7] -> '2-4, 7' — keeps 60-row findings readable."""
    if not rows:
        return ""
    rows = sorted(set(rows))
    spans, start, prev = [], rows[0], rows[0]
    for r in rows[1:]:
        if r == prev + 1:
            prev = r
            continue
        spans.append(f"{start}-{prev}" if prev > start else f"{start}")
        start = prev = r
    spans.append(f"{start}-{prev}" if prev > start else f"{start}")
    return ", ".join(spans)


def lint(cfg: Config, experiments: List[Experiment]) -> List[Finding]:
    """Run all rules; returns aggregated findings (possibly empty)."""
    findings: List[Finding] = []
    pending = [e for e in experiments
               if (e.status or "").upper() not in ("DONE", "SKIP")]

    # -- Rule 1: post-stall AOA under steady RANS ------------------------- #
    scale = getattr(cfg.workbench, "aoa_scale", 1.0)
    hot = [e.row for e in pending
           if abs(e.aoa_deg * scale) > _RANS_AOA_LIMIT_DEG]
    if hot:
        findings.append(Finding(
            "WARN", "rans-post-stall",
            f"|AOA| > {_RANS_AOA_LIMIT_DEG:g} deg: steady RANS cannot resolve "
            "deep-stall flow — expect frozen/oscillating CL with no physical "
            "meaning. Consider limiting the sweep to ±12 deg.",
            rows=hot))

    # -- Rule 2: incompressible Mach limit -------------------------------- #
    fast = [e.row for e in pending
            if e.velocity / _A_SOUND > _MACH_LIMIT]
    if fast:
        vmax = max(e.velocity for e in pending)
        findings.append(Finding(
            "WARN", "mach-limit",
            f"V up to {vmax:g} m/s → Mach {vmax / _A_SOUND:.2f} exceeds the "
            f"~{_MACH_LIMIT} incompressible-validity limit; drag will be "
            "under-predicted. Use a compressible baseline case above "
            f"~{_MACH_LIMIT * _A_SOUND:.0f} m/s.",
            rows=fast))

    # -- Rule 3: suspicious default reference values ----------------------- #
    ref = cfg.fluent.reference
    if ref.area == 1.0 and ref.length == 1.0:
        findings.append(Finding(
            "INFO", "default-reference",
            "reference.area and reference.length are both exactly 1.0 — if "
            "these are placeholders rather than your real planform area and "
            "chord, CL/CD are normalised wrong (forces in N stay correct)."))

    # -- Rule 4: Student edition core cap ---------------------------------- #
    if ("student" in cfg.ansys.awp_root.lower()
            and cfg.fluent.processor_count > 4):
        findings.append(Finding(
            "WARN", "student-core-cap",
            f"processor_count={cfg.fluent.processor_count} but ANSYS Student "
            "is capped at 4 cores — Fluent will refuse to launch."))

    # -- Rule 5: sign-convention hint --------------------------------------#
    if scale == 1.0 and pending and all(e.aoa_deg <= 0 for e in pending) \
            and any(e.aoa_deg < 0 for e in pending):
        findings.append(Finding(
            "INFO", "all-negative-aoa",
            "Every pending AOA is ≤ 0. If you are entering negative values to "
            "compensate for an inverted rotation, set workbench.aoa_scale: "
            "-1.0 and use natural positive angles instead."))

    return findings


def report(findings: List[Finding], printer=print) -> None:
    """Pretty-print findings (used by --dry-run and `doctor`)."""
    if not findings:
        printer("Physics linter: no findings — schedule looks sane.")
        return
    printer(f"Physics linter: {len(findings)} finding(s)")
    for f in findings:
        printer(f"  {f}")


def log_findings(findings: List[Finding]) -> None:
    """Send findings to the logging system (batch start, GUI Log panel)."""
    for f in findings:
        (log.warning if f.level == "WARN" else log.info)("%s", f)
