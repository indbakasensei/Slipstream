"""Physics linter — pre-flight sanity checks on a study before it runs.

Every rule here exists because it burned real compute time at least once:

* AOA beyond ~±12–14° → steady RANS stalls (CL/CD freeze for 1500 iterations
  while the physics is unresolved vortex shedding).
* V > ~102 m/s at sea level → Mach 0.3, the edge of incompressible validity.
* reference area/length left at the 1.0 defaults → CL/CD normalised wrong.
* processor_count above the Student edition's 4-core cap → licence refusal.
* Internal Flow: pipe diameter/reynolds/f friction-factor sanity.

The linter never blocks a run (engineers overrule tools); it prints loudly in
``--dry-run``, logs warnings at batch start, and the GUI shows the same
findings in the Log panel. Rules are deliberately cheap — no ANSYS calls.

Phase 8F revision R5: ``lint()`` uses a **generic rule registry** instead of
template-id branching.  Templates register lint rule callables via
``register_lint_rules(template_id, fn)``.  The ``lint()`` function executes
registered rules for the active template plus universal rules (student-core-cap).
No hardcoded template-id checks inside the rule dispatch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List

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


# --------------------------------------------------------------------------- #
# Generic lint rule registry (Phase 8F revision R5).
# --------------------------------------------------------------------------- #
# Instead of hardcoding template-id checks, templates register their lint
# rules via ``register_lint_rules(template_id, fn)``.  ``lint()`` executes
# the registered callable for the active template.
LintRuleFn = callable  # (Config, List[Experiment], template?) -> List[Finding]
_RULE_REGISTRY: Dict[str, LintRuleFn] = {}


def register_lint_rules(template_id: str, rule_fn: LintRuleFn) -> None:
    """Register a lint rule function for a template.

    ``rule_fn`` receives ``(cfg, pending_experiments, template)`` and
    returns a list of :class:`Finding`.  Called once per ``lint()`` when
    the active template matches ``template_id``.
    """
    _RULE_REGISTRY[template_id] = rule_fn


def lint(cfg: Config, experiments: List[Experiment],
         template=None) -> List[Finding]:
    """Run all rules; returns aggregated findings (possibly empty).

    Parameters
    ----------
    template:
        Optional :class:`SimulationTemplate`.  When provided the linter
        looks up the registered rule function for its ``id``.  When
        ``None`` the legacy External Aerodynamics rules are applied
        (backward-compatible default).
    """
    findings: List[Finding] = []
    pending = [e for e in experiments
               if (e.status or "").upper() not in ("DONE", "SKIP")]
    if not pending:
        return findings

    tpl_id = getattr(template, "id", None) if template is not None else None

    # Phase 8F R5: generic rule registry dispatch (no template-id branching).
    # If a rule function is registered for this template_id, execute it.
    if tpl_id is not None and tpl_id in _RULE_REGISTRY:
        findings.extend(_RULE_REGISTRY[tpl_id](cfg, pending, template))
    elif tpl_id is None:
        # Backward-compatible default: legacy External Aerodynamics rules
        # when no template is provided.
        findings.extend(_lint_aero(cfg, pending))

    # -- Rules that apply to every template -------------------------------- #
    if ("student" in cfg.ansys.awp_root.lower()
            and cfg.fluent.processor_count > 4):
        findings.append(Finding(
            "WARN", "student-core-cap",
            f"processor_count={cfg.fluent.processor_count} but ANSYS Student "
            "is capped at 4 cores — Fluent will refuse to launch."))

    return findings


def _lint_aero(cfg: Config, pending: List[Experiment]) -> List[Finding]:
    """External Aerodynamics lint rules."""
    findings: List[Finding] = []
    scale = getattr(cfg.workbench, "aoa_scale", 1.0)

    # Rule 1: post-stall AOA under steady RANS
    hot = [e.row for e in pending
           if abs(e.aoa_deg * scale) > _RANS_AOA_LIMIT_DEG]
    if hot:
        findings.append(Finding(
            "WARN", "rans-post-stall",
            f"|AOA| > {_RANS_AOA_LIMIT_DEG:g} deg: steady RANS cannot resolve "
            "deep-stall flow — expect frozen/oscillating CL with no physical "
            "meaning. Consider limiting the sweep to ±12 deg.",
            rows=hot))

    # Rule 2: incompressible Mach limit
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

    # Rule 3: suspicious default reference values
    ref = cfg.fluent.reference
    if ref.area == 1.0 and ref.length == 1.0:
        findings.append(Finding(
            "INFO", "default-reference",
            "reference.area and reference.length are both exactly 1.0 — if "
            "these are placeholders rather than your real planform area and "
            "chord, CL/CD are normalised wrong (forces in N stay correct)."))

    # Rule 5: sign-convention hint
    if scale == 1.0 and pending and all(e.aoa_deg <= 0 for e in pending) \
            and any(e.aoa_deg < 0 for e in pending):
        findings.append(Finding(
            "INFO", "all-negative-aoa",
            "Every pending AOA is ≤ 0. If you are entering negative values to "
            "compensate for an inverted rotation, set workbench.aoa_scale: "
            "-1.0 and use natural positive angles instead."))

    return findings


# Internal Flow lint thresholds
_PIPE_V_MIN = 0.01        # m/s — below this, flow is essentially stagnant
_PIPE_V_MAX = 50.0        # m/s — very high for liquid pipe flow
_RE_LOW = 2300            # laminar upper bound
_RE_HIGH = 4000           # fully turbulent lower bound


def _lint_internal_flow(cfg: Config, pending: List[Experiment],
                        template) -> List[Finding]:
    """Internal Flow lint rules — template-driven from parameter metadata."""
    findings: List[Finding] = []

    # Helper: extract a parameter value from the experiment (duck-typed).
    def _param_val(exp, name: str):
        pv = (exp.parameters or {}).get(name)
        return pv.value if pv is not None else None

    # Rule IF-1: inlet velocity sanity
    v_vals = [(e.row, _param_val(e, "inlet_velocity")) for e in pending]
    v_vals = [(r, v) for r, v in v_vals if v is not None]
    if v_vals:
        low_v = [r for r, v in v_vals if v < _PIPE_V_MIN]
        high_v = [r for r, v in v_vals if v > _PIPE_V_MAX]
        if low_v:
            findings.append(Finding(
                "WARN", "pipe-low-velocity",
                f"Inlet velocity < {_PIPE_V_MIN} m/s: flow may be stagnant "
                "and solver residuals won't converge meaningfully.",
                rows=low_v))
        if high_v:
            findings.append(Finding(
                "WARN", "pipe-high-velocity",
                f"Inlet velocity > {_PIPE_V_MAX} m/s: very high for liquid "
                "pipe flow — check units and compressibility.",
                rows=high_v))

    # Rule IF-2: pipe diameter sanity
    d_vals = [(e.row, _param_val(e, "pipe_diameter")) for e in pending]
    d_vals = [(r, d) for r, d in d_vals if d is not None]
    if d_vals:
        tiny = [r for r, d in d_vals if d < 0.001]
        huge = [r for r, d in d_vals if d > 10.0]
        if tiny:
            findings.append(Finding(
                "WARN", "pipe-tiny-diameter",
                "Pipe diameter < 1 mm — mesh may be too coarse to resolve "
                "the boundary layer.",
                rows=tiny))
        if huge:
            findings.append(Finding(
                "INFO", "pipe-large-diameter",
                "Pipe diameter > 10 m — verify this is intentional (industrial "
                "scale, not a unit error).",
                rows=huge))

    # Rule IF-3: Reynolds-number range hint (requires density + viscosity + D + V)
    re_rows: List[int] = []
    for e in pending:
        rho = _param_val(e, "fluid_density")
        mu = _param_val(e, "fluid_viscosity")
        d = _param_val(e, "pipe_diameter")
        v = _param_val(e, "inlet_velocity")
        if all(x is not None for x in (rho, mu, d, v)) and mu > 0:
            re = rho * v * d / mu
            if re < _RE_LOW:
                re_rows.append(e.row)
    if re_rows:
        findings.append(Finding(
            "INFO", "pipe-laminar-regime",
            f"Reynolds number < {_RE_LOW}: flow is laminar — ensure the "
            "solver setup and turbulence model (if any) are appropriate.",
            rows=re_rows))

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


# --------------------------------------------------------------------------- #
# Built-in rule registrations (Phase 8F R5) — registered at import time.
# --------------------------------------------------------------------------- #
def _aero_rules(cfg: Config, pending: List[Experiment],
                template=None) -> List[Finding]:
    """External Aerodynamics lint rules (registered for ``external-aerodynamics``)."""
    return _lint_aero(cfg, pending)


def _internal_flow_rules(cfg: Config, pending: List[Experiment],
                         template=None) -> List[Finding]:
    """Internal Flow lint rules (registered for ``internal-flow``)."""
    return _lint_internal_flow(cfg, pending, template)


# Register built-in templates' lint rules.
register_lint_rules("external-aerodynamics", _aero_rules)
register_lint_rules("internal-flow", _internal_flow_rules)
