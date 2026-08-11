# Slipstream QA Guide

A narrative, step-by-step manual verification walkthrough. For the fast
checkbox version of the same pass (used right before tagging a release),
see [`docs/RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md). None of this
requires ANSYS unless explicitly noted — Mock mode covers most of it.

> Applies to the current development version **v2.2.0-dev** (Neo v2.2 UI).

## 1. Startup verification

**Steps**
1. From a clean clone: `pip install -r requirements.txt -r requirements-gui.txt`.
2. Run `python main.py doctor`. With no `config/config.yaml` pointed at a
   real ANSYS install, several rows will show `WARN`/`FAIL` — that's
   expected; the check itself must run cleanly (no traceback, no crash)
   and print a summary line.
3. Run `python main.py gui` with no project ever opened before (or delete
   `%APPDATA%\Slipstream\recent_projects.json` / `~/.slipstream/recent_projects.json`
   first to simulate a truly fresh machine).

**Expected outcome:** the Project Selector dialog (Open Recent / Open
Existing / Create New) appears automatically shortly after the main
window shows — *not* a bare, silent empty Dashboard, and *not* an error
dialog. Cancelling it is safe; the Dashboard then shows its normal
"No project loaded" placeholder state.

**Troubleshooting:** if the dialog never appears, check whether a
`config/config.yaml` actually exists at the default path relative to where
you launched `python main.py gui` — a *valid, existing* config short-circuits
the first-run experience by design (this is the normal, unchanged launch
path for an existing project).

## 2. GUI walkthrough

With any project open (mock or real):

- **Dashboard** — status cards (Pending/Running/Done/Failed) update live;
  the L/D-vs-AOA chart and "Recent events" feed populate as cases finish;
  the Study Summary widget (bottom of the Dashboard) starts in its
  placeholder state ("Run a study to view summary statistics.").
- **Queue** (persistent right panel) — every schedule row appears,
  color-coded by status; **Run All**, **Run Selected**, **Stop**, and
  **Retry FAILED** are all reachable from the Queue controls and the
  toolbar/menu. The status filter pills (**ALL / PENDING / RUNNING /
  DONE / FAILED**) filter the visible rows, and the ☰ Queue toggle in the
  workspace header collapses the panel.
- **Monitor** (right dock, hidden by default — **View → Monitor**) —
  pipeline stage chips and a weighted progress bar for whichever case is
  currently running; empty/idle when nothing is running.
- **Results / Charts / Images** (sidebar pages) — populate only after at
  least one case has finished; **Charts** should render a CL-vs-AOA drag
  polar without error once there's data.
- **Parameters** (right dock, hidden by default — **View → Parameters**) —
  the metadata-generated form for the selected row (spinboxes with the
  active template's units/ranges; locked read-only for rows with results).
- **Log console** (bottom dock) — mirrors exactly what the CLI would print
  to the terminal.
- **Console** (bottom dock) — `help / open / run / stop / reload / mock`
  all respond without a traceback.
- **Focus Mode** (workspace header) — hides the sidebar, Queue, and docks;
  the current page fills the window and the exact layout is restored on exit.
- **File ▸ Projects…** (`Ctrl+Shift+O`) — reopens the Project Selector at
  any time, not just at startup.

**Expected outcome:** every panel above renders without a Python traceback
in the terminal, even with zero data loaded.

## 3. Mock workflow

**Steps**
1. Toggle **Mock mode** (toolbar checkbox or `Run` menu) — the orange
   "MOCK MODE" banner appears across the top of the workspace, and the
   window title/toolbar button both reflect it.
2. Click **▶ Run All**.
3. Wait for the batch to finish (a few seconds for the default 8-row template).

**Expected outcome:**
- Every row reaches `DONE` with plausible, non-null CL/CD/Lift/Drag values.
- The Live Monitor showed a moving progress bar and live CL/CD/residual
  plots while cases were running.
- The **Study Summary** widget on the Dashboard now shows real numbers —
  Total/Successful/Failed/Retries, Best L/D (+ row), Highest Lift (+ row),
  Lowest Drag (+ row), Fastest Convergence (+ row), a "Last updated"
  timestamp, and either "No warnings." or a list of deterministic
  warnings in the fixed severity order (failed → unconverged → retries →
  still-running → still-pending → empty study).
- Re-running **Run All** immediately afterward finds nothing to do (every
  row already `DONE`) — this is the resume-safety contract, not a bug.
- The Images panel shows 4 generated placeholder PNGs per case
  (geometry/mesh/pressure/velocity) — fabricated, not real CFD fields, by
  design in Mock mode.

## 4. Project workflow

**Steps**
1. **File ▸ Projects…** ▸ **Create New…** ▸ enter a name ▸ pick a parent folder.
2. Confirm the standard layout (`config/ data/ docs/ outputs/ runs/` +
   `project.json`) now exists on disk at that location.
3. Because a freshly created project has no `config.yaml` yet, confirm you
   get the informational message ("...still requires a config.yaml...")
   rather than a silent failure or a crash when Slipstream tries to load it.
4. Add/copy a working `config.yaml` into that project's `config/` folder,
   then **File ▸ Projects…** ▸ **Open Existing…** ▸ select the same folder.
5. Confirm the project now loads normally, and that it now appears under
   **Recent projects** the next time you open the dialog.
6. Reopen the same project a second time — confirm it still appears only
   **once** in the recent list (moved to the top, not duplicated).

**Expected outcome:** no step above should ever require deleting or
hand-editing `project.json`; opening an invalid/incomplete project shows
an actionable error message (via the existing error-formatting dialog),
never a raw Python traceback.

## 5. Packaging verification

Requires Windows + `pip install -r requirements-build.txt`. See
`build/README.md` for full detail.

**Steps**
1. `powershell -ExecutionPolicy Bypass -File build\build.ps1`
2. Run `dist\Slipstream\Slipstream.exe` directly (double-click or from a
   terminal — not `python gui_main.py`).
3. Repeat the Mock workflow (§3) against the packaged executable.
4. Right-click `Slipstream.exe` ▸ Properties ▸ Details — confirm File
   version / Product version match `cfdauto.__version__` for this release.

**Expected outcome:** the packaged app behaves identically to running from
source in Mock mode; the version shown in the title bar, About dialog, and
the `.exe`'s own file properties all agree.

**Troubleshooting:** Windows SmartScreen may warn on first launch of an
unsigned executable — expected, unrelated to a build defect. If the `.exe`
fails to start at all, rerun `build\build.ps1` from a clean tree
(`build\clean.ps1` first) before assuming a real regression.

## 6. Validation workflow

Requires `pip install -r requirements-validation.txt` for plot generation
(the metrics-only path needs nothing extra). See
`docs/validation/VALIDATION.md` for the full engineering write-up.

**Steps**
1. Run a real (or mock) study, then
   `python main.py export-study <name> --out docs/validation/benchmark/slipstream/<name>.csv`.
2. Place a reference dataset CSV (`AOA_deg, Velocity_m_s, CL, CD`) under
   `docs/validation/benchmark/reference/`.
3. `python -m tools.validation.compare docs/validation/benchmark/reference/<ref>.csv docs/validation/benchmark/slipstream/<name>.csv --out-dir docs/validation/benchmark --plots`

**Expected outcome:** `comparison_summary.json` and `comparison_table.csv`
appear under `docs/validation/benchmark/`, and `cl_comparison.png` /
`cd_comparison.png` / `ld_comparison.png` appear under
`docs/validation/benchmark/plots/`. Running the exact same two CSVs twice
must produce identical numbers and byte-identical plots — if it doesn't,
that's a real regression in the tooling, not expected variance.

**Note:** as of v2.2.0-dev this workflow has still not been run against a
real ANSYS benchmark case in this repository (this was already the case at
v1.0.0-rc1) — `docs/validation/VALIDATION.md` is still a template. Running
it end-to-end with real data is itself a useful QA pass even before a real
reference dataset is sourced (any two CSVs in the right shape will do to
confirm the tooling works).

## 7. General troubleshooting notes

- Most "GUI does nothing" reports trace back to `python main.py doctor`
  showing a `FAIL` row — run it first before filing anything as a bug.
- `ansys.version` and `fluent.product_version` in `config.yaml` **must**
  agree (see README's Troubleshooting section) — this is the single most
  common real-world misconfiguration.
- If the test suite fails only on GUI-related tests on a headless machine,
  set `QT_QPA_PLATFORM=offscreen` before running pytest.
- `config/config.yaml` and `experiments.xlsx` at the repository root are
  intentionally excluded from every release's git history (local working
  files) — don't expect them to match between machines.
