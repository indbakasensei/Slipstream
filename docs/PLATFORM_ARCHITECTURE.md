# Slipstream — Universal CFD Platform Architecture

**Status: v2.0.0-dev, Phase 3A (template-driven study definition).** This
document describes an architectural direction, the metadata layer that
seeds it (Phase 1), the runtime's migration onto it (Phase 2), and the
introduction of template-driven study definitions and input ordering
(Phase 3A, §7). Through Phase 3A **behavior remains byte-for-byte identical
to v1.0** — every existing project, workflow, Excel file, and test is
unchanged.

---

## 1. Why this exists

Slipstream began as an *airfoil* automation tool. That history is baked
into the vocabulary of the current code: the schedule has `AOA_deg` and
`Velocity_m_s` columns, the models speak of `aoa_deg`/`velocity`, the
analytics headline "best L/D," and the linter knows about stall and Mach
limits for lifting bodies.

None of that is wrong — it is exactly the workflow the tool was built for.
But the *machinery* underneath it (Excel-driven scheduling, crash-safe
resume, mesh caching, a Workbench→Fluent pipeline, a provenance ledger,
live telemetry, post-batch analytics, packaging, validation) is completely
general. There is nothing airfoil-specific about "run a parametric sweep,
record every case, resume after a crash, compare against a reference."

The long-term vision is to make that generality explicit:

```
Today's mindset                 Target mindset
---------------                 -------------
Airfoil                         Project
   │                               │
   ▼                               ▼
Angle of Attack                 Simulation Template
   │                               │
   ▼                               ▼
Velocity                        Parameters  (AoA, RPM, pressure, …)
   │                               │
   ▼                               ▼
Run CFD                         Workbench → Fluent → Metrics
                                   │
                                   ▼
                                Analytics → Report
```

**The end state: Slipstream Core knows nothing about airfoils.** The
current wing/airfoil workflow becomes *one simulation template* —
"External Aerodynamics" — sitting alongside future templates (internal
flow, heat transfer, turbomachinery, …) that reuse the same engine
unchanged.

---

## 2. The three abstractions (Phase 1)

A new package, `cfdauto/platform/`, holds **pure metadata models** — no
GUI imports, no solver imports, no Qt, no runtime behavior. Three concepts:

### 2.1 Generic Parameters — `ParameterDefinition`

> *Why parameters became generic:* "Angle of Attack" and "Velocity" are
> not special — they are two *instances* of a general idea: a named,
> typed, bounded input variable, optionally bound to a Workbench
> parameter. RPM, inlet pressure, a flap angle, a pipe diameter are all
> the same shape of thing.

`ParameterDefinition` carries: `id`, `name`, `display_name`, `unit`,
`type`, `default_value`, `minimum`, `maximum`, `step`, `required`,
`category`, `workbench_parameter`, `description`. It also provides a pure
`validate_value()` (collect-all-problems, never raises — matching the
codebase's existing `Config.validate_static` / `validate_project_structure`
convention), so a future dynamic parameter editor and a schedule validator
can share one source of truth.

The names are deliberately domain-neutral. **`ParameterDefinition`, not
`AirfoilParameter` or `AerodynamicParameter`** — every abstraction had to
answer *"can this support ANY CFD project later?"*

### 2.2 Generic Metrics — `MetricDefinition`

> *Why metrics became generic:* CL, CD, and L/D are instances of a general
> idea: a named output quantity with a unit and a source. Torque, mass
> flow, pressure drop, and efficiency fit the exact same model.

`MetricDefinition` carries: `id`, `name`, `display_name`, `unit`,
`source`, `description`. `source` is a plain string (with `SOURCE_SOLVER_REPORT`
/ `SOURCE_DERIVED` constants for the built-ins) rather than an enum,
because future solvers will legitimately invent new sources.

### 2.3 Simulation Templates — `SimulationTemplate`

> *Why templates exist:* a template is the bundle that turns the generic
> engine into a *specific* study type — "these are my inputs, these are my
> outputs, this is my solver and its defaults, this is how I get validated
> and reported." It is the unit future users will pick from ("New study
> from template"), and the unit contributors will add to extend Slipstream
> to a new domain.

`SimulationTemplate` carries: `id`, `name`, `description`,
`supported_parameters`, `supported_metrics`, `default_solver`,
`default_boundary_conditions`, `report_type`, `validation_profile`, plus
`parameter()`/`metric()` lookups by name or id.

### 2.4 Registry — `TemplateRegistry`

A small lookup: `register()`, `get(id)`, `ids()`, `all()`. The
module-level default registry is pre-loaded with the single Phase 1
template and exposes `get_default_template()`. Adding a future template is
one `register()` call — nothing about the registry changes to support heat
transfer, turbomachinery, etc.

---

## 3. The one Phase 1 template: External Aerodynamics

`EXTERNAL_AERODYNAMICS` (in `templates.py`) *describes* today's
application, faithfully:

| Aspect | Value | Mirrors |
|---|---|---|
| Parameters | `aoa` (Workbench `P1`), `velocity` (inlet, not Workbench) | the schedule's `AOA_deg`/`Velocity_m_s` columns; `config.py` `aoa_parameter="P1"` |
| Metrics | `cl`, `cd`, `l_over_d` (derived), `lift`, `drag` | every value the GUI/analytics already show |
| Solver | `ansys-fluent` | the only backend today |
| BC defaults | `inlet_type=velocity_inlet`, `aoa_method=geometry` | `config.py` `FluentConfig` defaults |
| Report | `study-summary` | `cfdauto/study_analytics.py` |
| Validation | `benchmark-comparison` | `docs/validation/VALIDATION.md` |

This template is **descriptive, not authoritative** in Phase 1: it is
proven correct by tests and round-trips through the registry, but no code
path reads it to drive a run. "The existing application automatically uses
this template" is true *by construction* — this template is, by definition,
the current workflow — not by any new wiring.

---

## 4. Future migration path

Each phase is independently shippable and preserves behavior:

- **Phase 1 (this sprint) — Foundation.** Metadata models + registry +
  External Aerodynamics template, consumed by nothing. ✅
- **Phase 2 (this sprint) — Runtime reads the metadata.** Introduce a
  runtime `SimulationContext` (§6) and redirect the safe, duplicated
  parameter/metric *display* metadata (labels, units, editing bounds,
  defaults, legend names) to read from the template instead of literals.
  Byte-identical behavior. ✅
- **Phase 3A (this sprint) — Template-driven study definition.** Introduce
  `StudyDefinition` (§7): the template now owns the *ordered* input
  specification and spreadsheet-column metadata, and the runtime asks the
  template for input ordering instead of hardcoding "AOA first, Velocity
  second." Byte-identical behavior; no Excel generated yet. ✅
- **Phase 3B — Column mapping via the template.** Let `ExcelManager`'s
  column vocabulary and the linter's rules be *derived from* the active
  template's `StudyDefinition`/metrics instead of `config.ColumnMap`, with
  External Aerodynamics reproducing today's exact columns, and wire an
  Excel generator to `StudyDefinition.spreadsheet_columns()`.
- **Phase 4 — Second template.** Add a genuinely different template
  (e.g. internal flow: mass-flow-rate in, pressure-drop out) end-to-end,
  proving the engine is domain-agnostic. This is the first phase with a
  user-visible feature.
- **Phase 5 — Template selection + dynamic editor.** "New study from
  template," a parameter editor generated from `StudyDefinition`, and
  per-project template resolution replacing `get_default_template()`.

Guardrail for every phase: *the External Aerodynamics path must produce
byte-identical Excel rows and identical analytics to today.* The regression
suite (188 tests as of Phase 3A) is the contract that guarantees it.

---

## 5. What Phases 1–3A deliberately do **not** do

No Alpha/Beta/Mach/RPM support wired in; no DOE; no heat transfer, cars,
pipes, combustion, or multiphase templates; no plugins; no new GUI pages,
template-selection dialog, or dynamic parameter editor; no second template;
no solver, analytics, Excel-schema, or result-extraction changes; no Excel
*generated* from the new study metadata. Phases 2–3A migrated *duplicated
display and ordering metadata only* — they did not change any runtime
logic.

---

## 6. Phase 2 — runtime integration

### 6.1 `SimulationContext` (the runtime source of truth)

`cfdauto/simulation_context.py` adds a lightweight, frozen
`SimulationContext` — "which template is this study, and what are its
parameters and metrics." It resolves the template **through the registry**
(`get_default_template()`), never by hardcoding the template id at call
sites, and exposes `parameter_definitions`, `metric_definitions`,
`parameter(name_or_id)`, and `metric(name_or_id)`.

Dependency direction is preserved: `simulation_context` (runtime) →
`cfdauto.platform` (pure). The platform layer still imports nothing from
the runtime.

`gui.state.AppState` holds one (`self.context`), built in `__init__` and
refreshed on `load_project` with the project's identity. It is always the
External Aerodynamics template in Phase 2, so nothing user-visible changes.

### 6.2 Metadata migrated (duplicated literals → single source)

| Where | Was hardcoded | Now reads from |
|---|---|---|
| `ParamsPanel` row labels | `"AOA [deg]"`, `"Velocity [m/s]"` | `ParameterDefinition.display_name` + `.unit` |
| `ParamsPanel` spin bounds | `-90, 90` / `0.01, …` | `ParameterDefinition.minimum` / `.maximum` |
| `ParamsPanel` add-new defaults | `0.0` / `20.0` | `ParameterDefinition.default_value` |
| `MonitorPanel` force-plot legend | `name="CL"`, `name="CD"` | `MetricDefinition.display_name` |

To make these reads reproduce the v1.0 UI exactly, the External
Aerodynamics template's `display_name`s were reconciled to the terse labels
the app actually shows (`"AOA"`, `"Velocity"`, `"CL"`, `"CD"`), with the
verbose descriptions moved to each definition's `description` field — a
cleaner split (short label vs. explanation) that also feeds future tooltips.

### 6.3 What was deliberately **not** migrated, and why

- **Excel `ColumnMap`** (`AOA_deg`, `Velocity_m_s`, `CL`, …). These are
  *user-configurable* in `config.yaml` and are the authoritative,
  persisted schedule vocabulary. The template's `name`s (`aoa`, `velocity`)
  intentionally differ from the column headers; unifying them is Phase 3
  work (deriving columns *from* the template) and would risk changing how
  existing workbooks are read. Left authoritative.
- **`Experiment.validate()` / the physics linter thresholds.** These
  encode *runtime validation behavior*, not just display metadata.
  `ParameterDefinition.validate_value()` exists and matches the spirit of
  these checks, but wiring it in would be a behavior migration (e.g. the
  velocity `> 0` vs. `>= 0.01` boundary), reserved for a later phase.
- **Dataset column identifiers** (`state.py` `OUTPUT_COLS`, chart
  `Y_CHOICES`, queue columns). These are keys used for DataFrame lookups
  *and* display; redirecting them touches analytics and the dataset schema,
  which Phase 2 excludes.
- **The velocity editing cap (`5000`)** remains a GUI-local constant: the
  template models velocity as physically unbounded (`maximum=None`), so the
  spin box's finite cap is a UI affordance, not a domain claim.

---

## 7. Phase 3A — template-driven study definition

### 7.1 `StudyDefinition` and `StudyParameter`

`cfdauto/platform/study_definition.py` adds two pure-metadata models:

- **`StudyParameter`** binds a `ParameterDefinition` to its place in a
  study: `column_name` (spreadsheet header), `order`, `visible`,
  `editable`, `group`. It *references* the shared `ParameterDefinition`
  (name/display_name/unit/bounds/default delegate to it) — no field is
  copied, so there is one source of truth per parameter.
- **`StudyDefinition`** is the ordered tuple of `StudyParameter`s plus
  descriptive accessors: `ordered()`, `visible()`, `editable()`,
  `parameter(name|id|column)`, `column_names()`, `display_names()`, and
  `spreadsheet_columns()` (the ordered per-column metadata a future Excel
  generator will iterate — descriptive only; **nothing generates a
  workbook in Phase 3A**).

Every accessor sorts by `order`, so callers never depend on construction
order. Both models are frozen; no Qt, solver, or runtime logic.

### 7.2 Template integration

`SimulationTemplate` gains a `study_definition` field. External
Aerodynamics declares:

| Parameter | `column_name` | `order` |
|---|---|---|
| `aoa` | `AOA_deg` | 0 |
| `velocity` | `Velocity_m_s` | 1 |

The `AOA`/`Velocity` `ParameterDefinition` objects are defined once as
module constants (`_AOA`, `_VELOCITY`) and shared between the template's
`supported_parameters` and its study definition — verified by a test that
asserts `study_definition.parameter("aoa").parameter is template.parameter("aoa")`.
The `column_name`s mirror `config.ColumnMap`'s defaults.

### 7.3 Ordering assumption removed

`SimulationContext.input_columns()` returns the study's ordered input
column keys (`["AOA", "Velocity"]`), sourced from the study definition
(falling back to `supported_parameters` order for a template without one).
The two runtime sites that hardcoded that ordering now read it:

| Where | Was hardcoded | Now reads from |
|---|---|---|
| `ChartsPanel._rebuild_axes` | `["AOA", "Velocity"] + wbp` | `context.input_columns() + wbp` |
| `QueuePanel.columns()` | `["Row", "AOA", "Velocity"] + …` | `["Row"] + context.input_columns() + …` |

Both produce byte-identical output today (verified at runtime and by the
unmodified GUI smoke tests) and would order correctly for any future
template automatically.

### 7.4 What Phase 3A deliberately leaves for later

- **`config.ColumnMap` stays authoritative** for actual Excel reading/
  writing. `StudyDefinition.column_name` currently *duplicates* the
  ColumnMap defaults descriptively; unifying them (deriving the runtime
  column vocabulary from the template) is Phase 3B — doing it now would
  risk how existing workbooks are read.
- **`Experiment` and `state.py`'s dataset construction remain
  aoa/velocity-shaped.** The dataset still keys inputs by
  `display_name` and maps them to `Experiment.aoa_deg`/`velocity`;
  generalizing the `Experiment` model to arbitrary parameters is a deeper
  later phase. Phase 3A removed the *display-ordering* assumptions, not the
  model's shape.
- **No Excel is generated** from `spreadsheet_columns()` — that helper is
  the seam a Phase 3B generator will consume; `make_experiment_template.py`
  is untouched.
