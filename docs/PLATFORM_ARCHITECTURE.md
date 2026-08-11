# Slipstream — Universal CFD Platform Architecture

**Status: v2.2-dev, UX Milestone 1 (Slipstream Neo UI).**
This document describes the architectural direction and every migration
phase: the metadata layer (Phase 1), the runtime's migration onto it
(Phase 2), template-driven study definitions/ordering (Phase 3A, §7),
template-driven experiment generation (Phase 3B, §8), the generic
`Experiment`/`CaseResult` model (Phase 4, §9), the study I/O boundary
(Phase 5, §10), a second domain-different template (Phase 6, §11),
template-owned execution — `ExecutionStrategy`/`ExecutionContext`/
`ExecutionResult` (Phase 7, §12), the first *second* workflow to run
end-to-end through that framework — executable Internal Flow (Capability 1,
§13) — and the desktop UI becoming a **renderer of template metadata**
(Capability 2, §14). The orchestrator delegates the per-case workflow to the
strategy the active template names, with no template branching. External
Aerodynamics execution *and its UI* are unchanged (verified via result-JSON
diff, mesh-cache behavior, the GUI smoke test, and the full regression
suite).

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
- **Phase 7 (this sprint) — Template-aware execution framework.** Move the
  per-case execution workflow out of the orchestrator into a template-owned
  `ExecutionStrategy` (§12), dispatched data-driven; introduce
  `ExecutionContext`/`ExecutionResult`. External Aerodynamics execution is
  unchanged; Internal Flow gets a plug-in stub. **No template branching in
  the runtime.** ✅
- **Phase 8 (future) — Template selection + dynamic editor + legacy
  removal.** Per-project template resolution (replacing the single default),
  "New study from template," a parameter editor generated from
  `StudyDefinition`, a real Internal Flow solver strategy, generalizing the
  remaining airfoil conveniences (`case_id`/`geometry_key`/`ColumnMap`
  output columns), and (once no caller needs them) removal of the legacy
  `aoa_deg`/`velocity`/`cl`/`cd` accessors.

Guardrail for every phase: *the External Aerodynamics path must produce
byte-identical Excel rows, result-JSON, and analytics to today.* The
regression suite (246 tests as of Phase 7) is the contract that guarantees it.

---

## 5. What Phases 1–7 deliberately do **not** do

No Alpha/Beta/Mach/RPM support wired in; no DOE; no heat transfer, cars,
combustion, or multiphase templates; no plugins; no new GUI pages,
template-selection dialog, or dynamic parameter editor; no solver
implementation or Fluent automation for Internal Flow (its execution
strategy is a stub); no distributed/remote execution; no per-project
template selection (External Aerodynamics is still the single default); no
analytics/result-extraction/Excel-*schema* changes; no removal of the
legacy `aoa_deg`/`velocity`/`cl`/`cd` accessors. Phase 7 *relocated* the
execution workflow into a template-owned strategy — it changed no execution
behavior, no solver/mesher, and no controller.

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

---

## 12. Phase 7 — template-aware execution framework

### 12.1 The final subsystem

Execution was the last place the runtime implicitly assumed the External
Aerodynamics workflow: `Orchestrator._attempt`/`_mesh_for` hardcoded
"geometry mode → Workbench mesh (cached) → Fluent solve", and the batch
loop's cascade detector hardcoded Fluent launch-failure detection and
orphaned-process cleanup. Phase 7 moves that workflow into a **template-
owned execution strategy**, leaving the orchestrator a generic loop.

New package `cfdauto/execution/`:

| Piece | Role |
|---|---|
| `ExecutionStrategy` (`strategy.py`) | the per-case workflow (`execute_case`) + two cascade hooks (`is_launch_failure`, `cleanup_after_cascade`) with benign defaults |
| `ExecutionContext` (`context.py`) | everything a strategy needs: config, template, study, experiments, paths, state, adapters, bus, excel |
| `ExecutionResult` (`result.py`) | standard batch outcome: status, completed/failed counts, duration, artifacts, logs |
| `MeshBackend` / `SolverBackend` (`adapters.py`) | the adapter seams (relocated from `orchestrator.py`) |
| `registry.py` | data-driven `strategy_id → strategy` dispatch |
| `external_aerodynamics.py` | the existing workflow, moved verbatim |
| `internal_flow.py` | a plug-in stub (no solver yet) |

Dependency direction: `orchestrator` → `execution` → (`platform`,
`models`, `state`, `excel_manager`, …); the platform layer imports none of
it; `execution` never imports `orchestrator` (the adapter protocols moved so
it doesn't need to).

### 12.2 Template ownership, no branching

`SimulationTemplate` gained one field — `execution_strategy_id` (a plain
string, so the platform stays runtime-free). External Aerodynamics declares
`"external-aerodynamics"`, Internal Flow `"internal-flow"`. The runtime
resolves the strategy through the registry:

```python
strategy = strategy_for_template(template)   # get_execution_strategy(template.execution_strategy_id)
result   = strategy.execute_case(exp, context, case_dir)
```

There is **no `if template == external_aero`** anywhere. The orchestrator
holds one resolved strategy (`self._strategy`) and calls it per case; adding
a workflow is one `register_strategy(...)` call.

### 12.3 What moved, and what stayed

**Moved into `ExternalAerodynamicsExecutionStrategy` (verbatim):**
`_attempt` → `execute_case`; `_mesh_for` (mesh cache + Workbench +
`mesh.ready`/`stage` events) → a private helper; `_last_error_was_fluent_launch`
→ `is_launch_failure`; the module-level `_cleanup_orphaned_fluent` →
`cleanup_after_cascade`.

**Stayed in the orchestrator (the generic loop):** resume/`pending`,
per-case retries, the ledger (study/batch/case/iteration), `stop_on_failure`,
the cascade *counter/threshold/break* (it now calls the strategy's hooks for
the Fluent-specific bits), result recording (`result.json`, Excel), and the
Study Analytics summary. None of this changed.

### 12.4 Backward compatibility (verified)

- A full mock batch produces 8/8 DONE, **4 meshes for 8 rows** (the mesh
  cache, now driven from the strategy, behaves identically), and a
  **byte-identical `result.json`** (top-level keys + the `experiment`
  sub-dict) versus the pre-Phase-7 reference.
- The controllers (`fluent_controller.py`, `workbench_controller.py`,
  `mocks.py`), `excel_manager.py`, `models.py`, `study_io.py`, and the GUI
  (`gui/state.py`, `gui/event_bridge.py`) are **byte-unchanged**
  (`git diff --quiet`).
- `run()` still returns its integer failure count; `ExecutionResult` is
  additive (exposed via `Orchestrator.execution_result`).
- Full regression suite: **246 passed** (234 prior, unmodified + 12 new).

### 12.5 Internal Flow strategy (plug-in proof)

`InternalFlowExecutionStrategy` is registered and dispatchable exactly like
External Aerodynamics; it inherits the base's benign cascade hooks. In
Phase 7 its `execute_case` was a `NotImplementedError` stub — enough to prove
the strategy *plugs in*. **Capability 1 (§13) makes it *run*** by filling in
that one method; nothing else in the execution package moved.

### 12.6 Remaining workflow assumptions

- The **cascade message text** still says "Fluent launch failures" in the
  orchestrator's loop (the counter/threshold is generic, the *phrasing* is
  Fluent-flavored). Cosmetic; could read from the strategy later.
- `ExecutionResult.artifacts`/`logs` carry representative paths (cases dir,
  log file), sufficient for the current single-machine run; richer
  artifact manifests are a distributed-execution concern (out of scope).
- Everything noted in §9.5 / §10.5 / §11.5 (airfoil-named `case_id`/
  `geometry_key`, `ColumnMap` output columns, per-project template
  resolution) is unchanged and remains Phase 8 work.

### 12.7 Performance impact

Negligible. Per case, one extra method hop (`_attempt` → `strategy.execute_case`)
and, per batch, one `ExecutionContext` construction and one `ExecutionResult`.
No change in the 246-test suite runtime.

---

## 13. Capability 1 — executable Internal Flow workflow

### 13.1 The goal: prove the framework, not build a solver

Phase 7 proved a second workflow could *plug in*; Capability 1 proves a
second workflow can *execute*. `InternalFlowExecutionStrategy.execute_case`
is now functional: a pipe / duct internal-flow case runs end-to-end through
the **same** execution framework as External Aerodynamics — the generic
orchestration loop, the `MeshBackend` adapter, `ExecutionContext`,
`CaseResult`, and the mesh cache — with **no core-runtime change**. The
deliverable is architectural validation, not an industrial internal-flow
setup.

### 13.2 The per-case workflow

```
Internal Flow experiment
        │
        ▼
InternalFlowExecutionStrategy.execute_case
        │   1. mesh phase  ─► context.mesh_backend.prepare_mesh (+ RunState mesh cache)
        │                      keyed on geometry only → meshed once per pipe,
        │                      reused across the inlet-velocity sweep
        │   2. solve phase ─► minimal analytical pipe flow:
        │                        Re = ρVD/μ
        │                        f  = 64/Re (laminar) | 0.3164·Re^-0.25 (Blasius)
        │                        Δp = f·(L/D)·½ρV²          (Darcy–Weisbach)
        ▼
CaseResult(metrics = {pressure_drop, reynolds_number, friction_factor})
```

The metrics are filled by iterating **`context.template.supported_metrics`**
and reading each metric's solved value + declared unit — the strategy never
hardcodes which metrics a template has. The mesh phase is identical in shape
to External Aerodynamics' (cache hit → `mesh.ready`/`stage` events → cached
path; miss → `prepare_mesh` → `store_mesh`), so a velocity sweep meshes the
pipe once. With no mesh backend the solve still runs (`mesh_file=""`) — the
analytical solve needs no mesh.

### 13.3 The solver seam is untouched

The existing `SolverBackend` (the Fluent controller) computes airfoil CL/CD
and cannot produce a pressure drop; modifying it would be a *runtime* change,
which this sprint forbids. So the minimal solve stands in for the solver
exactly as the sprint vision allows ("Fluent **or** minimal placeholder
workflow"). The `SolverBackend` protocol is unchanged and ready: a real
internal-flow Fluent adapter drops in behind it later with, again, only
`internal_flow.py` changing.

### 13.4 Superseded by Phase 8A — the identity bridge is gone

As shipped by Capability 1 (Phase 7), internal-flow rows bridged onto the
still airfoil-shaped case identity in exactly one isolated place,
`build_internal_flow_experiment` — mapping `inlet_velocity` onto the
canonical `velocity` slot, the Workbench geometry parameters
(`pipe_diameter`/`pipe_length`) onto `extra_wb_params`, fluid properties onto
`Experiment.metadata`, and pinning `aoa` to `0.0`.

**Phase 8A (§17) removed that bridge.** `Experiment.case_id` / `geometry_key`
/ `validate` are now derived from the template contract, so internal-flow
experiments are built through the generic
`ExperimentDefinition.build_experiment` path with no airfoil-shaped slots and
no fabricated `aoa`. `internal_flow_inputs` now reads straight from the
parameter store. See §17 for the generic identity contract.

### 13.5 Which seams already generalize — and which don't (yet)

Capability 1 is a sharp probe of exactly how far the platform's generality
reaches today:

- **Already generic (used unchanged):** the platform metadata + template
  registry, `StudyDefinition`/`ExperimentDefinition` (built the Internal Flow
  study's 8 example rows), `ExecutionStrategy`/`ExecutionContext`, the
  `MeshBackend` adapter + `RunState` mesh cache, and `CaseResult.metrics` /
  `metrics_dict()` (carried the internal-flow metrics with no airfoil
  contamination — `res.cl`/`res.cd` are simply `None`).
- **Still hardwired to External Aerodynamics (Phase 8):** `ExcelManager`
  builds `StudyIO.default(...)` (its required-column check expects
  `AOA_deg`/`Velocity_m_s`), `Orchestrator` resolves `get_default_template()`,
  and `CaseResult.to_json_dict()` / the Excel output columns are the four
  airfoil metrics. **These are exactly the "per-project template selection"
  items already scheduled for Phase 8** — Capability 1 did not touch them,
  and executes Internal Flow *around* them (build → strategy → `result.json`)
  rather than redesigning them.

  *(Phase 8A, §17, resolved the **Experiment identity / geometry / validation**
  part of this bullet — the generic core no longer hardwires AOA/Velocity.
  The remaining couplings are `ExcelManager`'s required-column check, the
  Orchestrator's default template, and the CaseResult/Excel output metrics,
  which belong to Phases 8C–8F.)*

### 13.6 Backward compatibility (verified)

- The full regression suite passes: **255 passed** (246 prior — one Phase 7
  stub-assertion test updated in place, since the strategy is no longer a
  stub — plus 9 new Internal Flow tests).
- External Aerodynamics is untouched: its strategy, the orchestrator, the
  adapters, the context/result objects, `models.py`, `state.py`,
  `study_io.py`, `excel_manager.py`, and the platform templates are all
  unchanged by this sprint. The only engine file Capability 1 modified is
  `cfdauto/execution/internal_flow.py` (plus a one-line export in
  `execution/__init__.py`).

### 13.7 Architecture audit (this sprint)

Nearly all of the change is **Workflow**, as intended:

| File | Classification | Change |
|---|---|---|
| `cfdauto/execution/internal_flow.py` | **Workflow** | stub → executable strategy + `internal_flow_inputs` / `solve_internal_flow` (the `build_internal_flow_experiment` bridge was removed by Phase 8A, §17) |
| `cfdauto/execution/__init__.py` | Execution | export the three workflow helpers |
| `tests/test_internal_flow_execution.py` | Test | new — physics, bridge, execution, mesh reuse, end-to-end |
| `tests/test_execution_framework.py` | Test | update the (now obsolete) stub-assertion test |
| `docs/PLATFORM_ARCHITECTURE.md`, `README.md` | Documentation | this section + the architecture tree |

No **Platform**, **Runtime**, or execution-**framework** file was modified.

### 13.8 Lessons learned

- The Phase 4 decision to make `CaseResult` store metrics generically is what
  let an internal-flow result travel through the shared model with zero
  contamination — the strategy fills the template's metrics and the airfoil
  accessors just report `None`.
- Filling metrics by iterating `template.supported_metrics` (rather than
  naming `pressure_drop` etc. in the strategy) means a third template's
  metrics would flow through the *same* strategy code shape — the pattern
  generalizes past internal flow.
- The remaining airfoil coupling is now empirically pinned to three seams
  (`ExcelManager`'s default `StudyIO`, `Orchestrator`'s default template,
  `CaseResult.to_json_dict`/Excel output columns). Executing Internal Flow
  *around* them made the Phase 8 scope concrete: it is precisely
  per-project template selection, nothing more.

---

## 14. Capability 2 — dynamic template-driven UI

### 14.1 The UI becomes a renderer of metadata

The desktop panels used to *assume* External Aerodynamics: hardcoded AOA /
Velocity spin boxes, a queue that indexed `row["AOA"]`, chart presets naming
`"AOA"`/`"Velocity"`, and overview/stats rows labelled "AOA Range". Capability
2 turns the UI into a **renderer of platform metadata**: every parameter
control, queue column, validation message, unit, tooltip, and default is
generated from the active template's `StudyDefinition` / `ParameterDefinition`.
The UI holds **no parameter names** — swap the template and the same widgets
redraw for Internal Flow (or any future template) with zero UI code.

### 14.2 The rendering pipeline

```
SimulationTemplate ─► StudyDefinition ─► StudyParameter ─► ParameterDefinition
                                                              │
                                              gui/param_render.py (the pipeline)
                                                              │
        ┌──────────────┬──────────────┬───────────────┬──────┴───────┬─────────────┐
        ▼              ▼              ▼               ▼              ▼             ▼
   label_for      make_spin      tooltip_for     range_text     decimals_for   validate_*
  "AOA [deg]"   range+default    desc·unit·      "≥ 0.01 m/s"   step→dp (≥2)   reuse pdef
                 +step+tooltip    default·range                                  limits
        │              │              │               │              │             │
        └──────────────┴──────────────┴───────────────┴──────────────┴─────────────┘
                                        │  consumed by every panel:
        ParamsPanel (form)   QueuePanel (columns+header tooltips)   ChartsPanel (X/colour selectors)
        DashboardPanel (chart axes)   StatsPanel (best-case line)   StudyOverviewTable (range rows)
```

`gui/param_render.py` is the single seam. It is pure (functions of the
metadata plus thin Qt widget factories) and therefore unit-testable without a
running window. Panels ask `AppState` for the ordered inputs
(`input_parameters()`, `primary_input()`, `secondary_input()`) and render each
through `param_render` — they never name a parameter.

### 14.3 What each objective became

| Objective | Where | How |
|---|---|---|
| Parameter forms | `ParamsPanel` | one `make_spin` per `study.ordered()` parameter; `_sel_rows`/`_add_rows` keyed by name |
| Queue columns | `QueuePanel` | columns from `input_columns()`; generic `_cell_value`; per-input header tooltips |
| Validation | `param_render.validate_row` → `ExperimentDefinition.validate_row` | reuses the ParameterDefinition limits — no second copy |
| Units | everywhere | `label_for` (form) + `tooltip_for` "Unit: …" (queue headers, spin tooltips) |
| Tooltips | `tooltip_for` | description · unit · default · range |
| Defaults | `make_spin(pdef)` | the "Add experiment" form seeds each spin from `default_value` |
| Chart selectors | `ChartsPanel`, `DashboardPanel` | X / colour / preset axes from `input_columns()` / `primary_input()` — no literal names |

### 14.4 Example — External Aerodynamics (unchanged)

`study.ordered()` = (AOA, Velocity), so the form renders exactly as before:
`AOA [deg]` (range −90…90, 2 dp, default 0.0) and `Velocity [m/s]` (≥ 0.01,
2 dp, default 20.0, the unbounded side capped at 5000 for editing). The queue
shows `Row | AOA | Velocity | Status | CL | CD | L/D | It | Conv`; the
dashboard chart is still "L/D vs AOA (by Velocity)". Pixel-for-pixel the same
UI — now produced from metadata instead of literals.

### 14.5 Example — Internal Flow (automatic)

The *same* code, given the Internal Flow template, renders a five-row form —
`Inlet Velocity [m/s]`, `Fluid Density [kg/m3]`, `Fluid Viscosity [Pa.s]`
(6 dp, because its default is 1.002e-3), `Pipe Diameter [m]` (0.001…10),
`Pipe Length [m]` — with each spin's range/default/tooltip from metadata. The
queue columns become `Row | Inlet Velocity | Fluid Density | Fluid Viscosity |
Pipe Diameter | Pipe Length | Status | …`, each header carrying its unit on
hover; the chart's X/colour selectors list the same inputs; the overview grows
a range row per input. No UI code was added for this template — only its
metadata file (§11) and strategy (§13) exist.

### 14.6 Remaining hardcoded UI assumptions

Three references to `aoa`/`velocity` survive in the GUI, all *outside* the
metadata-rendering surface and all tied to still-airfoil-bound runtime seams
(explicitly out of this sprint's "no runtime changes" scope):

- **`AppState.add_experiment`** bridges the metadata form onto
  `ExcelManager.append_experiment(aoa, velocity, extra)` — the airfoil-shaped
  *write* API. It maps the study's first two inputs positionally (no name
  hardcoded); it collapses to a pass-through when ExcelManager becomes
  template-driven (Phase 8).
- **`MonitorPanel`** shows the live case's inputs from the engine's
  `case.started` *event payload* (still `aoa`/`velocity` keys). Read
  defensively now; generalizes with the event schema (Phase 8 / runtime).
- **`DashboardPanel` subtitle** prints `fluent.aoa_method` — an aero *config*
  field, not a parameter selector.

The **output/metric** columns (CL, CD, L/D, …) remain fixed too: they mirror
what the airfoil-bound `ExcelManager.read_row_outputs` actually provides.
Generalizing metric rendering waits on the same Phase 8 runtime work; this
sprint's scope was the *input parameter* surface, which is now fully
metadata-driven.

### 14.7 Performance impact

None measurable. Rendering does a handful of extra metadata lookups at widget
build / refresh time (already O(rows × columns)); no new per-frame work, no
new I/O. The GUI smoke test's runtime is unchanged.

### 14.8 The engineering rule, now true

Adding a template requires **1 metadata file + 1 execution strategy + 0 UI
code**. Internal Flow proves it end-to-end: its form, queue, validation,
units, tooltips, defaults, and chart selectors all exist with no panel change —
only `platform/internal_flow.py` and `execution/internal_flow.py` were ever
written for it.

---

## 15. Capability 3 — project template selection & UX foundation

### 15.1 The last default assumption, removed

Through Capability 2 the *UI* was metadata-driven, but a **project** still
implicitly meant External Aerodynamics: `Orchestrator`, `ExcelManager`, and
`AppState` all called `get_default_template()` / `SimulationContext.default()`.
Capability 3 makes the project itself template-aware. One new config field —
`runtime.template` (a SimulationTemplate id; empty ⇒ the registry default, so
every pre-existing config loads unchanged) — is the single source of truth,
read through one accessor, `Config.template_id()`.

```
config.yaml (runtime.template)  ──►  Config.template_id()
                                          │
              ┌───────────────────────────┼─────────────────────────────┐
              ▼                            ▼                             ▼
 SimulationContext.for_config     ExperimentDefinition.for_config   StudyIO.for_config
       (template, metrics)            (input schema, rows)          (spreadsheet mapping)
              │                            │                             │
              ▼                            ▼                             ▼
  Orchestrator._template /        workbook generation           ExcelManager.for_config
  strategy_for_template(...)      (build_template + exp_def)     (reads project columns)
              │                                                          │
              ▼                                                          ▼
   per-project execution strategy                         AppState.context / experiment_definition
                                                          → the dynamic UI (Capability 2)
```

There is no `if template == ...` anywhere; every seam resolves the id through
the registry. `.default()` survives only where a default is genuinely correct
(a bare app before any project is open, and back-compat callers that pass no
template).

### 15.2 Per-project configuration & persistence

A project remembers its template in **two** places, each authoritative for its
layer:

- **`config/config.yaml` → `runtime.template`** — the engine's copy. Everything
  the runtime resolves (study definition, workbook schema, execution strategy,
  UI) derives from it.
- **`project.json` → `template_id`** — the desktop-layer record of the choice
  (`ProjectMetadata`), written by `create_project(...)`. Older `project.json`
  files without the field read back `""` (→ default), so they still open.

`Config.template_id()` and `ProjectMetadata.template_id` are the only new
persisted state; execution strategy, workbook schema, and study definition are
*derived* from the template, never stored separately (no drift possible).

### 15.3 New-project flow (choose template → ready to run)

```
New Project dialog ─► pick template (registry-populated combo)
        │
        ▼
create_project(root, name, template_id)      # project.json + folders
        │
        ▼
scaffold_project(root, template_id)          # cfdauto/project_scaffold.py
        │   ├─ data/experiments.xlsx   (build_template with the template's ExperimentDefinition)
        │   └─ config/config.yaml      (runtime.template + absolute paths + mock:true)
        ▼
MainWindow._load(config/config.yaml) ─► AppState restores template → study → strategy → UI
```

`project_scaffold.py` is deliberately separate from `project_manager.py`: the
latter stays free of any engine/openpyxl import (folders + metadata only),
while the former does the template-aware generation. Workbook generation is
already template-agnostic (§8), so it needed no change — only the *caller* now
passes the project's `ExperimentDefinition`.

### 15.4 Loading an existing project restores everything

`AppState.load_project` now calls `SimulationContext.for_config(cfg)` and
`ExcelManager.for_config(cfg)`: the project's template, its study, its
execution strategy (via the orchestrator), and the metadata-driven UI all
restore automatically from `runtime.template`. An External Aerodynamics project
resolves to exactly the prior objects; an Internal Flow project loads its own
columns, defaults, and strategy with no code path special-cased.

### 15.5 UX foundation (presentation only)

Infrastructure for the upcoming **Neo UI** milestone — no visual restyle, no
themes/animations/glass:

- **Design tokens** (`gui/theme.py`): added `SECTION_SPACING`,
  `CONTROL_SPACING`, and layout minimums `MIN_SIDEBAR_WIDTH`,
  `MIN_CENTER_WIDTH`, `MIN_QUEUE_WIDTH`, `MIN_PANEL_WIDTH`, `MIN_PLOT_HEIGHT`,
  `MIN_CONTROL_HEIGHT` — one source of truth for spacing/padding/minimums.
- **Monitor** (`gui/panels/monitor.py`): restructured from a cramped
  side-by-side grid into a clear hierarchy (title over details), a labelled &
  aligned "Solver Pipeline" progress block, a plot area with a minimum height,
  and the whole panel inside a `QScrollArea` so a short dock scrolls instead of
  clipping. Every widget attribute (`bar`, `pipeline`, `forces`, `_tabs`, …) and
  all `handle_event` logic are unchanged.
- **Parameters** (`gui/panels/params_panel.py`): wrapped in a scroll area — the
  dynamic form may be long (Internal Flow's five inputs + WBP columns) and must
  never clip.
- **Responsive main splitter** (`gui/main_window.py`): per-region minimum widths
  from the tokens + `setChildrenCollapsible(False)` so no region collapses to an
  unreadable sliver on a small window; the user still resizes freely above the
  floors.

Per the engineering rule, only the **presentation** layer changed here —
`AppState` and the business logic are untouched.

### 15.6 Remaining assumptions

- **Non-aero *execution* via the orchestrator** — Phase 8A (§17) removed the
  remaining airfoil assumptions from the `Experiment` identity (`case_id` /
  `geometry_key` / `validate` are now template-driven, and the Internal Flow
  bridge builder was deleted), so a non-aero study can run end-to-end through
  the generic `ExperimentDefinition → strategy` path. The still-open pieces
  are the **output side**: `ColumnMap` / `ExcelManager.read_row_outputs`
  remain the airfoil metric set, `Orchestrator` still resolves the default
  template, and `CaseResult`/Excel serialization is generic-experiment-only
  (Phases 8B–8F).
- **Output/metric columns** remain the airfoil set in `ColumnMap` /
  `ExcelManager.read_row_outputs` (a template's *inputs* are generic; its
  *outputs* are the next generalization — Phase 8B onward).
- **A fresh project defaults to `mock: true`** so it runs immediately without
  ANSYS; the user disables it once a real baseline case is configured.

### 15.7 Performance impact

None measurable. Template resolution is a single registry dict lookup at
project-load / orchestrator-construction time; the UX foundation changes are
static layout wiring. No new per-frame work, no new I/O. Full suite runtime
unchanged.

---

## 16. UX Milestone 1 — Slipstream Neo UI (presentation only)

With the platform architecturally complete (template/execution/metadata/project
aware), the remaining weakness was user experience. Neo redesigns **how**
Slipstream is presented — a modern, professional engineering interface — while
the architecture, execution, runtime, `AppState`, controllers, signals/slots,
and workflows stay **frozen**. Every public widget attribute the app and tests
depend on is preserved; only presentation changed.

The design language (tokens, palette, typography, components, layout
philosophy) lives in **[`docs/UI_DESIGN_SYSTEM.md`](UI_DESIGN_SYSTEM.md)** and
is implemented in `gui/theme.py` (one token set + one application-wide
stylesheet that restyles every Qt widget class, so no default-Qt surface
remains) plus shared components `gui/widgets/card.py` and
`gui/widgets/status_chip.py`.

Highlights:

- **Design system** — a 4-based spacing scale (4·8·12·16·24·32·48), a 6/8/12
  radius scale, a Display→Caption type scale, and a full colour-token set
  (layered surfaces + one accent + semantic status hues), all in one place.
- **Monitor** (the priority) — rebuilt into five information-first cards
  (Current Study · Pipeline · Live Metrics · Convergence · Timeline). It still
  renders entirely from engine events; `bar`, `pipeline`, `forces`,
  `residuals`, `cl_curve`, `cd_curve`, `_tabs`, `_scroll`, `handle_event`,
  `_append_iteration`, and `_reset_case` are all unchanged in behaviour.
- **Global restyle** — tables (sticky, uppercase headers, row hover), buttons
  (accent/ghost/flat variants), inputs (focus ring), tabs (underline active),
  thin scrollbars, cards/sections, menus, tooltips, and progress bars are all
  restyled from the shared stylesheet — the whole app updates from one file.

Per the engineering rule (`Business Logic → AppState → View Models →
Presentation`), only the presentation layer changed. Full regression suite
stays green; Neo adds snapshot-style UI tests (`tests/test_neo_ui.py`).

---

## 17. Phase 8A — template contract + generic identity & validation

### 17.1 The goal

The last airfoil assumptions in the *generic* `Experiment` layer are
removed. Before Phase 8A, `case_id` / `geometry_key` / `validate` /
`to_json_dict` / `__repr__` assumed AOA, velocity, and airfoil geometry even
for templates that have nothing to do with airfoils. After Phase 8A the
generic core **asks the template**:

```
Template
   │  identity parameters        → case_id
   │  geometry parameters        → geometry_key
   │  validation policy          → experiment validation
   ▼
ExperimentDefinition
   ▼
Experiment  (identity / geometry / validation / serialization)
```

The generic `Experiment` no longer needs to know what CFD domain it serves.
The domain rule is preserved at the boundary the architecture always drew:
the External Aero *strategy/solver* may legitimately use AOA/Velocity/CL/CD —
the *generic* layer may not.

### 17.2 Template contract additions

`SimulationTemplate` gained two metadata fields (both optional — empty means
"default"):

| Field | Meaning | Default |
|---|---|---|
| `identity_parameters` | Ordered `(name, label)` pairs composing a case's identity (`case_id`); the label is the compact token rendered beside the value. | Every input parameter of the study definition, in study order, labelled by its own name. |
| `geometry_parameters` | Ordered parameter names determining mesh/geometry identity (`geometry_key`). | Every parameter with `category == "geometry"` **or** a `workbench_parameter` — the parameters that actually shape a mesh. |

The built-in templates declare exactly what their domains need:

- **External Aerodynamics** — `identity_parameters=(("aoa","aoa"),("velocity","v"))`,
  `geometry_parameters=("aoa",)`. This *reproduces* the legacy byte-identical
  identity (`r005_aoa8_v30`) and geometry (`aoa=8.000000`) — a declaration,
  not a special case.
- **Internal Flow** — `geometry_parameters=("pipe_diameter","pipe_length")`
  (the pipe dimensions are what a mesh depends on); identity is left to the
  default, so all five study inputs compose a case's identity and a
  velocity/fluid sweep reuses one pipe mesh.
- **A test-only third-template canary** (`tests/test_phase8a_generic_identity.py`)
  declares neither field, proving the *defaults* work for a template with no
  AOA/velocity/CL/CD anywhere.

### 17.3 Generic identity & geometry derivation

With a template attached, `Experiment` derives:

- **`case_id`** — `rNNN` + each identity parameter's `label{value:g}` +
  sorted Workbench extras (`source == "wbp"`, which is how non-identity
  Workbench parameters arrive), sanitized to filesystem-safe characters.
- **`geometry_key`** — `name={value:.6f}` for each declared geometry
  parameter + sorted Workbench extras, joined with `|`.

Workbench extras are marked by their **parameter source** (`"wbp"`), not by
their name — so an experiment never needs an AOA/velocity field to carry
extras, and a template's geometry contract stays data-driven.

Template-*less* experiments keep the legacy airfoil-shaped derivation
**byte-identically** — that path exists purely for backward compatibility and
is what the golden regression pins.

### 17.4 Experiment validation semantics

The distinction the contract insists on:

- **`ParameterDefinition.validate_value`** — *parameter-level* validation
  (finite / required / min / max / type), pure and reusable.
- **`SimulationTemplate.experiment_validation_problems(exp)`** — the
  *experiment-level* policy: each parameter the experiment carries is
  validated against its own definition, every problem prefixed with the
  parameter name (`velocity: Velocity: -5 is below the minimum of 0.01.`).

`Experiment.validate()` raises a single `ValueError` listing all problems.
The generic core never hardcodes a domain rule — the policy *is* the
template's parameters. The template-less legacy checks ("AOA is not a finite
number", "velocity must be a positive number") remain byte-identical on the
legacy path.

### 17.5 Compatibility accessors

`Experiment.aoa_deg`, `Experiment.velocity`, and `Experiment.extra_wb_params`
are preserved as **compatibility accessors** routing to the generic
`parameters` dict — one source of truth, never duplicate storage. External
Aero code continues to use them; the generic layer does not. Their eventual
removal is deferred to a later milestone once every downstream consumer has
migrated.

### 17.6 Serialization & `__repr__`

- **Template-attached** `to_json_dict()` is generic:
  `{row, status, template, parameters, metadata}` — no domain field implied.
- **Template-less** `to_json_dict()` is byte-identical to v1.0.
- `__repr__` is self-describing and domain-free: it names the template and
  the actual parameter set, never implying every experiment has `aoa_deg` /
  `velocity`.

(Full generic *result*/metric serialization — the `CaseResult` half — is
Phase 8B, not Phase 8A.)

### 17.7 Internal Flow generic path — the bridge is removed

The airfoil-shaped bridge `build_internal_flow_experiment` (Phase 7, §13.4)
is **deleted**. Internal-flow experiments are built through the generic
`ExperimentDefinition.build_experiment` path: all five study inputs land
under their own parameter names, `case_id` and `geometry_key` come from the
template contract, and validation uses the declared parameter bounds. No
`aoa` is fabricated anywhere. `internal_flow_inputs` is kept as genuine
domain logic and now reads straight from the parameter store.

### 17.8 Registration seam (minimal, additive)

Two one-function seams wire the *built-in* templates and strategies in a
single, explicit place — without touching the registry, the runtime, or the
generic core:

- `cfdauto.platform.registry.register_builtin_templates()`
- `cfdauto.execution.registry.register_builtin_strategies()`

A new built-in template is added by editing one of these functions. A
*third-party* template (the Phase 8A canary) registers itself on its own
`TemplateRegistry` at the call site — also with no core change. Full plugin
discovery (importlib entry points / packaging) is deliberately **not**
implemented; that is Phase 8G.

### 17.9 Backward compatibility (verified, not assumed)

External Aerodynamics is the golden regression. For existing rows — standard,
multiple AOA values, multiple velocities, WBP extras, and edge values — the
template-attached path reproduces the legacy `case_id`, `geometry_key`,
validation accept/reject behavior, and serialization **byte-identically**
(`r005_aoa8_v30_P112_P26`, `aoa=8.000000|P1=12.000000|P2=6.000000`). The
template-less legacy path is unchanged. The full suite (397 prior tests + the
Phase 8A tests) stays green; no existing assertion was weakened.

### 17.10 What Phase 8A deliberately leaves for later

- **8B** generic outputs & metrics (`CaseResult` serialization) — this sprint
  only made the *Experiment* half generic.
- **8C** generic Excel / `StudyIO`.
- **8D** generic results & analytics.
- **8E** generic storage / ledger.
- **8F** generic events + linter.
- **8G** full registration seam / plugin discovery.
- **8H** Internal Flow end-to-end through every downstream subsystem.

The Excel output system, ledger schema, analytics, orchestrator event
payloads, and the `gui/` are **untouched** by Phase 8A.
