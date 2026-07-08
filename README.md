# Slipstream v0.8 — Desktop CFD Study Manager for ANSYS Workbench + Fluent

**Excel-driven parametric wing studies with a professional engineering GUI** —
project dashboard, live simulation monitoring, an interactive results
workspace, and the battle-tested `cfdauto` automation engine underneath.
Free · open source (Apache-2.0) · 100% local · no telemetry.

```
pip install -r requirements.txt -r requirements-gui.txt
python main.py gui            # toggle "Mock mode" in the toolbar → ▶ Run All
```

The **mock mode** demonstrates the entire application — queue, live pipeline
stages, CL/CD convergence plot, dataset table, charts, statistics, and
generated contour images — in ~5 seconds, with no ANSYS installed.

| Desktop shell (v0.8) | Engine (CLI, unchanged) |
|---|---|
| Dashboard · Project Explorer · Simulation Queue · Live Monitor (pipeline + progress + CL/CD) · Parameters editor · Results table · Interactive charts · Statistics · Image browser · Log console | `python main.py run` / `wb-info` / `init-template` — resumable batches, mesh caching, per-case artifacts |

Design record for this release: **`docs/V08_DESIGN.md`** ·
Long-term architecture: **`docs/CFD_PLATFORM_BLUEPRINT.md`** ·
Tests: `pytest tests/ -q` → engine suite + offscreen GUI smoke tests.

---

# Engine manual (cfdauto)

## cfdauto — Excel-driven ANSYS Workbench + Fluent AOA/velocity sweep automation

Production automation for aircraft-wing aerodynamic studies. An Excel workbook
is the experiment schedule; for every unfinished row the framework sets the
angle of attack in Workbench, updates geometry, regenerates the mesh, launches
Fluent with **identical physics**, applies the inlet velocity, solves to
convergence, extracts **CL, CD, Lift [N], Drag [N]** (plus CL/CD and FL/FD),
and writes the results back into the same row — then moves to the next one.
Kill it at any point and re-run the same command: it resumes exactly where it
stopped.

```
python main.py init-template experiments.xlsx     # 1. create the schedule
# fill in AOA_deg / Velocity_m_s rows, edit config/config.yaml
python main.py wb-info                            # 2. find system/parameter names
python main.py run --dry-run                      # 3. validate everything
python main.py run                                # 4. go (resumable, overnight-safe)
```

Tested end-to-end in mock mode (`python main.py run --mock`, `pytest tests/`),
which exercises the complete pipeline — Excel resume, mesh caching, retries,
artifacts — without ANSYS installed. Requires Python 3.11+, ANSYS 2024R2+
recommended (2024R2 and 2025R2 API differences are handled automatically).

---

## 1. High-level architecture

Layered, with one orchestrator and one controller per external tool. Python
(CPython 3.11+) is the brain; each ANSYS product is driven over the channel
that is most reliable for it:

```
                    ┌─────────────────────────────────────────────┐
                    │                main.py (CLI)                │
                    │      run · wb-info · init-template          │
                    └──────────────────┬──────────────────────────┘
                                       │
   config/config.yaml ──▶ ┌────────────▼────────────┐ ◀── runs/cfdauto.lock
   (all site-specifics)   │       Orchestrator      │     (single instance)
                          │  per-row pipeline loop  │
                          └─┬─────────┬───────────┬─┘
              ┌─────────────┘         │           └──────────────┐
   ┌──────────▼─────────┐  ┌──────────▼─────────┐  ┌─────────────▼──────────┐
   │    ExcelManager    │  │ WorkbenchController│  │    FluentController    │
   │ openpyxl, in-place │  │ renders IronPython │  │  PyFluent (gRPC) —     │
   │ status = run state │  │ journal → RunWB2   │  │  BCs, solve, extract   │
   │ atomic saves       │  │ -B -X -R (batch)   │  │  242/252 adapters      │
   └──────────┬─────────┘  └──────────┬─────────┘  └─────────────┬──────────┘
              │                       │                          │
   experiments.xlsx        wing_study.wbpj              baseline.cas.h5
   (the ledger)            SpaceClaim/DM ▸ Mesh         + FFF.msh per AOA
                           ▸ (Setup refresh)            (mesh replaced, physics
                                                         untouched)
```

Supporting modules: `models.py` (Experiment/CaseResult dataclasses),
`aero.py` (wind-axis vectors, q, C↔F conversions), `state.py` (lockfile,
mesh cache, per-case artifact dirs, result.json), `logging_setup.py`
(console + rotating file + per-case logs), `exceptions.py` (error taxonomy),
`mocks.py` (ANSYS-free backends), `config.py` (YAML → typed dataclasses,
unknown keys rejected loudly).

**Why a hybrid WB-journal + PyFluent design?** Geometry and meshing live
inside Workbench's dependency system, and the only fully reliable way to run
"set parameter → update geometry → update mesh" unattended across versions is
a batch journal (`RunWB2 -B -X -R`). The solver, by contrast, is far better
driven live over PyFluent's gRPC API: chunked iteration, convergence checks on
the actual force histories, structured result extraction, and clean error
handling — none of which a fire-and-forget journal can give you. Each tool is
used where it is strongest, and the mesh file is the clean hand-off between
them.

## 2. Folder structure

```
wing_aoa_automation/
├── main.py                        # CLI: run / wb-info / init-template
├── requirements.txt
├── experiments.xlsx               # THE schedule + results ledger (template incl.)
├── config/
│   └── config.yaml                # every site-specific setting, fully commented
├── cfdauto/                       # the package
│   ├── __init__.py
│   ├── config.py                  # YAML → validated dataclasses
│   ├── models.py                  # Experiment, CaseResult, status vocabulary
│   ├── aero.py                    # wind axes, q, coefficient↔force
│   ├── exceptions.py              # CaseError vs FrameworkError taxonomy
│   ├── logging_setup.py           # console + runs/logs/cfdauto.log + per-case
│   ├── excel_manager.py           # read schedule, resume logic, atomic writes
│   ├── state.py                   # lockfile, mesh cache, artifact dirs
│   ├── workbench_controller.py    # journal rendering + RunWB2 subprocess
│   ├── fluent_controller.py       # PyFluent session: BCs → solve → extract
│   ├── orchestrator.py            # the pipeline loop + failure policy
│   ├── mocks.py                   # ANSYS-free stand-ins (testing/CI)
│   └── templates/
│       ├── wb_update.wbjn.tpl     # set params → update Geometry+Mesh (+Setup)
│       └── wb_inspect.wbjn.tpl    # dump systems/parameters for `wb-info`
├── tools/
│   └── make_experiment_template.py
├── tests/
│   └── test_mock_pipeline.py      # end-to-end mock run, resume, retries, math
└── runs/                          # created at runtime
    ├── logs/cfdauto.log           # rotating debug log
    ├── cfdauto.lock               # PID lock (stale locks auto-cleared)
    ├── mesh_cache.json            # geometry_key → cached mesh
    ├── meshes/                    # meshes copied out of the WB project tree
    └── cases/<case_id>/           # per-experiment artifacts:
        ├── wb_update.wbjn         #   the exact journal that ran
        ├── wb_status.json         #   Workbench-side outcome
        ├── transcript.trn         #   full Fluent transcript
        ├── cfdauto_history.out    #   CL/CD vs iteration (plot me!)
        ├── result.json            #   authoritative result record
        └── case.log               #   everything logged for this case
```

## 3. Execution pipeline (per experiment row)

1. **Read schedule** — `ExcelManager` maps headers, parses rows, and queues
   everything not `DONE`/`SKIP` (plus `FAILED` with `--retry-failed`, plus
   stale `RUNNING` rows from a crash).
2. **Mark RUNNING** — written and saved immediately: the crash marker.
3. **Geometry & mesh** (`geometry` mode; skipped entirely in
   `velocity_vector` mode)
   - Mesh cache lookup by `geometry_key` (AOA + any `WBP:` extras). Hit →
     Workbench is skipped (a 4-AOA × 5-velocity matrix meshes 4 times, not 20).
   - Miss → render `wb_update.wbjn` from the template, run
     `RunWB2 -B -X -R journal` with a hard timeout, verify `wb_status.json`,
     discover the newest `*.msh*` under `<project>_files/dp0/**/MESH/`, and
     copy it to `runs/meshes/` (Workbench overwrites its copy next case).
4. **Solve** — fresh headless Fluent via PyFluent: read `baseline.cas.h5`
   (all physics) → `file.replace_mesh` → per-case **reference values**
   (velocity!) → inlet velocity (and rotated flow direction in
   `velocity_vector` mode) → create `cl/cd/fl/fd` report definitions →
   hybrid init (standard fallback) → iterate in chunks, checking CL/CD
   flatness → `report_definitions.compute()` → CL↔Lift cross-check.
5. **Record** — `result.json` first (authoritative), then the Excel row:
   CL, CD, CL/CD, Lift_N, Drag_N, FL/FD, Iterations, Converged, timestamps,
   Duration, CaseDir, Status=`DONE`/`FAILED` — saved atomically.
6. **Next row** — failures mark the row and continue (configurable).

## 4. AOA parameterization — recommended method

**Recommended: a driven rotation parameter in the CAD, exposed as a Workbench
parameter** (this is what the framework's `geometry` mode drives). One-time
setup:

*DesignModeler* — insert **Create ▸ Body Operation ▸ Rotate** (or a Rotate in
**Body Transformation**) on the wing body, axis = spanwise (e.g. Z), angle =
your AOA. In *Details*, tick the **P** checkbox next to the angle → it becomes
a Workbench parameter (`P1`, display text editable). DM parameters are the
most robust choice for unattended batch updates — they regenerate
deterministically and survive version upgrades well.

*SpaceClaim* — give the wing a **Move ▸ Rotate** with a driving dimension, or
create a **Group** holding the rotation angle (Groups panel → select the
dimension → *Create P Group*). The P-group appears in the WB parameter set the
same way. Works fine; just be aware SC scripts/records are historically more
version-sensitive than DM parameters.

Then: **Named Selections** for `inlet`, `outlet`, and every wing wall
(`wing`, …) — created once in the geometry so zone names survive every remesh
(this is what lets `replace_mesh` keep the boundary conditions attached).
Verify with `python main.py wb-info`, put the parameter name (or display
text) in `workbench.aoa_parameter`, done. Extra geometry parameters need
zero code: add an Excel column `WBP:<ParamName>`.

Rotate the **wing inside a fixed far-field domain** (not the whole domain), so
inlet/outlet orientation stays constant. At high AOA the Boolean/mesh can
fail — that surfaces as a clean `FAILED` row with the Workbench message, and
`retries_per_case` covers transient hiccups.

**Alternative worth knowing — `velocity_vector` mode** (built in, one config
switch): keep wing and mesh fixed and rotate the *incoming flow* at the inlet
instead; lift/drag are then evaluated along rotated wind axes
(drag = (cos α, sin α, 0), lift = (−sin α, cos α, 0) — handled automatically
in `aero.py`). No Workbench, no remeshing: a full sweep costs minutes of
overhead instead of hours, and mesh-induced scatter between AOAs disappears.
Standard practice for external aero **when the domain is a generous far
field** around the wing (all outer boundaries comfortably far, ideally
pressure-far-field or velocity inlets on the upstream faces). If your mesh is
tight around the wing or the domain is a narrow tunnel, stick with `geometry`
mode. The two modes produce directly comparable coefficients because both use
proper wind-axis force vectors.

## 5. How Python talks to each tool

| Tool | Channel | Why |
|---|---|---|
| **Workbench** (parameter, project update) | IronPython **journal** rendered from a template, executed by `RunWB2 -B -X -R <journal>` as a subprocess with timeout; outcome handed back via `wb_status.json` | Works on every WB version, fully headless, no COM fragility. The journal is saved per case = perfect reproducibility. |
| **Geometry** (SpaceClaim/DM) | Not scripted directly — the journal calls `Geometry.Update(AllDependencies=True)` and the parametric rotation regenerates | The parameter *is* the interface; far more robust than driving CAD scripts. |
| **Meshing** | `Mesh.Update(AllDependencies=True)` in the same journal; optional `Setup.Refresh()` forces the Fluent transfer `.msh` write | Uses your interactively-tuned mesh settings unchanged. |
| **Fluent** | **PyFluent** (`ansys-fluent-core`) over gRPC: `launch_fluent`, `file.read_case`, `file.replace_mesh`, settings tree for BCs/reference values/report definitions, `run_calculation.iterate`, `report_definitions.compute` | Live, structured control: chunked solving, convergence on force histories, typed extraction, clean shutdown. |
| **Excel** | `openpyxl` in-place edits (formatting preserved), atomic replace-on-save, retry loop for the file-open-in-Excel lock, CSV recovery sidecar | The workbook stays both human-friendly and machine-authoritative. |

*Modern alternative:* `ansys-workbench-core` (PyWorkbench, gRPC) can replace
the subprocess path on 2024R1+ — `launch_workbench()` + `client.run_script_string(...)`
with the same journal body. The controller is isolated behind
`prepare_mesh(exp, case_dir) -> Path`, so swapping backends touches one class.

## 6. CL/CD & force extraction strategy

- Four **report definitions** are created in the case: `cfdauto_cl`
  (type *lift*), `cfdauto_cd` (type *drag*), `cfdauto_fl`, `cfdauto_fd`
  (type *force*), all on `fluent.wall_zones`, with `force_vector`s supplied by
  `aero.wind_axes` (domain axes in `geometry` mode, rotated wind axes in
  `velocity_vector` mode).
- **Reference values are set per case** — density, area, length from config
  and **reference velocity = this row's inlet velocity**. This is the classic
  silent-killer: forget it and every velocity produces the "same" CL.
- A **report file** (`cfdauto_history.out`) logs CL/CD every iteration into
  the case folder; it drives convergence and doubles as the plot-ready history.
- Final numbers come from `report_definitions.compute(report_defs=[...])`
  (output-shape differences across PyFluent versions are normalized); if that
  ever fails, the last history values are used and forces are reconstructed as
  `C·q·A` (logged as such).
- **Cross-check:** `Lift ≈ CL·½ρV²A` must hold within
  `solve.crosscheck_tolerance` (default 3 %) — a mismatch warns loudly and
  almost always means the config reference values don't match the case.
- FL/FD is written as requested; note that with a single reference set it is
  mathematically identical to CL/CD (the sheet documents this).
- **Convergence criterion:** CL *and* CD flat (max−min < tolerance) over the
  trailing `convergence_window` samples, after `min_iterations`, iterating in
  `check_interval` chunks up to `max_iterations`. Force flatness is the
  criterion aerodynamicists actually trust — residuals routinely stall while
  the forces are long converged (keep your baseline case's residual criteria
  as a floor if you like; they simply stop a chunk early). Non-finite CL/CD →
  `DivergedError` → row `FAILED`.

## 7. Error recovery & resume

- **Status column = run state.** `PENDING/empty → RUNNING → DONE/FAILED`,
  `SKIP` respected. Crash mid-case? The row is still `RUNNING` and gets
  re-queued next launch (`rerun_stale_running`). Nothing is ever re-run that
  finished, nothing is lost that didn't.
- **Per-case isolation.** Everything solver-related raises a `CaseError`
  subclass (`WorkbenchError`, `MeshNotFoundError`, `FluentError`,
  `DivergedError`, `NotConvergedError`, `ResultExtractionError`) → row marked
  `FAILED` with the reason in *Error*, batch continues (`stop_on_failure`
  flips that). `FrameworkError`/`ConfigError` (bad paths, bad YAML) abort
  immediately — no point burning a night on a broken setup.
- **Retries:** `retries_per_case` extra attempts for transient failures
  (license blips, flaky mesh at high AOA).
- **Timeouts:** Workbench journals run under `subprocess` timeout
  (`workbench.timeout_s`); Fluent launch under `launch_timeout_s`; solving is
  bounded by `max_iterations` in chunked calls.
- **Excel can't eat your results.** `result.json` is written to the case
  folder *before* the workbook. Saves are atomic (temp file + `os.replace`);
  if the workbook is locked open in Excel, the save retries
  `save_retries × save_retry_wait_s` and finally appends to
  `runs/recovery_results.csv` instead of crashing the batch.
- **Single-instance lock** (`runs/cfdauto.lock`, stale-PID aware) prevents two
  batches fighting over the same project/workbook.
- **Full forensics per case:** journal, WB status, transcript, history,
  case.log, result.json — a failed 3 a.m. case is diagnosable at 9 a.m.

## 8. Scalability & future extensions

- **New geometry variables — zero code.** Add an Excel column
  `WBP:<WorkbenchParam>` (e.g. `WBP:FlapAngle`, `WBP:P3`); values flow into
  the journal's parameter dict, and the mesh cache key includes them
  automatically.
- **Turbulence model / physics variants.** The clean pattern: one exported
  baseline case per physics variant (`baseline_sst.cas.h5`,
  `baseline_keps.cas.h5`) and a config per study — physics stays *verified by
  you in the GUI*, not reverse-engineered in code. A `fluent.case_overrides`
  hook in `FluentController` is the natural place for programmatic model
  switching if you later want a `Model` column.
- **New backends.** The orchestrator depends only on two protocols
  (`prepare_mesh`, `run_case`); the mocks prove it. PyWorkbench, Fluent
  Meshing, or an HPC submit-and-poll backend are drop-in classes.
- **Parallel/HPC.** Per-case Fluent core count is `processor_count`; for
  farm-level parallelism, run several instances each pointed at its own copy
  of the project + a row-range (the lockfile intentionally serializes a
  *single* project). Workbench Design Points are the native alternative for
  massive DOEs — this framework deliberately stays outside it for
  per-case control, but the journal template shows exactly where DP calls
  would slot in.
- **Config-first design** means renamed columns, different units text, other
  zone names, 2-D airfoil studies (`dimension: 2`, area = chord × 1 m) are all
  YAML edits.

## 9. One-time setup checklist

1. `pip install -r requirements.txt` (Python 3.11+).
2. Geometry: parametric AOA rotation (Section 4) + Named Selections
   (`inlet`, `outlet`, `wing`…). Verify one manual Update works in WB.
3. Mesh: tune it once interactively; automation just re-runs it.
4. Fluent (via WB, once): set models, materials, BCs, solver controls,
   reasonable residual criteria → run a sanity case → **File ▸ Write ▸ Case**
   → that file is `fluent.baseline_case`.
5. `python main.py wb-info` → fill `workbench.system_name`,
   `workbench.aoa_parameter` in `config/config.yaml`; set zones, reference
   values (area & length = your planform & chord!), core count.
6. `python main.py init-template experiments.xlsx` → enter your AOA/velocity
   matrix.
7. `python main.py run --dry-run` → fix anything it flags.
8. `python main.py run --max-cases 1` → inspect the first case's artifacts.
9. `python main.py run` → let it work through the schedule. Watch
   `runs/logs/cfdauto.log` or the console.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `MeshNotFoundError` after a successful WB update | The Mesh cell updated but no `.msh` landed where expected. Keep `workbench.refresh_setup: true` (forces the Fluent transfer file), or point `workbench.mesh_file_glob` at your project's mesh path. |
| `replace_mesh` fails: zone name mismatch | Named Selections missing/renamed in the geometry, so the new mesh's zones ≠ baseline case zones. Fix the Named Selections; names must be stable. |
| Every velocity gives the same CL | Reference velocity wasn't updated → can't happen here (set per case), but if you see it, check the cross-check warning and `fluent.reference.area`. |
| `AWP_ROOT252 is not set` | Set `ansys.awp_root` explicitly or define the env var (e.g. `C:\Program Files\ANSYS Inc\v252`). |
| Workbook save keeps retrying | The file is open in Excel. Close it; the run continues. Worst case results land in `runs/recovery_results.csv` and in each case's `result.json`. |
| PyFluent launch errors / API mismatch | Pair versions sensibly: recent `ansys-fluent-core` + Fluent 2024R2/2025R2 are covered by the built-in adapters. Pin `fluent.product_version` if several ANSYS versions are installed. |
| WB journal fails instantly | Run the saved `runs/cases/<id>/wb_update.wbjn` manually via `RunWB2 -R` and read `wb_stdout.log` — the journal echoes each stage. |
| Two runs at once | Second instance exits on the lockfile. Stale locks from crashes clear themselves (PID check). |
| High-AOA meshing failures | Expected physics of the method: enable `retries_per_case`, consider `velocity_vector` mode for the sweep extremes, or robustify sizing in the Mesh cell. |

## License / notes

Internal engineering tooling example — adapt freely. The mock mode
(`--mock` / `CFDAUTO_MOCK=1`) is the fastest way to demo the workflow to
colleagues: the whole pipeline runs in ~2 s with plausible aerodynamics and
identical file outputs.
