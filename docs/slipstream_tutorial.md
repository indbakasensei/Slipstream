# Slipstream v2.2 — User Guide

**A desktop application for running CFD studies with ANSYS Workbench + Fluent**

Slipstream wraps the `cfdauto` CFD automation engine in the **Neo v2.2** desktop interface. You define a parametric study in Excel, press **Run All**, and watch every simulation from geometry update to convergence — live, in one window.

---

## Table of contents

1. [Overview](#1-overview)
2. [Launch the app](#2-launch-the-app)
3. [Interface layout](#3-interface-layout)
4. [Mock run (no ANSYS)](#4-mock-run-no-ansys)
5. [Open your project](#5-open-your-project)
6. [Queue panel and run controls](#6-queue-panel-and-run-controls)
7. [Live monitor](#7-live-monitor)
8. [Results page and charts](#8-results-page-and-charts)
9. [Images and artifacts](#9-images-and-artifacts)
10. [Edit experiments](#10-edit-experiments)
11. [Add experiments](#11-add-experiments)
12. [Resume and retry](#12-resume-and-retry)
13. [Panel reference guide](#13-panel-reference-guide)
14. [Keyboard shortcuts](#14-keyboard-shortcuts)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Overview

Everything you could previously only see in the terminal is now visualised in real time. The **engine is identical** — same Workbench journal, same PyFluent pipeline, same Excel resume ledger — the GUI simply makes it observable and interactive.

**Main features:**

- 📋 **Dashboard** — hero header, KPI row, Execution Pipeline, Study Overview, live L/D chart, Recent Activity, Study Summary
- 🧭 **Sidebar** — Workspace navigation (**Dashboard / Results / Charts / Images**) plus the embedded **Project** tree
- ▶ **Queue** — your schedule as a persistent, colour-coded table with run controls and status filters
- 📡 **Monitor** — live pipeline stages, telemetry, and CL/CD + residual convergence plots
- 📊 **Charts** — interactive presets plus custom X/Y/Colour — hover to identify, PNG export
- 🖼 **Images** — thumbnail browser + zoom/pan viewer for geometry, mesh, pressure and velocity contours
- 📈 **Statistics** — Mean, std, min/max for every metric — best case highlighted
- 🖥 **Console** — an engineering terminal with typed commands (`help / open / run / stop / reload / mock`)
- 🎯 **Focus Mode** — hide the sidebar, Queue, and docks so the current page fills the whole window
- ⚠️ **Mock mode** — test the whole application without ANSYS installed

---

## 2. Launch the app

### Step 1 — Open PowerShell in VS Code
Press `` Ctrl+` `` in VS Code, or open a new terminal window.

### Step 2 — Navigate and activate the virtual environment
```powershell
cd C:\Users\tejas\Desktop\CFD_Auto
..\venv\Scripts\activate    # (venv) prefix appears
cd slipstream
```

### Step 3 — Start Slipstream
```powershell
python main.py gui
```

The terminal line `Project loaded: config\config.yaml` appears and the window opens (its title shows `Slipstream — CFD Study Manager v2.2.0-dev`). The terminal stays "frozen" — that is normal, the Qt event loop is running.

> 💡 **Tip:** To close the app cleanly, press **Ctrl+Q** or use File → Exit. If a batch is running, Slipstream will ask you to confirm — the current case always finishes before stopping.

---

## 3. Interface layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Menu: File · Run · View · Help                                           │
│─────────────────────────────────────────────────────────────────────────│
│ Toolbar: [Open Project] [Reload]  |  SIMULATION  [▶ Run All] [⏹ Stop]   │
│          [☐ Mock mode (no ANSYS)]                                        │
│─────────────────────────────────────────────────────────────────────────│
│ ⚠ MOCK MODE banner — only visible when mock mode is active ⚠            │
│ ┌─────────┬────────────────────────────────────────────┬──────────────┐ │
│ │ BRAND   │ WorkspaceHeader (page · project · template │  QUEUE       │ │
│ │ header  │  · schedule)  [☰ Queue] [⛶ Focus]          │ (persistent  │ │
│ │ SIDEBAR ├────────────────────────────────────────────┤  panel)      │ │
│ │ Workspace│                                           │  Run All     │ │
│ │  • Dashboard    Center page (QStackedWidget):        │  Run Selected│ │
│ │  • Results      Dashboard / Results / Charts / Images│  Stop after  │ │
│ │  • Charts                                            │  case        │ │
│ │  • Images                                            │  …           │ │
│ │ Project │                                           │  status pills│ │
│ │  ▾ tree │                                           │  …           │ │
│ ├─────────┴────────────────────────────────────────────┴──────────────┤ │
│ │ LOG · Statistics · Console (tabbed bottom dock)                      │ │
│ ├─────────────────────────────────────────────────────────────────────┤ │
│ │ engine: case 2/8 … · queue: 6 pending · project · template · Py 3.x  │ │
│ │  · LIVE · Slipstream v2.2.0-dev                                       │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
```

**Sidebar** — the left column holds the brand header, the **Workspace** navigation (Dashboard / Results / Charts / Images), and the **Project** section with the project tree. Clicking a nav entry switches the center page.

**WorkspaceHeader** — the bar above the center page shows the current page, plus a `Project · Template · Schedule` context line. On its right edge: the **Queue toggle** (show/hide the Queue panel) and the **Focus** button (Focus Mode).

**Queue** — a **persistent right-hand panel, not a dock**. It holds the run controls and the schedule table. Hide it with the Queue toggle in the workspace header to give the center workspace more room.

**Docks** — **Monitor** and **Parameters** are docks that are **hidden by default**; reveal them from **View → Monitor / Parameters**. The bottom **Log · Statistics · Console** tab group is visible by default. Any dock can be dragged by its title bar to move or tab it; **View → Reset layout** restores the default arrangement.

---

## 4. Mock run (no ANSYS)

Before running real simulations, verify the whole GUI works using the built-in mock engine. It fabricates plausible aerodynamics and generates demo contour images in about 5 seconds.

### Step 1 — Enable Mock mode
Click **Mock mode (no ANSYS)** in the toolbar (or Run → Mock mode). When active you'll see:
- The button turns **orange**
- A **persistent orange banner** appears across the top of the workspace
- The window title shows **[MOCK MODE]** and the status bar chip reads **MOCK**

### Step 2 — Click ▶ Run All (or press F5)
The Queue shows all rows turn **RUNNING** then **DONE**. Open **View → Monitor** to watch the pipeline as the batch runs.

### Step 3 — Watch the pipeline stages light up

```
[Geometry+Mesh ✓] → [Fluent ✓] → [Setup ✓] → [Init ✓] → [▶ Solve] → [Extract]
```

Each chip turns **blue** when active and **green** when complete. A cached mesh shows as **teal** (Workbench was skipped).

### Step 4 — Explore the results

All 8 rows are **DONE** with CL/CD values. Go to:
- **Dashboard** — the L/D chart and Study Summary update live
- **Charts** (sidebar) — the **CL vs AOA** preset
- **Images** (sidebar)
- **Statistics** (bottom dock)

to see the full output.

> ⚠️ **Important:** After a mock run, right-click all rows → **Re-queue** and **untick Mock mode** before launching a real ANSYS run. Otherwise nothing will run ("Nothing to do").

---

## 5. Open your project

### Step 1 — Open a project
Two ways:
- **File → Open Project (Ctrl+O)** — navigate to `C:\Users\tejas\Desktop\CFD_Auto\slipstream\config\config.yaml` and click Open.
- **File → Projects… (Ctrl+Shift+O)** — the **Project Selector** dialog offers **Open Recent / Open Existing / Create New**. It also opens automatically at startup when no project is loaded.

### Step 2 — Verify the project loaded
The Dashboard hero header shows your project name and template, the **WorkspaceHeader** context line reads `Project · Template · Schedule`, the Queue populates with rows, and the status bar shows the queue summary. The **Project** section in the sidebar shows your config, schedule, baseline case, and run folders.

### Step 3 — Before running, close these:
- ✗ **Workbench GUI** — two instances of Workbench on the same project causes a crash
- ✗ **Excel** with experiments.xlsx open — the engine needs write access

---

## 6. Queue panel and run controls

The Queue is the persistent right-hand panel. Its header line summarises the schedule (`8 cases · 6 pending · 2 done`), and the status filter pills (**ALL / PENDING / RUNNING / DONE / FAILED**) hide rows that don't match.

```
┌ Queue ─────────────────────────────────────────────────────────────┐
│ Queue                        8 cases · 6 pending · 2 done          │
│ Run: [▶ Run All] [Run Selected] [⏹ Stop after case]                │
│ [ALL] [PENDING] [RUNNING] [DONE] [FAILED]  ☐ Retry FAILED Max:[all▾]│
│                                                                    │
│  Row  AOA  Velocity  Status   CL       CD      L/D    It    Conv   │
│  ───────────────────────────────────────────────────────────────    │
│    2    0     20     DONE     0.1969  0.0183  10.78   400    YES   │
│    3    0     30     FAILED   nan     nan     nan      0    NO     │
│    4    4     20     DONE    -0.0146  0.0129  -1.13   400    YES   │
│    5    4     30     RUNNING   …        …        …      …    …     │
│    6    8     20     PENDING                                       │
│    7    8     30     PENDING                                       │
│    8   12     20     SKIP                                          │
│    9   12     30     PENDING                                       │
└────────────────────────────────────────────────────────────────────┘
```

The table columns (Row, then the study inputs, then Status / CL / CD / L/D / It / Conv) are generated from the active template's metadata — hovering an input column header shows its unit and allowed range.

### Run controls

| Button | What it does |
|--------|-------------|
| **▶ Run All** | Runs every PENDING row in order. DONE and SKIP rows are ignored. |
| **Run Selected** | Select rows with click/Ctrl+click, then press this to run only those rows. |
| **⏹ Stop after case** | Graceful stop — finishes the currently running case then halts. Re-run to resume; DONE rows are skipped automatically. |
| **☑ Retry FAILED** | When ticked, FAILED rows are added back to the queue when you click Run All. |
| **Max** | Set to 1 for a single-case smoke test. "all" (value 0) means no limit. |

### Status filter pills
Click **PENDING / RUNNING / DONE / FAILED** to show only rows in that state (presentation only — nothing is removed from the schedule). Click **ALL** to restore the full list.

### Right-click context menu

| Action | When to use |
|--------|-------------|
| **Toggle SKIP** | Exclude a row from the batch without deleting it. Toggle again to re-include. |
| **Re-queue (clear status)** | Clears DONE or FAILED status so the row runs again. Use after fixing a geometry issue. |

> 💡 **Hide the Queue:** click the **Queue toggle** (☰) in the workspace header to collapse the Queue and give the center workspace more room. Click again to restore it at its previous width.

---

## 7. Live monitor

Open **View → Monitor** to watch the active case. Every block updates in real time as the engine progresses.

```
┌ Monitor — Current Run ──────────────────────────────────────────────┐
│                                                                      │
│  Case 3/8 — r005_aoa4_v30              [Running]                    │
│                                                                      │
│  [✓ Geo+Mesh]→[✓ Fluent]→[✓ Setup]→[✓ Init]→[▶ Solve]→[ Extract]   │
│                                                                      │
│  ████████████████████░░░░░░░░░  74%            Est. remaining 2m 11s│
│                                                                      │
│ ┌ Live Telemetry ──────────────────────────────────────────────────┐ │
│ │ Iterations     742     Min residual  8.2e-06                      │ │
│ │ CL       0.48312       CD        0.02184                          │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ ┌ Convergence ──────────────── Forces | Residuals ────────────────┐ │
│ │  CL   ╭───────────────────                                      │ │
│ │  CD      ╭─────────────────                                     │ │
│ └──────┬──────┬──────┬──────┬──── iteration ─────────────────────┘ │
│       100    200    300    400                                     │
│ ┌ Event History ──────────────────────────────────────────────────┐ │
│ │ 10:32:07  ▶ Case started — r005_aoa4_v30                        │ │
│ │ 10:32:05  ◆ Mesh generated                                      │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Reading the monitor

| Element | Meaning |
|---------|---------|
| Status chip | **Running / Converged / Done / Failed / Idle** — the current case state |
| Stage chips | **Blue** = currently active · **Green** = done · **Teal** = cached (mesh reused, WB skipped) · **Red** = failed |
| Progress bar | Weighted: Geo+Mesh = 0–25%, Solve = 25–95%, Extract = 95–100% |
| Est. remaining | Estimated time to the case finishing, from iterations so far |
| Live Telemetry | Iterations, min residual, and the template's force metrics (CL/CD) as live readouts |
| Convergence | The **Forces** and **Residuals** plots (tabbed). Flat tail = the solver has converged. The engine declares convergence when the forces are flat within tolerance. |
| Event History | Newest-first feed: mesh generated, solver started, convergence, results written, finished |

> 💡 **What "converged" means:** The engine uses **force flatness**, not residuals. It checks that CL and CD change by less than a threshold over the last 50 samples. You'll see `Converged at iteration N` in the Log when it stops early — this is correct behaviour.

---

## 8. Results page and charts

### Results page
Click **Results** in the sidebar to see the full dataset. Click any column header to sort. Click a row to select that case (the Monitor and Images panels update). Click **Export CSV** to save the entire table.

### Charts page — interactive plots

Open **Charts** in the sidebar. The preset buttons cover the most common aero plots (labels are generated from the active template's inputs):

| Preset | X | Y | Color by | What it shows |
|--------|---|---|----------|--------------|
| **CL vs AOA** | AOA | CL | Velocity | Lift curve slope — should rise with AOA up to stall |
| **Drag polar** | CD | CL | AOA | Classic polar — lower-left = efficient |
| **L/D vs V** | Velocity | L/D | AOA | Aerodynamic efficiency by speed |

You can also set any **X / Y / Color by** combination manually using the dropdowns. **Hover over any point** to see the case ID and exact values. **Export PNG…** saves a high-resolution chart image.

> ⚠️ **Current note — inverted AOA:** If your study shows CL *decreasing* with AOA and negative L/D, this is a **geometry rotation sign issue** in DesignModeler (positive P1 rotates nose-down instead of nose-up). The charts and data are correct — the sign convention just needs fixing. Open the Rotate body operation in DM, flip the axis direction, re-export `baseline.cas.h5`, and re-run.

### Statistics dock (bottom)
Shows count/mean/std/min/max for every output metric across all DONE cases, plus a headline **Best L/D** case. Visible alongside the Log in the tabbed bottom dock — click **Statistics** to bring it forward.

---

## 9. Images and artifacts

The **Images** page (sidebar) lets you browse every image file in a case's artifact folder — geometry screenshots, mesh previews, pressure and velocity contours.

### Step 1 — Select a case
Use the **Case** dropdown at the top to pick any case, or click a row in the Queue/Results table — the dropdown updates automatically.

### Step 2 — Browse thumbnails
Thumbnails appear on the left with a zoomable preview on the right, plus a metadata readout (file · dimensions · size · path). Real ANSYS runs (with `capture_images: true`) generate 4 images per case:
- `geometry.png` — wireframe view of the wing
- `mesh.png` — surface mesh with black edges
- `pressure_contour.png` — static pressure on the wall
- `velocity_contour.png` — velocity magnitude on the wall

### Step 3 — Zoom and pan
- **Scroll wheel** to zoom in/out
- **Drag** to pan
- Press the **fit** button to reset the view

### Step 4 — Open the folder
Click the **folder** button to see all case artifacts in Windows Explorer: `transcript.trn`, `cfdauto_history.out`, `result.json`, `case.log`, and any exported images.

> 💡 **Enabling real contour images:** To capture actual pressure/velocity contours from Fluent, open `config\config.yaml` and set:
> ```yaml
> fluent:
>   capture_images: true
> ```
> This triggers an experimental step after convergence. If it fails for any reason, the case still completes normally.

---

## 10. Edit experiments

Open **View → Parameters**. Click any row in the Queue first to load it.

> ⚠️ **Lock rule:** Inputs can only be edited on rows that have **not produced results yet** (status PENDING, FAILED, or SKIP). Rows with status DONE show their values as read-only to protect provenance.

### Step 1 — Select a pending row in the Queue
Click the row. The Parameters panel loads its current input values.

### Step 2 — Change the values
Adjust the spinboxes. The editors are **generated from the active template's metadata** — each row shows its display name, allowed range, unit, and default (so an Internal Flow template shows its own parameters here, with no UI change).

### Step 3 — Click Apply changes
The workbook is saved atomically. The Queue table updates immediately.

---

## 11. Add experiments

The **Add experiment** section in the Parameters panel adds new rows to the schedule without opening Excel.

| Button | What it does |
|--------|-------------|
| **＋ Add row** | Appends a new row with the values you've set in the spinboxes. Status is PENDING. |
| **Duplicate selected** | Copies the currently selected row (same inputs and any extra Workbench parameters) as a new PENDING row. |

---

## 12. Resume and retry

### Resume after a stop or crash
Slipstream is always resume-safe. Close the window, kill the terminal, or press Stop — the `experiments.xlsx` Status column records exactly where you are. Re-open the app and press **▶ Run All**: DONE rows are skipped, the batch continues from the first PENDING row.

> 💡 **Tip:** Any row left as **RUNNING** by a crash is automatically re-queued on the next run. You never lose progress.

### Retry failed rows

1. **Tick ☑ Retry FAILED** in the Queue
2. **Click ▶ Run All** — Failed rows are added back to the queue and re-executed.

### Re-run everything from scratch
Select all rows in the Queue (Ctrl+A), right-click → **Re-queue (clear status)**, then click **▶ Run All**.

Or regenerate a clean schedule from the terminal:
```powershell
python main.py init-template experiments.xlsx
```
Then click **Reload Project** in the toolbar (Ctrl+R).

---

## 13. Panel reference guide

| Panel | Location | Purpose |
|-------|----------|---------|
| **Dashboard** | Sidebar → page (default) | Hero header, KPI row, Execution Pipeline, Study Overview, L/D chart, Recent Activity, Study Summary |
| **Results** | Sidebar → page | Full sortable dataset table · Export CSV |
| **Charts** | Sidebar → page | X/Y/colour interactive plots · presets · hover · Export PNG |
| **Images** | Sidebar → page | Browse and zoom case artifact images |
| **Project** | Sidebar → Project section | Project tree: config, schedule, baseline case, all case folders |
| **Queue** | Right panel (persistent) | Schedule table + run controls + status filters + right-click actions |
| **Parameters** | Right dock — hidden by default | Edit inputs for selected row · add/duplicate rows (View → Parameters) |
| **Monitor** | Right dock — hidden by default | Live pipeline stages + telemetry + CL/CD + residual convergence (View → Monitor) |
| **Log** | Bottom dock (tab) | Full engine log stream — same as the old terminal output |
| **Statistics** | Bottom dock (tab) | Descriptive stats for all DONE cases + best L/D headline |
| **Console** | Bottom dock (tab) | Engineering terminal — `help / open / run / stop / reload / mock` |

> 💡 **Rearranging:** The Monitor, Parameters, Log, Statistics, and Console are docks — drag any by its title bar to move or tab it. Use **View → Reset layout** to restore the default positions. The Sidebar and Queue are fixed panels; the Queue can be hidden with the ☰ toggle in the workspace header, and **Focus Mode** hides everything but the current page.

---

## 14. Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Run All (start a batch) |
| `Shift+F5` | Stop after current case |
| `Ctrl+O` | Open Project |
| `Ctrl+R` | Reload Project (re-reads config + workbook) |
| `Ctrl+Shift+O` | Projects… (Open Recent / Open Existing / Create New) |
| `Ctrl+Q` | Exit (asks if a batch is running) |
| `Ctrl+A` | Select all rows in Queue / Results table |
| `Scroll wheel` | Zoom in/out in the Images viewer |

---

## 15. Troubleshooting

### Nothing to do — all rows say DONE
The workbook already has results from a previous run. Right-click rows → **Re-queue**, or tick **Retry FAILED** if rows are FAILED.

### Window opened but charts/plots are blank
Add `useOpenGL=False` to pyqtgraph config. Open `gui\theme.py`, find `pg.setConfigOptions(...)` and add the option, then restart.

### Run All does nothing (engine exits instantly)
Check the **Log** panel — it will show the reason. Most common: ANSYS project file not found (wrong path in config.yaml), or Workbench GUI is open at the same time.

### Row stuck as RUNNING after a crash
This is expected and handled automatically. Re-run the app and press **▶ Run All** — the RUNNING row is re-queued and starts fresh.

### Excel save fails / workbook locked
Close `experiments.xlsx` in Excel. The engine retries 10 times (60 seconds) — if you close Excel during that window, the save succeeds.

### Workbench crashes (rc=3221225477)
Close the Workbench GUI before running. Only one Workbench instance can have a project open at a time. Check the `runs\cases\<id>\wb_stdout.log` file for the actual error (visible in the Project section of the sidebar → double-click the file).

### CL is negative / L/D chart goes downward
This is the rotation sign issue: the P1 parameter is rotating the wing nose-down for positive values. Fix: in DesignModeler, open the Rotate body operation and flip the rotation axis direction. Re-export `baseline.cas.h5` and re-run.

### Fluent crashes with "Abnormal Exit" / RPC handshake failure
Usually an ANSYS Student license lockout after previous crashes. Fix:
```powershell
Get-Process | Where-Object {$_.ProcessName -like "*fluent*"} | Stop-Process -Force
Get-Process | Where-Object {$_.ProcessName -like "*fl_mpi*"} | Stop-Process -Force
```
Wait 5 minutes for the license server to release tokens, then retry.

### Mesh image shows only surface (no grid lines visible)
This happens when Fluent 26.1's mesh display API doesn't set edge visibility properly. Solutions:
1. Try opening the case manually in Fluent GUI to verify mesh actually exists
2. Increase mesh edge visibility manually in `fluent_controller.py` `_capture_images` method
3. Enable `save_case_data: true` in config, then open `final.cas.h5` in Fluent GUI for full 3D inspection

### Solver stalls at high AOA (CL/CD frozen for 1500 iterations)
Steady-state RANS cannot resolve deep post-stall flow (typically past ±14° AOA on most wings). The solver "converges" numerically but the physics is unphysical due to massive vortex shedding. **Limit AOA range to ±12°** for meaningful results. Beyond that requires LES/DES.

### `compute() returned no value` warning
Cosmetic warning on Fluent 26.1 — results are extracted from the history file correctly. Latest `fluent_controller.py` uses the history file first and eliminates this warning.

### Images not appearing after real ANSYS runs
Verify `fluent.capture_images: true` is set in config (NOT under `ansys:` — must be under `fluent:`):
```powershell
@"
import yaml
cfg = yaml.safe_load(open('config/config.yaml'))
print('capture_images =', cfg['fluent'].get('capture_images', False))
"@ | python
```
Must print `capture_images = True`.

---

**Slipstream v2.2.0-dev · Apache-2.0 · Engine: cfdauto · GUI: PySide6 + pyqtgraph · No telemetry · No cloud required**
