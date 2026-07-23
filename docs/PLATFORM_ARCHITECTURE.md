# Slipstream — Universal CFD Platform Architecture

**Status: v2.0.0-dev, Phase 6 (multi-template proof — platform validated).**
This document describes an architectural direction, the metadata layer that
seeds it (Phase 1), the runtime's migration onto it (Phase 2), template-
driven study definitions and input ordering (Phase 3A, §7), template-driven
experiment generation/validation/defaults (Phase 3B, §8), the generic
`Experiment`/`CaseResult` model (Phase 4, §9), the template-driven study I/O
boundary (Phase 5, §10), and a **second, domain-different reference template
— Internal Flow — added with zero core-runtime changes (Phase 6, §11)**.
Phase 6 is the architecture's proof: two independent CFD templates coexist,
External Aerodynamics remains the default (v1.0 behavior byte-for-byte
unchanged), and adding the new domain touched no runtime code — only a data
file and one registry registration.

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
- **Phase 3B (this sprint) — Template-driven experiment engine.**
  Introduce the runtime `ExperimentDefinition` (§8) that materializes a
  `StudyDefinition` into concrete rows/validation, and drive workbook
  generation, the default sweep, queue columns, and the validation surface
  from it. Byte-identical output (verified by regenerate-and-diff). ✅
- **Phase 3C — Column vocabulary unification.** Let `ExcelManager`'s
  *reading* of a schedule (`config.ColumnMap`) be reconciled with the
  template's `StudyDefinition` column names, so a project's column
  vocabulary has one authoritative origin. (Deferred here because existing
  workbooks with custom `ColumnMap` overrides must keep reading unchanged.)
- **Phase 4 (this sprint) — Generic experiment model.** Refactor the
  runtime `Experiment`/`CaseResult` (§9) to store generic
  `ParameterValue`/`MetricValue` containers; the airfoil-named attributes
  become compatibility accessors. The runtime model no longer contains any
  engineering-specific field. Byte-identical serialization. ✅
- **Phase 5 (this sprint) — Generic study I/O layer.** Introduce `StudyIO`
  (§10): the template-driven boundary that resolves spreadsheet columns,
  builds `Experiment`s from rows, and drives dataset construction — so
  workbook import/export and the GUI dataset derive from template metadata,
  not hardcoded `AOA`/`Velocity`. Byte-identical. This **completes the core
  platform architecture**: no airfoil assumption remains between the
  spreadsheet and the runtime. ✅
- **Phase 6 (this sprint) — Multi-template proof (Internal Flow).** Add a
  second, domain-different reference template (§11) — internal pipe flow —
  purely as data, driven through the existing runtime. **No core-runtime
  changes.** Validates the whole architecture. ✅
- **Phase 7 (future) — Template selection + dynamic editor + legacy
  removal.** Per-project template resolution (replacing the single default),
  "New study from template," a parameter editor generated from
  `StudyDefinition`, a solver setup for Internal Flow, generalizing the
  remaining airfoil conveniences (`case_id`/`geometry_key`/`ColumnMap`
  output columns), and (once no caller needs them) removal of the legacy
  `aoa_deg`/`velocity`/`cl`/`cd` accessors.

Guardrail for every phase: *the External Aerodynamics path must produce
byte-identical Excel rows, result-JSON, and analytics to today.* The
regression suite (234 tests as of Phase 6) is the contract that guarantees it.

---

## 5. What Phases 1–6 deliberately do **not** do

No Alpha/Beta/Mach/RPM support wired in; no DOE; no heat transfer, cars,
combustion, or multiphase templates; no plugins; no new GUI pages,
template-selection dialog, or dynamic parameter editor; no solver
implementation or Fluent automation for Internal Flow; no per-project
template selection (External Aerodynamics is still the single default); no
analytics/result-extraction/Excel-*schema* changes; no removal of the
legacy `aoa_deg`/`velocity`/`cl`/`cd` accessors. Phase 6 *added a second
template as data* to validate the architecture — it changed no runtime code.

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

---

## 8. Phase 3B — template-driven experiment engine

### 8.1 `ExperimentDefinition` (runtime materialization)

`cfdauto/experiment_definition.py` adds `ExperimentDefinition` — the
*runtime* object that consumes a platform-level `StudyDefinition`. The
distinction is deliberate and enforced:

- **`StudyDefinition`** (platform, `cfdauto/platform/`) — pure metadata:
  "this study has these parameters, in this order, with these columns and
  example sweep values."
- **`ExperimentDefinition`** (runtime, `cfdauto/`) — *materializes* that
  metadata: concrete default rows, the spreadsheet/editable/validation
  views the runtime consumes, and value validation.

`ExperimentDefinition` **references** a `StudyDefinition` (`self.study`);
it never copies its fields (verified by a test asserting
`ed.study is ctx.study_definition`). Dependency direction stays one-way:
runtime → platform.

`gui.state.AppState` holds one (`self.experiment_definition`), built in
`__init__` and refreshed on `load_project`, alongside the
`SimulationContext`.

### 8.2 What now originates from the template

| Concern | Was hardcoded in | Now driven by |
|---|---|---|
| Schedule **input columns** | `make_experiment_template.INPUT_HEADERS` | `ExperimentDefinition.column_names()` (← StudyDefinition) |
| **Default example rows** | `EXAMPLE_AOA`/`EXAMPLE_VEL` literals | `ExperimentDefinition.default_experiment_rows()` (cartesian product of each input's `example_values`) |
| **Queue** input columns | `["Row", "AOA", "Velocity"] …` | `["Row"] + experiment_definition.input_columns() + …` |
| **Charts** input axes | `["AOA", "Velocity"] + wbp` | `experiment_definition.input_columns() + wbp` |
| **Validation** surface | (only `ParamsPanel` spin bounds, Phase 2) | `ExperimentDefinition.validate_value()/validate_row()` (← `ParameterDefinition`) |

The example sweep values (`AOA (0,4,8,12)`, `Velocity (20,30)`) moved from
the generator's module constants onto the template's `StudyParameter`s
(`example_values`). The generator now iterates
`default_experiment_rows()`; the output header names, column widths,
fonts, fills, number formats, freeze panes, and the ReadMe sheet are
unchanged.

### 8.3 Byte-compatibility (verified, not assumed)

The generated `experiments.xlsx` was dumped to a structural snapshot
(headers, every cell value, number format, font, fill, alignment, column
widths, freeze panes, both sheets) **before** the migration, then again
**after**, and the two snapshots are identical. The existing regression
tests (schedule reads back as 8 experiments, `append_experiment` lands on
row 10, mock pipeline runs) independently confirm the workbook is
unchanged in practice.

### 8.4 What Phase 3B deliberately leaves for later

- **`config.ColumnMap` remains authoritative for *reading* a schedule.**
  A user may rename columns in `config.yaml`; the template's
  `column_name`s are the *generation* default and describe the built-in
  study, but the schedule *reader* still uses `ColumnMap`. Reconciling the
  two origins is Phase 3C — doing it now would risk existing workbooks
  with custom column names.
- **`Experiment.validate()` is not re-sourced from the template.** Its
  velocity check (`> 0`) differs from `ParameterDefinition.minimum`
  (`0.01`, a UI editing cap); `ExperimentDefinition.validate_value()`
  provides the template-driven validation surface, but wiring it into the
  run path would change that boundary and is out of scope
  ("do not change validation behaviour").
- **The `Experiment` model and dataset schema stay aoa/velocity-shaped.**
  Generalizing them to arbitrary parameters is a later phase; Phase 3B
  moved the *column and default-sweep metadata*, not the model's shape.

---

## 9. Phase 4 — generic experiment model

### 9.1 Generic value containers

`cfdauto/models.py` adds two lightweight runtime containers:

- **`ParameterValue`** — `parameter_id`, `value`, `source`
  (`schedule`/`wbp`/`derived`/`override`), `status`. One runtime input.
- **`MetricValue`** — `metric_id`, `value`, `unit`, `status`. One computed
  result.

Their `*_id`s match the corresponding `name` in the active template's
`ParameterDefinition`/`MetricDefinition`, so the runtime never needs a new
*field* to carry a new quantity (RPM, pressure, torque, …) — only a new
dict *entry*.

### 9.2 `Experiment` and `CaseResult` store generically

The spec's idealized single "Experiment {parameters, metrics}" maps onto
this codebase's existing input/output split:

| Spec concept | Lives on | Authoritative store |
|---|---|---|
| Parameters | `Experiment` | `self.parameters: Dict[str, ParameterValue]` |
| Metrics | `CaseResult` | `self.metrics: Dict[str, MetricValue]` |

`Experiment` no longer has `aoa_deg`/`velocity` fields; `CaseResult` no
longer has `cl`/`cd`/`lift_n`/`drag_n` fields. Those names are now
**compatibility accessors** (property + setter) that route to the single
dict — there is exactly one source of truth, no duplicate storage
(verified by tests asserting e.g. `"aoa_deg" not in vars(experiment)`).
Run bookkeeping on `CaseResult` (`iterations`, `converged`, `error`,
timestamps, paths) stays as plain attributes — it is not a physical metric.

### 9.3 Backward compatibility — how everything keeps working

| Legacy usage | Still works because |
|---|---|
| `Experiment(row=, aoa_deg=, velocity=, extra_wb_params=)` | `__init__` keeps the legacy signature and builds the `parameters` dict from it |
| `exp.aoa_deg`, `exp.velocity`, `exp.extra_wb_params` | compatibility properties over `parameters` |
| `exp.aoa_deg = 12.0` | property setter writes back to `parameters["aoa"]` |
| `CaseResult(cl=, cd=, …)` / `res.cl, res.cd = a, b` | `__init__` + property setters populate `metrics` |
| `res.cl`, `res.cl_over_cd`, … | accessors read from `metrics` |
| `res.to_json_dict()` | rebuilt explicitly with the **same keys in the same order** as the former `asdict(self)` |
| result-JSON `"experiment"` sub-dict | orchestrator now calls `exp.to_json_dict()` (was `vars(exp)`), producing the identical `{row, aoa_deg, velocity, status, extra_wb_params}` |

Both serialization paths were verified by capturing a real result-JSON
before the refactor and diffing the regenerated one after — **identical**.
The `Excel` writer, `Workbench`/`Fluent` controllers, the ledger, and
analytics all read/write through the accessors unchanged.

### 9.4 Generic accessors and template-driven construction

- `Experiment.parameter(name)` / `parameters_dict()`,
  `CaseResult.metric(name)` / `metrics_dict()` — the domain-neutral way to
  read values; future templates never add a property.
- `ExperimentDefinition.build_parameter_values(values)` and
  `build_experiment(row, values)` construct generic containers /
  experiments from a name→value mapping **without ever naming
  AOA/velocity** — the runtime asks the template. (Available and tested;
  the schedule *reader* in `ExcelManager` is not yet rewired onto it — see
  §9.5.)

### 9.5 Remaining airfoil assumptions (deferred)

- **`ExcelManager.read_experiments()` still constructs experiments by
  reading the `AOA_deg`/`Velocity_m_s` columns explicitly** (via
  `config.ColumnMap`) rather than iterating the study definition. Rewiring
  it onto `ExperimentDefinition.build_experiment()` is the natural next
  step but touches the authoritative schedule-reading path; deferred to
  keep this sprint's blast radius to the model itself.
- **`Experiment.validate()`, `case_id`, `geometry_key`** still reference
  `aoa`/`velocity` by name (via the accessors). They are airfoil-flavored
  conveniences; generalizing them (e.g. a template-driven `case_id`) is a
  later phase.
- **The GUI dataset** (`state.py`) still keys inputs as `"AOA"`/`"Velocity"`
  columns. Unchanged this sprint.
- **Legacy accessor removal** happens only in Phase 6, once no caller needs
  them.

### 9.6 Performance impact

Negligible. Reads/writes now go through a dict lookup + attribute access
instead of a bare attribute; construction builds a handful of small
dataclass instances per experiment/result. There is no extra storage (the
dict replaces the former fields) and no measurable change in the 213-test
suite runtime.

---

## 10. Phase 5 — generic study I/O layer

### 10.1 `StudyIO` (the spreadsheet↔runtime boundary)

`cfdauto/study_io.py` adds `StudyIO` — the layer that maps a study's
template metadata to and from its spreadsheet representation. It owns the
*mapping*; `ExcelManager` still owns the *file* (openpyxl) and delegates
per-row work to it, so exactly one place knows the template↔spreadsheet
correspondence. Roles across the stack:

| Layer | Owns | Module |
|---|---|---|
| `StudyDefinition` | input metadata | `cfdauto/platform/` |
| `ExperimentDefinition` | materialization (rows, values, validation) | `cfdauto/experiment_definition.py` |
| **`StudyIO`** | **serialization (column resolution, row↔Experiment)** | `cfdauto/study_io.py` |
| `ExcelManager` | the openpyxl workbook I/O | `cfdauto/excel_manager.py` |

`StudyIO` imports from `experiment_definition`/`platform`; nothing in the
platform layer imports it. One-way dependency preserved.

### 10.2 Column resolution — the key to backward-compatible import

The build-in study parameter *names* (`aoa`, `velocity`) are also the
attribute names on `config.ColumnMap`. So `StudyIO.input_column_header(name)`
resolves `getattr(column_map, name)` first (honouring a user's renamed
column), falling back to the template's declared `column_name`:

```
study param "aoa"  ──►  ColumnMap.aoa  ──►  "AOA_deg"   (or the user's rename)
```

This is what lets the reader *iterate the template* while a project with a
custom `ColumnMap` keeps loading unchanged — verified by a test that
renames both the sheet header and `ColumnMap` and still reads 8 rows.

### 10.3 What now flows through the template

| Concern | Was hardcoded | Now |
|---|---|---|
| Required input columns (`_map_columns`) | `(columns.aoa, columns.velocity)` | `StudyIO.input_column_headers()` |
| Reading a row (`read_experiments`) | explicit `aoa`/`velocity` cell reads + `Experiment(aoa_deg=, velocity=)` | `StudyIO.interpret_row()` → `ExperimentDefinition.build_experiment()` |
| Workbook generation | (already template-driven, Phase 3B) | `ExperimentDefinition` / `StudyIO.export_input_headers()` |
| GUI dataset input columns (`state.reload_dataset`) | `{"AOA": exp.aoa_deg, "Velocity": exp.velocity}` + hardcoded `cols` | iterate `experiment_definition.study.ordered()` → `display_name` keys, `exp.parameter(name).value` |
| Import validation surface | — | `StudyIO.validate_row()` → `ExperimentDefinition.validate_row()` |

`ExcelManager` keeps every public method and behavior; only the *input
column identity/reading* is delegated. Result writing, `save()`,
`append_experiment`, WBP discovery, recovery CSV — all unchanged.

### 10.4 Compatibility verification (empirical, not assumed)

- **Import** — captured `read_experiments()` output (row/aoa/velocity/status/
  extra/case_id) for a standard workbook, a WBP workbook, and edge rows
  (blank / half-filled / unreadable) *before* the migration; regenerated
  *after*: **identical**, including the skip rules and WBP extras.
- **ColumnMap override** — a workbook + config with renamed input columns
  reads correctly (8 rows) through the template-driven resolver.
- **GUI dataset** — the DataFrame columns and input values after
  `reload_dataset` are unchanged (`["Row","CaseID","AOA","Velocity",…]`,
  `AOA=0.0`, `Velocity=20.0`).
- **Export** — the generated workbook was already proven byte-identical in
  Phase 3B; the round-trip (generate → read back) is now covered end-to-end.
- Full suite: **224 passed** (213 prior, unmodified + 11 new).

### 10.5 Remaining template-specific assumptions

The platform is architecturally complete between the spreadsheet and the
runtime; the residual airfoil flavor is intentional and cosmetic:

- **`Experiment.validate()`, `case_id`, `geometry_key`** still name
  `aoa`/`velocity` (via the generic accessors) — airfoil-flavored
  conveniences; a template-driven `case_id`/validation is a later phase.
- **The GUI still labels input columns `AOA`/`Velocity`** — because the
  template's `display_name`s are those strings; a different template would
  yield different labels automatically.
- **`config.ColumnMap`** still enumerates the built-in inputs/outputs as
  fixed fields; a fully arbitrary column vocabulary is a future
  generalization, not required by the single External Aerodynamics template.
- **Legacy accessor removal** waits for Phase 7.

### 10.6 Performance impact

Negligible. `read_experiments` does the same number of cell reads; the
per-row work now goes through two small method calls (`interpret_row` →
`build_experiment`) instead of an inline `Experiment(...)`. No measurable
change in the 224-test suite runtime.

---

## 11. Phase 6 — multi-template proof (Internal Flow)

### 11.1 What was added

A second reference template, **Internal Flow** (`cfdauto/platform/internal_flow.py`),
for parametric internal pipe flow:

| | |
|---|---|
| Parameters | `inlet_velocity` (m/s), `fluid_density` (kg/m³), `fluid_viscosity` (Pa·s), `pipe_diameter` (m, Workbench `P1`), `pipe_length` (m, Workbench `P2`) |
| Metrics | `pressure_drop` (Pa, solver), `reynolds_number` (–, derived), `friction_factor` (–, derived) |
| Study | sweep inlet velocity × pipe diameter; fluid properties + length fixed at defaults → **8 example rows** |
| Defaults | water at ~20 °C (ρ = 998.2, μ = 1.002e-3) |
| Solver / BC | `ansys-fluent`, velocity inlet + pressure outlet |
| Validation | `moody-chart` |

It shares **nothing** with External Aerodynamics — disjoint parameters and
metrics (asserted by a test) — and is defined with the exact same platform
models (`ParameterDefinition`, `MetricDefinition`, `StudyParameter`,
`StudyDefinition`, `SimulationTemplate`).

### 11.2 Core-runtime changes required: **none**

The entire sprint's diff, outside the new template file and its tests:

| File | Change | Kind |
|---|---|---|
| `cfdauto/platform/registry.py` | one `register(INTERNAL_FLOW)` call | the registry's designed extension point |
| `cfdauto/platform/__init__.py` | export `INTERNAL_FLOW` | trivial re-export |
| `tools/make_experiment_template.py` | `build_template(path, exp_def=None)` | additive generator generalization (default unchanged) |
| `tests/test_platform.py` | one test now asserts *two* templates | required — the registry count changed by design |

Verified byte-unchanged (`git diff --quiet`): `models.py`, `study_io.py`,
`simulation_context.py`, `experiment_definition.py`, `excel_manager.py`,
`orchestrator.py`, `gui/state.py`, and every `platform/` model. The generic
runtime handled a brand-new CFD domain **untouched**.

### 11.3 Evidence of template isolation

- The default is unchanged: `get_default_template()`,
  `SimulationContext.default()`, and `ExperimentDefinition.default()` all
  still resolve to External Aerodynamics, so every existing runtime path and
  all 224 prior tests behave identically.
- Internal Flow is *inert* until requested by id
  (`registry.get("internal-flow")`); registering it changed no default and
  no behavior.
- The two templates generate independently side by side (one produces an
  `AOA_deg`/`Velocity_m_s` workbook, the other an
  `InletVelocity_m_s`/…/`PipeLength_m` workbook) with no interference.

### 11.4 How the existing runtime absorbed it (no branching)

- `SimulationContext(template=INTERNAL_FLOW)` — the frozen dataclass already
  accepts any template.
- `ExperimentDefinition.from_context(ctx)` — `column_names()`,
  `default_experiment_rows()` (cartesian product of `example_values`), and
  `build_experiment()` are template-agnostic; the 5-parameter study
  materializes with no special case.
- `StudyIO(exp_def, ColumnMap())` — `input_column_header()` resolves
  `getattr(ColumnMap, name)` and, for the Internal Flow parameters (which
  are *not* `ColumnMap` fields), **falls back to the template's
  `column_name`** — exactly the extension seam built in Phase 5. Import,
  row interpretation, and validation all work unchanged.
- `Experiment` stores the 5 generic `ParameterValue`s keyed by name;
  `exp.parameter("inlet_velocity")` reads them. The airfoil-named legacy
  accessors are simply never called on an Internal Flow experiment.

### 11.5 Platform weaknesses discovered (and their honest status)

Phase 6 confirmed the deferred couplings noted in §9.5 / §10.5 — none block
the multi-template proof, all are on the *run/results* path, out of scope
here:

- **`Experiment.case_id` / `geometry_key` / `validate()`** still name
  `aoa`/`velocity`; calling them on an Internal Flow experiment would fail.
  Not needed for generation/import/validation; needed only to *run* a
  study (Phase 7, with the Internal Flow solver setup). Generalizing them
  (template-driven `case_id`, per-parameter `validate`) is the clear next
  step.
- **Result/output columns** in the generated workbook remain the External
  Aerodynamics set (tied to `config.ColumnMap`, which enumerates fixed
  fields). Internal Flow's inputs are fully template-driven; its *output*
  columns are not — moot in Phase 6 (no solver writes them), and a
  `ColumnMap`-generalization task for later.
- **`ExcelManager` / `StudyIO.default()` resolve only the default
  template.** Reading an Internal Flow workbook through the full
  `ExcelManager` needs per-project template resolution (Phase 7); Phase 6
  drives StudyIO with the Internal Flow `ExperimentDefinition` directly,
  which is the same code path.

### 11.6 Lessons learned

- The Phase 5 `getattr(ColumnMap, name)` → `column_name` fallback was the
  single most important design decision: it is what let a template with
  entirely non-`ColumnMap` parameters flow through `StudyIO` with no change.
- Keeping the airfoil-named accessors as *thin* wrappers (Phase 4) meant a
  non-airfoil experiment is completely valid as long as those specific
  accessors aren't called — the generic store carries everything.
- The remaining airfoil coupling is now sharply localized to three
  run-path conveniences (`case_id`, `geometry_key`, `ColumnMap` outputs),
  a precise and small Phase 7 target rather than a diffuse assumption.
