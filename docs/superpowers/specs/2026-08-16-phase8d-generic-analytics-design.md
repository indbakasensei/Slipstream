# Phase8D Generic Analytics — Design Document

## 1. Architecture Overview

### 1.1 Core Principle

The template owns its analytics semantics via an **explicit analytics contract** — not via `MetricDefinition` annotations (which remain purely physical/output metadata). The generic analytics engine reads this contract, resolves declared metric names to workbook columns, computes generically, and returns a `StudySummary` that:

- **Preserves all legacy External Aero fields exactly** (backward compatibility)
- **Adds a generic `key_metrics` field** for future consumers

### 1.2 Component Boundaries

```
┌─────────────────────────────────────────────────────────────────────┐
│ SimulationTemplate (platform)                                       │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ supported_metrics: Dict[str, MetricDefinition]               │   │
│ │ analytics_contract: AnalyticsContract                        │   │
│ └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ study_analytics.py (generic engine)                                 │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ analyze_study(excel, rows, template=None, retries=0)         │   │
│ │ → reads template.analytics_contract                          │   │
│ │ → resolves metric names → workbook columns via StudyIO       │   │
│ │ → computes best_ratio / maximize / minimize / convergence    │   │
│ │ → returns StudySummary (legacy fields + key_metrics)         │   │
│ └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Callers (Orchestrator, GUI, tests)                                  │
│ • continue to call analyze_study(excel, rows, retries=0)           │
│ • External Aero: legacy fields populated identically               │
│ • New templates: key_metrics populated for their declared roles    │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Data Flow

```
Template declaration
      │
      ▼
analytics_contract: AnalyticsContract
 ├── best_ratio → "l_over_d" (External Aero)
 ├── maximize   → "lift" (External Aero)
 ├── minimize   → "drag" (External Aero)
 ├── convergence → ConvergencePolicy(iterations, converged)
 └── custom_roles (Phase 8D: extension point only)
      │
      ▼
analyze_study(excel, rows, template)
      │
      ▼
For each role in contract:
  1. Resolve metric_name → workbook header via StudyIO
  2. Read values from rows via ExcelManager.read_row_metrics()
  3. Apply generic computation (max/min/ratio/convergence)
      │
      ▼
StudySummary(
  # Legacy External Aero fields (always present, None for other templates)
  best_l_over_d, best_l_over_d_row,
  highest_lift_n, highest_lift_row,
  lowest_drag_n, lowest_drag_row,
  fastest_convergence_iterations, fastest_convergence_row,
  # Existing fields unchanged
  total_cases, successful_cases, failed_cases, retries, warnings...
  # NEW: generic key metrics
  key_metrics: {
    "best_ratio": KeyMetricResult(name="l_over_d", value=1.23, row=5,
                                   role="best_ratio", display_name="L/D", unit=""),
    "maximize":   KeyMetricResult(name="lift", value=45.6, row=3,
                                   role="maximize", display_name="Lift", unit="N"),
    "minimize":   KeyMetricResult(name="drag", value=12.3, row=7,
                                   role="minimize", display_name="Drag", unit="N"),
    "convergence":KeyMetricResult(name="iterations", value=150, row=2,
                                   role="convergence", display_name="Iterations", unit=""),
  },
  # custom_roles keys added when declared
)
```

---

## 2. Template Analytics Contract

### 2.1 New Types (in `cfdauto/platform/templates.py`)

```python
from dataclasses import dataclass, field
from typing import Dict, Optional

@dataclass(frozen=True)
class ConvergencePolicy:
    """How to compute 'fastest convergence' for this template.
    Iterations/converged are bookkeeping metadata, NOT template metrics.
    They live on CaseResult directly. This policy tells analytics how
    to interpret them for this template's physics.
    """
    iterations_metric: str = "iterations"  # CaseResult attribute name
    converged_metric: str = "converged"    # CaseResult attribute name
    enabled: bool = True                   # Some templates may not have convergence

@dataclass(frozen=True)
class AnalyticsContract:
    """Template-level declaration of analytical intent.
    Maps study-level analytical roles to template metric names.
    Roles are fixed enum; templates choose which to declare.
    """
    # Core metric roles (optional — declare only what makes physical sense)
    best_ratio: Optional[str] = None       # metric name for "best ratio" (e.g. l_over_d)
    maximize: Optional[str] = None         # metric name to maximize (e.g. lift)
    minimize: Optional[str] = None         # metric name to minimize (e.g. drag)

    # Convergence is separate: bookkeeping, not a physical metric
    convergence: ConvergencePolicy = ConvergencePolicy()

    # Extension point: arbitrary additional roles (Phase 8D: declared but
    # computation not yet supported by generic engine)
    custom_roles: Dict[str, str] = field(default_factory=dict)
    # e.g. {"peak_stress": "von_mises_stress", "efficiency_opt": "efficiency"}
```

### 2.2 Template Declarations

**External Aerodynamics Template** (`platform/external_aero.py`):
```python
EXTERNAL_AERO_TEMPLATE = SimulationTemplate(
    id="external-aerodynamics",
    # ... existing fields ...
    analytics_contract=AnalyticsContract(
        best_ratio="l_over_d",
        maximize="lift",
        minimize="drag",
        convergence=ConvergencePolicy(
            iterations_metric="iterations",
            converged_metric="converged",
            enabled=True
        )
    )
)
```

**Internal Flow Template** (`platform/internal_flow.py`):
```python
INTERNAL_FLOW_TEMPLATE = SimulationTemplate(
    id="internal-flow",
    # ... existing fields ...
    analytics_contract=AnalyticsContract(
        best_ratio=None,                    # No single "best ratio" metric
        maximize=None,                      # reynolds_number not maximized as engineering target
        minimize="pressure_drop",           # Primary engineering objective
        convergence=ConvergencePolicy(
            iterations_metric="iterations",
            converged_metric="converged",
            enabled=True
        ),
        custom_roles={
            "minimize_friction": "friction_factor"  # Secondary objective (declared only)
        }
    )
)
```

**Third-Template Canary** (test template):
```python
CANARY_TEMPLATE = SimulationTemplate(
    id="canary-template",
    # ... arbitrary metrics ...
    analytics_contract=AnalyticsContract(
        best_ratio="efficiency",
        maximize="heat_rate",
        minimize="vapor_fraction",
        convergence=ConvergencePolicy(enabled=False),  # No convergence bookkeeping
        custom_roles={"peak_stress": "von_mises_stress"}  # Declared only
    )
)
```

---

## 3. Metric Semantics

### 3.1 Role Definitions

| Role | Computation | Tie-breaking | Failure Handling |
|------|-------------|--------------|------------------|
| `best_ratio` | `max(value)` where value is finite | First row encountered (ascending row order) | Skip rows where metric is None/NaN/Inf |
| `maximize` | `max(value)` | First row | Skip non-finite |
| `minimize` | `min(value)` | First row | Skip non-finite |
| `convergence` | `min(iterations)` where `converged==True` | First row | Only consider converged DONE cases |
| `custom_roles[key]` | **Phase 8D: declared only — not computed** | — | — |

### 3.2 Determinism Guarantees

- Rows processed in **ascending row number order** (sorted `row_set`)
- Strict `>` / `<` comparisons (never `>=` / `<=`)
- Same input → identical `StudySummary` every run

---

## 4. Convergence / Bookkeeping Semantics

**Key principle**: `iterations` and `converged` are **not template metrics**. They are execution metadata on `CaseResult`. The analytics contract references them by `CaseResult` attribute name via `ConvergencePolicy`.

- **External Aero**: `convergence.enabled=True` → reads `res.iterations` and `res.converged` from each DONE case
- **Internal Flow**: Same policy (reuses universal bookkeeping)
- **Canary (no convergence)**: `convergence.enabled=False` → `fastest_convergence_*` fields remain `None`

**No template forces `iterations` into `supported_metrics`** — this preserves the clean separation between physical metrics and execution bookkeeping.

**Legacy behavior preserved exactly**:
- Case must be `STATUS_DONE`
- Case must have `converged == True`
- Choose minimum `iterations`
- Ties resolve to first row in ascending row order

---

## 5. `analyze_study()` API

### 5.1 Signature

```python
def analyze_study(
    excel: ExcelManager,
    rows: Iterable[int],
    template: Optional[SimulationTemplate] = None,
    retries: int = 0
) -> StudySummary:
```

### 5.2 Template Resolution Priority

1. **Explicit `template` argument** — preferred for new callers (Orchestrator)
2. **Resolve from `ExcelManager` via public StudyIO path** — `excel.study_io.exp_def.template`
   - `ExcelManager` already exposes `study_io` publicly (added in Phase 8C)
   - No private `_template()` access needed
3. **Fallback to registry default** — maintains backward compatibility for callers that don't pass template and use legacy ExcelManager without StudyIO

### 5.3 Backward Compatibility

- Existing callers: `analyze_study(excel, rows, retries=5)` — **unchanged**
- Legacy `ExcelManager` without StudyIO → falls back to default template (External Aero) → legacy fields populated exactly as before
- New callers (Orchestrator): pass `template=SimulationContext.for_config(cfg).template`

---

## 6. `StudySummary` Evolution

### 6.1 New Generic Type

```python
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass(frozen=True)
class KeyMetricResult:
    """One computed key metric with full identity."""
    name: str              # Template metric name (e.g. "l_over_d", "pressure_drop")
    value: float           # Computed value
    row: int               # Source row number
    role: str              # "best_ratio" | "maximize" | "minimize" | "convergence" | custom
    display_name: str      # Human-readable (from MetricDefinition.display_name)
    unit: str              # Unit string (from MetricDefinition.unit)
```

### 6.2 Updated `StudySummary`

```python
@dataclass
class StudySummary:
    # --- Existing fields (UNCHANGED) ---
    total_cases: int = 0
    successful_cases: int = 0
    failed_cases: int = 0

    best_l_over_d: Optional[float] = None
    best_l_over_d_row: Optional[int] = None
    highest_lift_n: Optional[float] = None
    highest_lift_row: Optional[int] = None
    lowest_drag_n: Optional[float] = None
    lowest_drag_row: Optional[int] = None
    fastest_convergence_iterations: Optional[int] = None
    fastest_convergence_row: Optional[int] = None

    retries: int = 0
    warnings: List[StudyWarning] = field(default_factory=list)

    # Reserved for future sprint
    average_l_over_d: Optional[float] = None
    average_cl: Optional[float] = None
    average_cd: Optional[float] = None
    average_iterations: Optional[float] = None

    # --- NEW: Generic key metrics (additive only) ---
    key_metrics: Dict[str, KeyMetricResult] = field(default_factory=dict)
    # Keys: "best_ratio", "maximize", "minimize", "convergence", plus custom_roles keys
```

### 6.3 Legacy Field Population (External Aero Compatibility)

| Legacy Field | Source |
|--------------|--------|
| `best_l_over_d` / `_row` | `key_metrics["best_ratio"]` if role exists and template is External Aero |
| `highest_lift_n` / `_row` | `key_metrics["maximize"]` if template is External Aero |
| `lowest_drag_n` / `_row` | `key_metrics["minimize"]` if template is External Aero |
| `fastest_convergence_*` | `key_metrics["convergence"]` if convergence enabled |

**Implementation**: After generic computation, if the resolved template is External Aero (by `template.id == "external-aerodynamics"` **only in this compatibility layer**), copy the generic results to legacy fields. This is the **only** template-ID branch in the codebase, confined to the compatibility mapping function.

---

## 7. Template Mappings

### 7.1 External Aerodynamics

| Analytics Role | Template Metric | Legacy Field |
|----------------|-----------------|--------------|
| `best_ratio` | `l_over_d` | `best_l_over_d` |
| `maximize` | `lift` | `highest_lift_n` |
| `minimize` | `drag` | `lowest_drag_n` |
| `convergence` | (bookkeeping) | `fastest_convergence_*` |
| `custom_roles` | (none) | — |

### 7.2 Internal Flow

| Analytics Role | Template Metric | Legacy Field |
|----------------|-----------------|--------------|
| `best_ratio` | (none) | `None` |
| `maximize` | (none) | `None` |
| `minimize` | `pressure_drop` | `None` |
| `convergence` | (bookkeeping) | `fastest_convergence_*` |
| `custom_roles["minimize_friction"]` | `friction_factor` | `None` (declared only) |

**No CL/CD/Lift/Drag/AOA/Velocity references anywhere.**

### 7.3 Third-Template Canary

| Analytics Role | Template Metric | Legacy Field |
|----------------|-----------------|--------------|
| `best_ratio` | `efficiency` | `None` |
| `maximize` | `heat_rate` | `None` |
| `minimize` | `vapor_fraction` | `None` |
| `convergence` | (disabled) | `None` |
| `custom_roles["peak_stress"]` | `von_mises_stress` | `None` (declared only) |

---

## 8. Error Handling

### 8.1 Invalid Analytics Contract (Fail Fast)

- Contract references metric name **not in** `template.supported_metrics`
- → **`ValueError` during template construction/validation** (fail fast)
- Validated in `AnalyticsContract.__post_init__` or `SimulationTemplate.__post_init__`

### 8.2 Missing Value in Valid Metric (Row-Level Skip)

- Metric exists in `template.supported_metrics`
- But a particular workbook row contains: blank, `None`, `NaN`, `Inf`, invalid/non-numeric value
- → **Skip that row for that metric** (current behavior preserved)

### 8.3 No Valid Rows Remain for a Role

- → Role produces no `KeyMetricResult`
- → Corresponding legacy field remains `None`
- → No exception

### 8.4 Invalid Contract (Duplicate/Conflicting Roles)

- `AnalyticsContract.__post_init__` validates:
  - `best_ratio`, `maximize`, `minimize` must be distinct metric names (if all set)
  - `custom_roles` keys must not collide with fixed role names (`best_ratio`, `maximize`, `minimize`, `convergence`)
  - All referenced metrics must exist in `supported_metrics`
- Invalid contract → **raise `ValueError` at template definition time**

### 8.5 Failed/Incomplete Cases

- Only `STATUS_DONE` cases considered for metric extrema (preserved)
- `convergence` role only considers `converged=True` cases (preserved)
- `ROW_STILL_RUNNING` / `ROW_STILL_PENDING` warnings unchanged

---

## 9. Deterministic Behavior

| Aspect | Rule |
|--------|------|
| Row iteration order | Ascending row number (sorted `row_set`) |
| Tie-breaking | First row wins (strict `>` / `<`) |
| Floating-point comparison | `math.isfinite()` filter; direct `>` / `<` |
| Missing values | Skip row for that metric (not fatal) |
| Same input → same output | Guaranteed by pure function + sorted iteration |

---

## 10. Test Matrix

The design must be validated against these test scenarios:

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | **Valid contract + valid metric values** | Result produced in `key_metrics` and legacy fields (External Aero) |
| 2 | **Valid contract + missing/blank row value** | Row skipped for that metric; other rows still considered |
| 3 | **Valid contract + all rows invalid** | Role result absent / `None`; legacy field `None`; no exception |
| 4 | **Invalid contract + unknown metric name** | `ValueError` during contract/template validation (not analysis time) |
| 5 | **Deterministic ties** | First ascending row wins (strict `>` / `<`) |
| 6 | **Failed/PENDING/RUNNING cases** | Excluded from extrema; generate appropriate warnings |
| 7 | **External Aero legacy fields** | Byte/value-compatible with previous behavior |
| 8 | **Internal Flow** | Generic metrics only (`minimize=pressure_drop`, `convergence`, `custom_roles` declared) |
| 9 | **Canary** | Arbitrary metric names with explicitly supported fixed roles (`best_ratio`, `maximize`, `minimize`, `convergence`) |
| 10 | **Static genericity audit** | `grep -r "external-aerodynamics" cfdauto/study_analytics.py` returns nothing (except compat mapping) |

---

## 11. Public API Impact

| Module | Change |
|--------|--------|
| `study_analytics.py` | `analyze_study()` gains optional `template` parameter; returns `StudySummary` with new `key_metrics` field |
| `StudySummary` | New field `key_metrics: Dict[str, KeyMetricResult]` (default empty dict) |
| `platform/templates.py` | New `AnalyticsContract`, `ConvergencePolicy`, `KeyMetricResult` types; `SimulationTemplate.analytics_contract` field |
| `platform/external_aero.py` | Declare `analytics_contract` with External Aero roles |
| `platform/internal_flow.py` | Declare `analytics_contract` with Internal Flow roles |
| `ExcelManager` | No change (already exposes `study_io` publicly) |
| `Orchestrator` | **Minimal call-site update only**: `analyze_study(excel, rows, template=ctx.template, retries=retries)` |
| `gui/widgets/study_summary_panel.py` | **No change required** — reads legacy fields; can optionally use `key_metrics` for future enhancement |

---

## 12. Firewall Boundaries

### DO NOT MODIFY (out of scope)
- `gui/` — no changes to `StudySummaryPanel` or any widget
- `ledger/` — no ledger interaction
- `orchestrator.py` — **only the single call-site update** to pass `template=`
- `platform/external_aero.py` execution logic — only the template declaration
- `config.py`, `ColumnMap` — no changes

### MODIFIED
- `cfdauto/study_analytics.py` — core implementation
- `cfdauto/platform/templates.py` — new types, `SimulationTemplate` field
- `cfdauto/platform/external_aero.py` — contract declaration
- `cfdauto/platform/internal_flow.py` — contract declaration
- `tests/test_study_analytics.py` — expanded test coverage
- **New**: `tests/test_phase8d_analytics_generic.py` — Internal Flow + canary tests

---

## 13. Static Genericity

Keep template-ID branching **OUT of generic analytics**.

The External Aero legacy compatibility mapping may use the existing legacy compatibility mechanism, but keep it isolated in a tiny compatibility function.

**Document exactly why that branch exists**:

```python
def _populate_external_aero_legacy(summary: StudySummary, template: SimulationTemplate) -> None:
    """
    Compatibility layer: External Aero callers (Orchestrator, GUI, tests) expect
    the legacy fields best_l_over_d, highest_lift_n, lowest_drag_n,
    fastest_convergence_iterations to be populated.
    
    This is the ONLY template-id branch in the analytics module.
    It exists solely for backward compatibility with existing consumers.
    """
    if template.id == "external-aerodynamics":
        # Copy from generic key_metrics to legacy fields
        ...
```

The generic computation itself must **never** inspect:
- `external-aerodynamics`
- `internal-flow`
- `aero`
- `AOA`
- `Velocity`
- `CL`
- `CD`
- `Lift`
- `Drag`

to decide how to calculate analytics.

---

## 14. Migration Strategy

1. **Add types** (`AnalyticsContract`, `ConvergencePolicy`, `KeyMetricResult`) to `platform/templates.py`
2. **Update `SimulationTemplate`** to carry `analytics_contract` (default empty contract)
3. **Declare contracts** in External Aero + Internal Flow templates
4. **Implement generic `analyze_study()`** with template parameter + `key_metrics`
5. **Add compatibility mapping** (External Aero → legacy fields) — single template-ID branch
6. **Update Orchestrator call site** to pass `template=ctx.template`
7. **Write tests** for all 10 scenarios in test matrix
8. **Run live validation**: External Aero workbook + Internal Flow workbook
9. **Full pytest suite** — zero regressions

---

## 15. Next Steps

1. ✅ Design reviewed and approved with corrections applied
2. **Invoke `writing-plans` skill** to create implementation plan
3. **Produce implementation plan**
4. **STOP** — await plan review before implementation