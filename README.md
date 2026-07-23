# Slipstream — Desktop CFD Study Manager for ANSYS Workbench + Fluent

**Excel-driven parametric wing studies with a professional engineering GUI, a live-streaming simulation monitor, a SQLite provenance ledger, and a battle-tested automation engine underneath.**

`Apache-2.0` · `100% local` · `no telemetry` · `no cloud` · `146/146 tests pass`

```bash
pip install -r requirements.txt -r requirements-gui.txt
python main.py gui            # toggle "Mock mode" → ▶ Run All
```

The **mock mode** demonstrates the entire application — queue, live pipeline stages, streaming CL/CD/residual plots, results table, charts, statistics, and generated contour images — in ~5 seconds, with no ANSYS installed.

---

## What it is (in one paragraph)

Slipstream is a local-first desktop application that automates ANSYS Fluent aerodynamics studies. You define a parametric sweep in Excel (AOA × velocity × any Workbench parameter), press **Run All**, and every simulation runs headlessly with:

- **Live plots** of CL, CD, and 6 scaled residuals streaming from Fluent per iteration
- **Automatic mesh caching** by geometry key (Workbench skipped when possible)
- **Resume-safe Excel ledger** — kill the process anytime, DONE rows are skipped on the next run
- **Physics linter** that flags stall regimes, Mach violations, and default reference values before wasting compute
- **`doctor` command** that diagnoses 14 aspects of your environment (ANSYS paths, licenses, locks, orphaned processes) in one shot
- **SQLite provenance database** with config hashing — `diff-config` shows exactly what changed between two batches
- **Per-case artifacts** — geometry, mesh, pressure and velocity contour PNGs, transcripts, per-case logs
- **License-lockout cascade detector** — halts the batch after 3 consecutive Fluent launch failures instead of burning through 25 cases in 90 seconds

The GUI is built on PySide6 + pyqtgraph. The engine (`cfdauto`) works with any Fluent aerodynamics project — the framework doesn't know or care what geometry you have. It only needs a Workbench project with a parameter promoted to `P1`, a baseline `.cas.h5` file, and named zones for the inlet, outlet, and walls.

---

## Table of contents

1. [Features at a glance](#features-at-a-glance)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [30-second quickstart](#30-second-quickstart)
5. [The GUI](#the-gui)
6. [The CLI](#the-cli)
7. [Configuration reference](#configuration-reference)
8. [Excel schedule format](#excel-schedule-format)
9. [SQLite ledger (v0.9-M3)](#sqlite-ledger)
10. [Study Analytics (v1.0.0-alpha.3)](#study-analytics)
11. [Projects (v1.0.0-alpha.5)](#projects)
12. [Architecture](#architecture)
13. [Building & Packaging (v1.0.0-alpha.6)](#building--packaging)
14. [Validation (v1.0.0-alpha.7)](#validation)
15. [Troubleshooting](#troubleshooting)
16. [Roadmap](#roadmap)
17. [Contributing](#contributing)
18. [License and credits](#license-and-credits)

---

## Features at a glance

### Desktop shell (v0.8)

- **Dashboard** — Status cards, overall progress, live L/D chart, recent events, pipeline mirror
- **Project Explorer** — Config, schedule, baseline case, every case folder with its artifacts
- **Queue** — Live colour-coded schedule table with Run All / Run Selected / Stop / Retry FAILED
- **Live Monitor** — Pipeline stage chips + weighted progress bar + **tabbed Forces + Residuals plots** (log-y residuals)
- **Parameters editor** — Edit AOA/velocity/WBP columns for any PENDING row, add or duplicate rows
- **Results table** — Sortable, CSV export
- **Interactive charts** — CL-vs-AOA, drag polar, L/D-vs-V presets plus custom X/Y/colour; hover-identify; PNG export
- **Statistics dock** — Mean/std/min/max for every metric + best-L/D headline
- **Image browser** — Thumbnails + zoom/pan viewer for `geometry.png`, `mesh.png`, `pressure_contour.png`, `velocity_contour.png`
- **Log console** — Streaming engine log identical to the CLI
- **Mock mode** — Full application demo with fabricated results, zero ANSYS required. Orange banner + toolbar highlight + `[MOCK MODE]` title make it unmissable.

### Engine (`cfdauto`)

- **Excel-driven scheduling** with atomic writes, 10-retry save on locked workbooks
- **Workbench batch journaling** with parameter-driven geometry updates
- **PyFluent solve loop** with sub-chunk iteration for smooth live telemetry
- **Force-flatness convergence** (CL/CD trailing-window standard deviation) — no residual-tolerance hunting
- **Mesh caching by geometry hash** — Workbench skipped when the AOA (and any extra Workbench parameters) are unchanged
- **Version-tolerant PyFluent adapters** — handles quirks across Fluent 24, 25, 26.1
- **Per-case log files, transcripts, and artifact folders**
- **Resume-safe with dead-PID lock detection** — never loses progress even after crashes

### v0.9 Engine Hardening

- **`aoa_scale` config knob** — one-line fix for inverted DesignModeler rotations
- **`doctor` command** — 14-check environment diagnosis with FAIL/WARN/PASS table and exit codes
- **Physics linter** — pre-flight checks for post-stall AOA, Mach violations, placeholder reference values, Student core-cap
- **Per-iteration telemetry tap** — thread-safe background poller streams CL/CD + residuals during solves
- **UTF-8 / UTF-16 LE / UTF-16 BE transcript auto-detection** — Fluent 26.1 on Windows writes UTF-16
- **Stale history-file cleanup** — Fluent 26.1 refuses to overwrite report files; the framework deletes stale variants first
- **License-lockout cascade detector** — auto-cleanup + halt after 3 consecutive Fluent-launch failures
- **SQLite ledger** — every batch, case, iteration recorded with config-hash provenance and cross-study querying

---

## Requirements

**Operating system**
- Windows 10/11 (primary — ANSYS-tested)
- Linux (engine + GUI both run; ANSYS not commonly installed but supported by PyFluent)
- macOS (engine only; ANSYS is not available for Apple silicon)

**Python**
- 3.11 or 3.12
- Virtual environment recommended

**ANSYS** (real runs only — mock mode needs none)
- ANSYS Workbench + Fluent
- Tested on ANSYS Student 2026 R1 (v261) and commercial installations
- ANSYS Student edition works with the built-in 4-core cap; the linter warns if you exceed it

---

## Installation

```bash
git clone https://github.com/<your-username>/slipstream.git
cd slipstream

# Create a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# Install the engine
pip install -r requirements.txt

# Install the desktop GUI (add if you want the desktop app)
pip install -r requirements-gui.txt

# Confirm all tests pass (146/146 as of v1.0.0-rc1)
python -m pytest tests/ -q
```

### Windows / ANSYS Student install path

If the `doctor` command reports missing ANSYS paths, edit `config/config.yaml` and set:

```yaml
ansys:
  version: "261"                                      # 2026 R1 = v261
  awp_root: "C:/Program Files/ANSYS Inc/ANSYS Student/v261"
  runwb2: "C:/Program Files/ANSYS Inc/ANSYS Student/v261/Framework/bin/Win64/RunWB2.exe"

fluent:
  product_version: "26.1.0"                           # must match ansys.version
```

Then rerun `python main.py doctor` — every check should pass.

---

## 30-second quickstart

```bash
# 1. Verify environment
python main.py doctor

# 2. Try the mock mode (no ANSYS)
python main.py gui
# → tick "Mock mode" in the toolbar → click "▶ Run All"
# 8 mock cases finish in ~5 seconds with live streaming plots.

# 3. For real runs: point config.yaml at your Workbench project + baseline case
# Confirm parameter names in your project
python main.py wb-info

# Preview what would run
python main.py run --dry-run

# Run one case as a smoke test
python main.py run --max-cases 1

# Full batch (or use the GUI)
python main.py run
```

---

## The GUI

### Layout

```
┌ Menu: File · Run · View · Help ──────────────────────────────────────────┐
│ [Open Project] [Reload] │ [▶ Run All] [⏹ Stop] │ [☐ Mock mode]           │
│─────────────────────────────────────────────────────────────────────────│
│ ⚠ ORANGE BANNER (visible only when mock mode is active) ⚠               │
│─────────────────────────────────────────────────────────────────────────│
│              │                                          │ QUEUE           │
│   EXPLORER   │  Dashboard  Results  Charts  Images     │ Run All RunSel  │
│   Project    │                                          │ ⏹ Stop ☐Retry  │
│   ⚙ config   │                                          │ Row AOA V St CL │
│   ▤ schedule │  Central workspace (tabs)                │  2  0 20 ✓ .20  │
│   ⬢ baseline │                                          │  3  0 30 ▶ …    │
│   Runs       │                                          │─────────────────│
│   📁 r002…   │                                          │ MONITOR         │
│      *.png   │                                          │ r003 · 2/8      │
│              │                                          │ [Stages]        │
│   [Refresh]  │                                          │ ████████░ 74%   │
│              │                                          │ CL/CD live plot │
│              │                                          │ Residual log-y  │
│─────────────────────────────────────────────────────────────────────────│
│                       LOG · Statistics (tabbed)                          │
│─────────────────────────────────────────────────────────────────────────│
│ engine: case 2/8 — r003_aoa0_v30 · queue: 6 pending · v1.0.0-rc1         │
└─────────────────────────────────────────────────────────────────────────┘
```

Every panel is dockable — drag by its title bar to move or tab it. `View → Reset layout` restores the default arrangement.

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Run All |
| `Shift+F5` | Stop after current case |
| `Ctrl+O` | Open Project |
| `Ctrl+R` | Reload Project |
| `Ctrl+Q` | Exit |
| `Ctrl+A` | Select all rows in Queue / Results |
| Scroll wheel | Zoom the Images viewer |

Full walkthrough with troubleshooting: [`docs/slipstream_tutorial.html`](docs/slipstream_tutorial.html) or [`.md`](docs/slipstream_tutorial.md).

---

## The CLI

```bash
python main.py <command> [options]
```

| Command | What it does |
|---------|-------------|
| `gui` | Launch the desktop application |
| `doctor` | 14-check environment diagnosis with PASS/WARN/FAIL table |
| `run` | Execute the schedule (batch mode). Options: `--dry-run`, `--max-cases N`, `--retry-failed`, `--config PATH` |
| `wb-info` | Print Workbench parameter names for the project (helps set `aoa_parameter`) |
| `init-template` | Generate a fresh `experiments.xlsx` with the correct columns |
| `studies` | (M3) List studies recorded in the ledger |
| `batches [--study NAME]` | (M3) List recent batches, optionally per study |
| `query "<SQL>"` | (M3) Read-only SQL against the SQLite ledger |
| `diff-config <HASH_A> <HASH_B>` | (M3) Show every config setting that differs between two batches |
| `export-study NAME --out PATH.csv` | (M3) Export every case in a study to CSV |

Example — see what changed between yesterday's good run and today's broken run:

```bash
python main.py batches
# id  study      config_hash    started_at
# 12  wing_v2    a1f4d329e8b7   2026-07-10T09:15:22
# 11  wing_v2    76b85065c2cb   2026-07-09T14:03:11

python main.py diff-config 76b85065c2cb a1f4d329e8b7
# 2 difference(s) between 76b85065c2cb and a1f4d329e8b7:
#   fluent.product_version    "26.1.0"  →  "27.1.0"
#   workbench.aoa_scale       -1.0      →  1.0
```

---

## Configuration reference

`config/config.yaml` is the single source of truth. Every debugged setting from real ANSYS runs:

```yaml
ansys:
  version: "261"                                      # ANSYS release: 261 = 2026 R1
  awp_root: "C:/Program Files/ANSYS Inc/ANSYS Student/v261"
  runwb2: "C:/Program Files/ANSYS Inc/ANSYS Student/v261/Framework/bin/Win64/RunWB2.exe"

workbench:
  project_file: "C:/path/to/wing_study.wbpj"
  system_name: "FFF"                                  # from `python main.py wb-info`
  aoa_parameter: "P1"                                 # from `python main.py wb-info`
  aoa_expression: "{value} [degree]"
  aoa_scale: 1.0                                      # -1.0 flips inverted DM rotations
  update_geometry: true
  refresh_setup: true
  save_project: true
  timeout_s: 3600

fluent:
  baseline_case: "C:/path/to/baseline.cas.h5"
  dimension: 3
  precision: "double"
  processor_count: 4                                  # Student edition cap
  product_version: "26.1.0"                           # MUST match ansys.version
  ui_mode: "no_gui"
  launch_timeout_s: 900
  inlet_zone: "inlet"
  inlet_type: "velocity_inlet"
  wall_zones: ["wing"]
  aoa_method: "geometry"                              # rotates via WB parameter
  base_flow_axis: "+x"
  base_lift_axis: "+y"
  capture_images: true                                # write 4 PNGs per case
  reference:
    density: 1.225                                    # kg/m³ sea-level air
    viscosity: 1.7894e-05
    area: 0.35                                        # m² — your real planform area
    length: 0.4                                       # m — your real chord
    depth: 1.0
    temperature: 288.16
    pressure: 0.0

solve:
  max_iterations: 500                                 # 1500 wastes time on stalls
  check_interval: 20                                  # smaller = smoother telemetry
  min_iterations: 100
  convergence_window: 50                              # trailing-samples flatness check
  cl_tolerance: 1.0e-3
  cd_tolerance: 1.0e-4
  initialization: "hybrid"
  accept_unconverged: true                            # write results even if not converged
  save_case_data: false                               # true = ~200 MB per case
  crosscheck_tolerance: 0.03                          # 3% CL·q·A vs Lift force sanity check

excel:
  file: "C:/path/to/experiments.xlsx"
  sheet: "Experiments"
  header_row: 1
  save_retries: 10                                    # retry N times if workbook is open in Excel
  save_retry_wait_s: 6                                # seconds between retries
  columns:
    aoa:        "AOA_deg"
    velocity:   "Velocity_m_s"
    status:     "Status"
    cl:         "CL"
    cd:         "CD"
    cl_cd:      "CL/CD"
    lift:       "Lift_N"
    drag:       "Drag_N"
    fl_fd:      "FL/FD"
    iterations: "Iterations"
    converged:  "Converged"
    error:      "Error"
    started:    "Started"
    finished:   "Finished"
    duration:   "Duration_min"
    case_dir:   "CaseDir"

runtime:
  work_dir: "runs"
  retries_per_case: 0                                 # don't waste 20 min on physics failures
  stop_on_failure: false
  reuse_mesh_per_geometry: true
  rerun_stale_running: true                           # re-queue RUNNING rows after crashes
  mock: false                                         # true = fabricate everything, no ANSYS
  study_name: "wing_v2_sweep"                         # tags batches in the SQLite ledger
```

---

## Excel schedule format

`experiments.xlsx` is where you define the sweep. Generate a fresh template:

```bash
python main.py init-template experiments.xlsx
```

Fill in `AOA_deg` and `Velocity_m_s`. Leave `Status` blank — the engine writes `RUNNING`, `DONE`, or `FAILED` there and never loses progress.

For multi-parameter studies, add columns prefixed with `WBP:` (Workbench Parameter). Any column named `WBP:Alpha`, `WBP:Beta`, etc. is automatically bound to Workbench parameters by name — no code change needed.

**Example schedule:**

| AOA_deg | Velocity_m_s | WBP:Flap | Status | CL | CD | ... |
|---------|--------------|----------|--------|-----|-----|-----|
| 0 | 20 | 0 | | | | |
| 4 | 20 | 0 | | | | |
| 8 | 20 | 0 | | | | |
| 4 | 20 | 15 | | | | |
| 4 | 20 | 30 | | | | |

The engine walks the queue in row order, caches meshes by (AOA, WBP:*) key, and skips Workbench when it can.

---

## SQLite ledger

Slipstream writes every batch, case, and per-iteration data point to `runs/slipstream.db` alongside the Excel workbook. Excel remains the human-facing schedule and result store; the database adds provenance and analytics.

### Schema (v1)

- **`studies`** — named groups of runs (`runtime.study_name`)
- **`configs`** — every unique effective config as a JSON snapshot, keyed by SHA-256 hash
- **`batches`** — one row per `main.py run`, tagged with study + config hash + version + timing
- **`cases`** — every experiment with row/case_id/AOA/velocity/CL/CD/lift/drag/iterations/converged/error
- **`iterations`** — the per-iteration telemetry tap output: `(case_id, iter, cl, cd, continuity, x_velocity, y_velocity, z_velocity, k, omega)`

### Why it matters

Every debugging session where a value silently drifted (`aoa_scale` reverted, `product_version` mismatched, `capture_images` moved to the wrong YAML section) is now diagnosable in one command:

```bash
python main.py batches --study wing_v2
python main.py diff-config <good_hash> <bad_hash>
```

The database is additive and non-fatal — if it fails to open or write, the batch still succeeds and Excel remains authoritative.

---

## Study Analytics

**What it is.** `cfdauto/study_analytics.py` is a small, read-only module that computes a `StudySummary` — a lightweight snapshot of one batch's results (how many cases succeeded/failed, the best-performing cases, and a list of deterministic warnings). It is purely computational: it never writes to Excel, never touches the ledger or a solver/Workbench controller, and never logs anything itself.

**When it runs.** Automatically, once, at the very end of every `Orchestrator.run()` call — after all of that call's cases have already been written to the Excel workbook (or the batch stopped early / hit the license-lockout cascade halt / had nothing queued at all). It never runs mid-batch and never changes what happens during a solve.

**How it works.** The orchestrator hands it the exact row numbers it queued for that `run()` call; the module re-reads their current Status/CL/CD/Lift/Drag/Iterations/Converged straight back out of the workbook via `ExcelManager`'s existing read methods — no new Excel columns, no schema change. The orchestrator then logs the result (one INFO summary line plus one WARNING per finding) — logging is the orchestrator's job, not the analytics module's.

**Metrics produced (`StudySummary`):**
- `total_cases`, `successful_cases`, `failed_cases`
- `best_l_over_d` (+ the row it came from), `highest_lift_n` (+ row), `lowest_drag_n` (+ row)
- `fastest_convergence_iterations` (+ row) — `None` when no successful, *converged* case has iteration data
- `retries` — retry attempts across the whole batch (Excel/the ledger don't track this per-case, so it's a batch total, not per-row)
- `warnings: list[StudyWarning]` — each a `(code, message)` pair from a fixed, explicit rule (never a subjective heuristic): `EMPTY_STUDY`, `CASE_FAILED`, `RETRIES_OCCURRED`, `UNCONVERGED_SUCCESS`, `ROW_STILL_RUNNING`, `ROW_STILL_PENDING`

**Tie-breaking.** If multiple rows tie exactly on a "best" metric, the **first row encountered** (ascending row number) wins, consistently, every time — never an arbitrary later row.

**Accessing it.** `Orchestrator._current_study_summary` always holds the most recently *completed* `run()` call's summary (reset to `None` at the start of every `run()`, then populated at every normal return — including a partial summary, with warnings, if the batch stopped early). It stays `None` only if `run()` raises before finishing its own bookkeeping (a `FrameworkError` abort from bad config/environment) — the raised exception is the caller's signal in that case.

**Limitations in this version.** No GUI panel yet, no historical/cross-batch view, and no persistence of the summary itself (it's recomputed fresh from Excel each time, and discarded when the process exits). The `average_l_over_d` / `average_cl` / `average_cd` / `average_iterations` fields exist on `StudySummary` today but are reserved for a future sprint — always `None` in v1.

**Future roadmap.** A GUI panel that renders this summary, and a ledger-backed historical view across many past batches, are tracked as a separate, larger feature in [`docs/PRODUCT_BACKLOG.md`](docs/PRODUCT_BACKLOG.md) (§4.3 — GUI Study Analytics Panel) — not part of this module.

---

## Projects

**Purpose.** `cfdauto/project_manager.py` (v1.0.0-alpha.5) adds a lightweight, optional organizational layer *above* the existing `config.yaml` workflow — a way to keep multiple CFD studies cleanly separated on disk, with recent-project tracking, instead of managing loose `config.yaml`/`experiments.xlsx` pairs by hand. It does **not** change how a study executes: opening a project simply points the existing config-loading flow at that project's `config/config.yaml`, unchanged.

### Project directory layout

```
Project/
├── config/
│   └── config.yaml      # exactly the same config.yaml the engine always used
├── data/                # optional: reference datasets, notes, imports
├── docs/                # optional: project-specific documentation
├── outputs/             # optional: exported CSVs, reports
├── runs/                # runtime.work_dir usually points here
└── project.json         # metadata: name, description, created, last_opened,
                          #           project_version, created_with, tags
```

`project.json` stores only lightweight metadata — never simulation results, config values, or anything the SQLite ledger already owns.

### Creating a project

GUI: **File ▸ Projects…** (`Ctrl+Shift+O`) ▸ enter a name ▸ **Create New…** ▸ pick a parent folder. Slipstream creates the standard layout and `project.json` immediately. A freshly created project has no `config.yaml` yet — add one at `<project>/config/config.yaml` before opening it (the dialog tells you this explicitly if you try to open it too soon).

Programmatically:

```python
from cfdauto.project_manager import create_project
create_project("C:/CFD/wing_v2", name="Wing v2", description="Flap sweep")
```

### Opening a project

GUI: **File ▸ Projects…** ▸ **Open Existing…** (browse to any valid project folder) or double-click an entry under **Recent projects**. If `config/config.yaml` exists, Slipstream loads it exactly the way `File ▸ Open Project…` always has; opening also bumps the project's `last_opened` timestamp.

An invalid project (missing standard folders, missing or corrupt `project.json`) is rejected with every problem listed at once — never just the first one found.

### Recent projects

Every successful open/create is recorded, most-recent-first, de-duplicated (opening the same project again moves it to the top rather than adding a second entry), capped at 10 entries. The list lives in your user data directory (`%APPDATA%/Slipstream/recent_projects.json` on Windows, `~/.slipstream/recent_projects.json` elsewhere) — a corrupt or missing recents file is simply treated as an empty list, never an error.

---

## Architecture

```
slipstream/
├── main.py                  # CLI entry: run, gui, doctor, wb-info, init-template,
│                            #           studies, batches, query, diff-config, export-study
├── gui_main.py              # GUI entry (imports gui.app)
├── config/
│   └── config.yaml          # your project config
│
├── cfdauto/                 # engine package (~4000 lines, 100% type-hinted)
│   ├── __init__.py          # version
│   ├── config.py            # dataclasses with validation
│   ├── models.py            # Experiment, CaseResult, Status constants
│   ├── events.py            # EventBus (thread-safe fan-out)
│   ├── exceptions.py        # CaseError, FrameworkError, FluentError, ...
│   ├── excel_manager.py     # atomic Excel read/write with retry
│   ├── state.py             # RunState (mesh cache, lock file, work_dir)
│   ├── workbench_controller.py    # WB batch journal + parameter binding
│   ├── fluent_controller.py       # PyFluent solve loop + image capture
│   ├── orchestrator.py            # main loop + cascade detector + ledger writes
│   ├── mocks.py             # dependency-free mock backends
│   ├── aero.py              # coefficient/force conversions
│   ├── telemetry.py         # v0.9-M2: per-iteration tap for CL/CD/residuals
│   ├── doctor.py            # v0.9-M1: environment diagnosis
│   ├── linter.py            # v0.9-M1: physics pre-flight
│   ├── ledger.py            # v0.9-M3: SQLite ledger + config hashing
│   ├── ledger_cli.py        # v0.9-M3: query/diff-config/export-study
│   ├── error_formatting.py  # v1.0.0-alpha.2: centralized error explanations
│   ├── study_analytics.py   # v1.0.0-alpha.3: post-batch StudySummary (read-only)
│   ├── project_manager.py   # v1.0.0-alpha.5: project folders + metadata + recents
│   ├── simulation_context.py # v2.0.0-dev: runtime template-metadata source of truth
│   ├── platform/            # v2.0.0-dev: universal CFD platform metadata
│   │   ├── parameters.py    #   ParameterDefinition (generic inputs)
│   │   ├── metrics.py       #   MetricDefinition (generic outputs)
│   │   ├── study_definition.py #   StudyDefinition (ordered inputs + columns)
│   │   ├── templates.py     #   SimulationTemplate + External Aerodynamics
│   │   └── registry.py      #   TemplateRegistry (see docs/PLATFORM_ARCHITECTURE.md)
│   └── logging_setup.py     # per-case log files
│
├── gui/                     # PySide6 desktop shell
│   ├── app.py, main_window.py
│   ├── theme.py
│   ├── state.py             # AppState (dataset, config, running flag)
│   ├── event_bridge.py      # bus → Qt signals bridge
│   ├── project_selector_dialog.py  # v1.0.0-alpha.5: Open Recent/Existing/Create New
│   ├── panels/
│   │   ├── dashboard.py, queue_panel.py, monitor.py, params_panel.py,
│   │   │   results_table.py, charts_panel.py, stats_panel.py,
│   │   │   images_panel.py, log_console.py, explorer.py
│   └── widgets/
│       └── cards.py, pipeline_widget.py
│
├── tests/                   # 33 tests
│   ├── test_engine.py       # baseline: models, config, aero, orchestrator
│   ├── test_v09_m1.py       # aoa_scale, linter rules, doctor
│   ├── test_v09_m2.py       # telemetry tap, residuals correlation, mock streaming
│   ├── test_v09_m2_encoding.py  # UTF-8 / UTF-16 LE / UTF-16 BE
│   └── test_v09_m3.py       # ledger schema, config hash, end-to-end
│
├── tools/                   # small utilities
│   ├── make_experiment_template.py
│   ├── inspect_fluent_mesh_api.py
│   └── validation/          # v1.0.0-alpha.7: compare.py + plots.py (never
│                             #   imported by the runtime app — see tools/validation/README.md)
│
├── docs/
│   ├── slipstream_tutorial.html
│   ├── slipstream_tutorial.md
│   ├── RELEASE_CHECKLIST.md # v1.0.0-alpha.6: manual pre-release checklist
│   └── validation/          # v1.0.0-alpha.7: VALIDATION.md + benchmark/{reference,slipstream,plots}
│
├── build/                   # v1.0.0-alpha.6: packaging (see build/README.md)
│   ├── slipstream.spec      # PyInstaller one-folder build spec
│   ├── make_version_info.py # generates the .exe's version resource from cfdauto.__version__
│   ├── build.ps1, clean.ps1, release.ps1
│   └── README.md
│
└── .github/workflows/
    └── ci.yml               # Ubuntu + Windows, Python 3.11 + 3.12
```

---

## Building & Packaging

Full details, prerequisites, and troubleshooting live in
[`build/README.md`](build/README.md) — this is a summary.

### Building from source

No packaging needed to develop or use Slipstream day-to-day — this is
what every earlier section of this README already assumes:

```bash
pip install -r requirements.txt -r requirements-gui.txt
python main.py gui
```

### Packaging prerequisites

Building the standalone Windows executable additionally needs:

```bash
pip install -r requirements-build.txt   # installs PyInstaller
```

ANSYS is **not** required to build or run the packaged executable — Mock
mode works standalone in the packaged `.exe` exactly as it does from
source.

### Creating release builds

```powershell
powershell -ExecutionPolicy Bypass -File build\build.ps1     # build only
powershell -ExecutionPolicy Bypass -File build\release.ps1   # clean + build + zip
powershell -ExecutionPolicy Bypass -File build\clean.ps1     # remove all generated output
```

`release.ps1` reads the version to embed in the archive's filename
(`Slipstream-v<version>-win64.zip`) directly from `cfdauto.__version__` —
the same single authoritative version source shown in the window title,
status bar, and About dialog — so the archive name can never drift from
what the app itself reports.

### Running the packaged executable

```
dist\Slipstream\Slipstream.exe
```

This is a one-folder build (a `Slipstream\` directory containing the
`.exe` plus its dependencies) rather than a single file — this keeps
PySide6/Qt's LGPLv3-licensed DLLs separate and individually replaceable,
per the LGPL-compliance approach already documented in
[`docs/CFD_PLATFORM_BLUEPRINT.md`](docs/CFD_PLATFORM_BLUEPRINT.md) §20.
Copy/zip the whole `Slipstream\` folder to distribute it, not just the
`.exe`.

### Known limitations

- Windows-only packaging path (the engine/GUI both still run cross-platform
  from source).
- No installer (MSI/NSIS) — just a one-folder build, zipped by `release.ps1`.
- Not code-signed — Windows SmartScreen may warn on first launch; this is
  expected for an unsigned executable and unrelated to the build itself.
- No icon is bundled yet (none exists in this repository — see
  `build/README.md` for how to add one later without touching the spec).
- See [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) for the
  manual verification a release should go through before tagging.

---

## Validation

**Purpose.** A repeatable way to check Slipstream's simulated CL/CD/L-D
against a trusted, independent reference dataset — not a one-off sanity
check, but a documented process any future release can re-run after an
engine, ANSYS version, or dependency change. Full write-up:
[`docs/validation/VALIDATION.md`](docs/validation/VALIDATION.md).

**Workflow.**

```bash
# 1. Run the real study, then export it in the standard column shape
python main.py export-study <study_name> --out docs/validation/benchmark/slipstream/<study_name>.csv

# 2. Drop a reference dataset CSV (AOA_deg, Velocity_m_s, CL, CD) into
#    docs/validation/benchmark/reference/ — sourced independently of
#    Slipstream, never generated by it

# 3. Compare
pip install -r requirements-validation.txt    # only needed for --plots
python -m tools.validation.compare \
    docs/validation/benchmark/reference/<ref>.csv \
    docs/validation/benchmark/slipstream/<study_name>.csv \
    --out-dir docs/validation/benchmark --plots
```

**Benchmark directory** — `docs/validation/benchmark/`: `reference/` (the
trusted dataset), `slipstream/` (Slipstream's own exported results),
`plots/` (generated comparison figures). No benchmark data ships in this
repository yet — each subfolder currently holds only a `PLACEHOLDER.md`
explaining what belongs there.

**Comparison tools** — `tools/validation/` (`compare.py` + `plots.py`):
pure, deterministic utilities, entirely separate from the runtime engine
— never imported by `main.py`, `cfdauto/`, or `gui/`. `compare.py` is
stdlib-only; only plot generation needs `requirements-validation.txt`
(matplotlib). Full reference: [`tools/validation/README.md`](tools/validation/README.md).

**Expected outputs:** `comparison_summary.json` (matched/unmatched row
counts + per-metric Mean Absolute Error, Root Mean Square Error, and
Maximum Absolute Error), `comparison_table.csv` (the same as a flat
table), and `cl_comparison.png` / `cd_comparison.png` / `ld_comparison.png`
under `docs/validation/benchmark/plots/`.

---

## Troubleshooting

### `python main.py doctor` says FAIL on an ANSYS path

Your config's `ansys.awp_root` or `runwb2` points to the wrong version. If you have ANSYS Student 2026 R1, they should end in `v261`, not `v271`. Fix the config and rerun `doctor`.

### `Fluent failed to launch: 'AWP_ROOT271'`

Config mismatch: `ansys.version: "261"` but `fluent.product_version: "27.1.0"`. PyFluent looks up `AWP_ROOT271` (from product_version) and doesn't find it. Set both to the same version (e.g. `"261"` and `"26.1.0"`) and rerun.

### Multiple consecutive `Fluent failed to launch: RPC UNAVAILABLE`

ANSYS Student license lockout — tokens are stuck for 30-60 min after a crashed session. The cascade detector halts the batch after 3 in a row. Kill orphaned processes and wait:

```powershell
Get-Process | Where-Object {$_.ProcessName -match "fluent|fl_mpi|cx"} | Stop-Process -Force
Remove-Item -Force runs\cfdauto.lock -ErrorAction SilentlyContinue
# wait 5-10 minutes, or restart your PC
```

### Residuals plot is empty during a real solve

Make sure you've replaced both `cfdauto/telemetry.py` and `cfdauto/fluent_controller.py` with v0.9-M2. The fix requires the stale-history-file cleanup in `fluent_controller.py` to work.

### CL decreases as AOA increases (upside-down polar)

Your DesignModeler rotation axis is inverted. Two options:

1. Set `workbench.aoa_scale: -1.0` in `config.yaml`. Enter natural positive angles in Excel; the engine negates before writing to the parameter.
2. Open the geometry in DesignModeler, flip the Rotate body axis direction, and re-export `baseline.cas.h5`.

### `Nothing to do — every row is DONE`

The workbook already has results. Right-click rows in the Queue → **Re-queue (clear status)**, or add `--retry-failed` to also re-queue FAILED rows.

Full troubleshooting matrix in [`docs/slipstream_tutorial.html`](docs/slipstream_tutorial.html).

---

## Roadmap

**v0.8 (shipped)** — GUI shell, live monitor with per-chunk progress, results/charts/images/stats panels

**v0.9 (shipped)**
- ✅ M1 — `aoa_scale`, `doctor`, physics linter, mesh-cache hardening
- ✅ M2 — per-iteration telemetry tap, live residuals plot, UTF-16 support, sub-chunk iteration, stale-file cleanup, license cascade detector
- ✅ M3 — SQLite ledger with config-hash provenance, per-iteration storage, 5 query commands

**v1.0.0-alpha.1 – alpha.7 (shipped)**
- ✅ alpha.1 — CI pipeline on GitHub Actions (Ubuntu + Windows, 3.11 + 3.12); behavioral test hardening for `config`/`excel_manager`/`state`/`doctor`
- ✅ alpha.2 — Centralized error formatting (CLI, GUI dialogs, `doctor`)
- ✅ alpha.3 — Study Analytics: post-batch `StudySummary` (best L/D, retries, warnings, …)
- ✅ alpha.4 — Study Summary panel on the GUI Dashboard (read-only view of the analytics above)
- ✅ alpha.5 — Project & Study Management: project folders, metadata, recent-projects, Project Selector
- ✅ alpha.6 — Packaging: PyInstaller one-folder Windows build, release scripts, centralized versioning
- ✅ alpha.7 — Benchmark validation framework (`tools/validation/`): MAE/RMSE/max-error comparison + plots against a reference dataset

**v1.0.0-rc1 (current)** — documentation audit, version-consistency pass, release notes, changelog, QA guide, release metadata (this release)

**Remaining before a final v1.0.0 tag**
- NACA 0012 validation as a second-geometry portfolio proof point (the *framework* to do this shipped in alpha.7; the actual benchmark run has not — see [`docs/validation/VALIDATION.md`](docs/validation/VALIDATION.md), which is currently a template)
- A dedicated USAGE guide and CONTRIBUTING guide as standalone files (currently folded into this README)

**Future** (tracked in [`docs/CFD_PLATFORM_BLUEPRINT.md`](docs/CFD_PLATFORM_BLUEPRINT.md), explicitly out of scope through v1.0)
- Interactive 3D viewer with PyVista (rotate/pan/zoom pressure and velocity fields, slice planes, streamlines)
- PDF report generator
- Multi-turbulence-model support (LES/DES for cases where RANS stalls)
- OpenFOAM backend (fully free CFD path, no ANSYS required)

Full blueprint: [`docs/CFD_PLATFORM_BLUEPRINT.md`](docs/CFD_PLATFORM_BLUEPRINT.md). Full backlog: [`docs/PRODUCT_BACKLOG.md`](docs/PRODUCT_BACKLOG.md).

---

## Contributing

1. Fork the repo, create a feature branch
2. Run `python -m pytest tests/ -q` — must show all tests passing (146/146 as of v1.0.0-rc1; more if you add tests)
3. Follow the existing code style: type hints everywhere, docstrings on public functions, small classes with narrow responsibilities
4. Open a pull request describing what problem you solved

The codebase is deliberately over-commented for readers who are also learning CFD automation. Continue that tradition.

### Running the test suite

```bash
# The full suite (146 tests as of v1.0.0-rc1)
python -m pytest tests/ -q

# Just the M3 SQLite tests
python -m pytest tests/test_v09_m3.py -v

# GUI tests need Qt's offscreen platform on headless machines
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q
```

---

## License and credits

**Apache License 2.0** — see [LICENSE](LICENSE).

Built with:
- [PySide6](https://doc.qt.io/qtforpython-6/) — Qt for Python
- [pyqtgraph](https://www.pyqtgraph.org/) — high-performance plots
- [ansys-fluent-core](https://fluent.docs.pyansys.com/) — PyFluent
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel read/write
- [pandas](https://pandas.pydata.org/) — data handling
- [PyYAML](https://pyyaml.org/) — config parsing
- [matplotlib](https://matplotlib.org/) — benchmark comparison plots (validation tooling only)

Slipstream is not affiliated with or endorsed by Ansys, Inc. ANSYS, Fluent, and Workbench are trademarks of Ansys, Inc.

---

**No telemetry. No cloud dependency. Your compute, your data, your machine.**
