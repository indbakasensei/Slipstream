# Slipstream v0.8 — User Guide

**A desktop application for running CFD studies with ANSYS Workbench + Fluent**

Slipstream wraps the `cfdauto` CFD automation engine in a professional desktop interface. You define a parametric study in Excel, press **Run All**, and watch every simulation from geometry update to convergence — live, in one window.

---

## Table of contents

1. [Overview](#1-overview)
2. [Launch the app](#2-launch-the-app)
3. [Interface layout](#3-interface-layout)
4. [Mock run (no ANSYS)](#4-mock-run-no-ansys)
5. [Open your project](#5-open-your-project)
6. [Queue panel and run controls](#6-queue-panel-and-run-controls)
7. [Live monitor](#7-live-monitor)
8. [Results tab and charts](#8-results-tab-and-charts)
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

- 📋 **Dashboard** — Status cards, overall progress, live L/D chart, recent events
- ▶ **Queue** — Your schedule as a live colour-coded table with run controls
- 📡 **Monitor** — Pipeline stages, progress bar, live CL/CD convergence plot
- 📊 **Charts** — Interactive polars, drag charts, L/D maps — hover to identify
- 🖼 **Images** — Browse and zoom geometry, mesh, pressure and velocity contours
- 📈 **Statistics** — Mean, std, min/max for every metric — best case highlighted
- ⚠️ **Mock mode** — Test the whole application without ANSYS installed

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

The terminal line `Project loaded: config\config.yaml` appears and the window opens. The terminal stays "frozen" — that is normal, the Qt event loop is running.

> 💡 **Tip:** To close the app cleanly, press **Ctrl+Q** or use File → Exit. If a batch is running, Slipstream will ask you to confirm — the current case always finishes before stopping.

---

## 3. Interface layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Menu: File · Run · View · Help                                           │
│─────────────────────────────────────────────────────────────────────────│
│ [Open Project] [Reload] │ [▶ Run All] [⏹ Stop] │ [☐ Mock mode]           │
│─────────────────────────────────────────────────────────────────────────│
│ ⚠ ORANGE BANNER (only visible when mock mode is active) ⚠               │
│─────────────────────────────────────────────────────────────────────────│
│              │                                          │ QUEUE           │
│   EXPLORER   │  Dashboard  Results  Charts  Images     │ Run All RunSel  │
│   Project    │                                          │ ⏹ Stop ☐Retry  │
│   ⚙ config   │                                          │ Row AOA V St CL │
│   ▤ schedule │  Central workspace (see tabs below)     │  2  0 20 ✓ .20  │
│   ⬢ baseline │                                          │  3  0 30 ▶ …    │
│   Runs       │                                          │─────────────────│
│   📁 r002…   │                                          │ MONITOR         │
│      *.png   │                                          │ r003 · 2/8      │
│              │                                          │ [Stages]        │
│   [Refresh]  │                                          │ ████████░ 74%   │
│              │                                          │ CL/CD live plot │
│─────────────────────────────────────────────────────────────────────────│
│                       LOG · Statistics (tabbed)                          │
│─────────────────────────────────────────────────────────────────────────│
│ engine: case 2/8 — r003_aoa0_v30 · queue: 6 pending · v0.8.0             │
└─────────────────────────────────────────────────────────────────────────┘
```

**Dockable panels:** Every panel can be dragged to a new position, tabbed, or closed from the **View** menu. Use **View → Reset layout** to restore the default arrangement.

---

## 4. Mock run (no ANSYS)

Before running real simulations, verify the whole GUI works using the built-in mock engine. It fabricates plausible aerodynamics and generates demo contour images in about 5 seconds.

### Step 1 — Enable Mock mode
Click **Mock mode (no ANSYS)** in the toolbar. When active you'll see:
- The button turns **orange**
- A **persistent orange banner** appears across the top
- The window title shows **[MOCK MODE]**

### Step 2 — Click ▶ Run All (or press F5)
The Queue shows all rows turn **RUNNING** then **DONE**. Switch to the **Monitor** tab (bottom right) to watch the pipeline.

### Step 3 — Watch the pipeline stages light up

```
[Geometry+Mesh ✓] → [Fluent ✓] → [Setup ✓] → [Init ✓] → [▶ Solve] → [Extract]
```

Each chip turns **blue** when active and **green** when complete. A cached mesh shows as **teal** (Workbench was skipped).

### Step 4 — Explore the results

All 8 rows are **DONE** with CL/CD values. Go to:
- **Charts → CL vs AOA** preset
- **Images tab**
- **Statistics dock**

to see the full output.

> ⚠️ **Important:** After a mock run, right-click all rows → **Re-queue** and **untick Mock mode** before launching a real ANSYS run. Otherwise nothing will run ("Nothing to do").

---

## 5. Open your project

### Step 1 — File → Open Project (Ctrl+O)
Navigate to `C:\Users\tejas\Desktop\CFD_Auto\slipstream\config\config.yaml` and click Open.

### Step 2 — Verify the project loaded
The Dashboard title shows your project path, the Queue populates with rows, and the status bar shows **"N experiments"**. The Explorer dock (left) shows your schedule and baseline case.

### Step 3 — Before running, close these:
- ✗ **Workbench GUI** — two instances of Workbench on the same project causes a crash
- ✗ **Excel** with experiments.xlsx open — the engine needs write access

---

## 6. Queue panel and run controls

```
┌ Queue dock ──────────────────────────────────────────────────────┐
│ [▶ Run All] [Run Selected] [⏹ Stop after case] ☐ Retry FAILED    │
│                                                    Max: [all ▾] │
│                                                                  │
│  Row  AOA  Velocity  Status   CL       CD      L/D    It         │
│  ────────────────────────────────────────────────────────────    │
│    2    0     20     DONE     0.1969  0.0183  10.78   400        │
│    3    0     30     FAILED   nan     nan     nan       0        │
│    4    4     20     DONE    -0.0146  0.0129  -1.13   400        │
│    5    4     30     RUNNING   …        …        …      …        │
│    6    8     20     PENDING                                     │
│    7    8     30     PENDING                                     │
│    8   12     20     SKIP                                        │
│    9   12     30     PENDING                                     │
└──────────────────────────────────────────────────────────────────┘
```

### Run buttons

| Button | What it does |
|--------|-------------|
| **▶ Run All** | Runs every PENDING row in order. DONE and SKIP rows are ignored. |
| **Run Selected** | Select rows with click/Ctrl+click, then press this to run only those rows. |
| **⏹ Stop after case** | Graceful stop — finishes the currently running case then halts. Re-run to resume; DONE rows are skipped automatically. |
| **☑ Retry FAILED** | When ticked, FAILED rows are added back to the queue when you click Run All. |
| **Max cases** | Set to 1 for a single-case smoke test. "all" (value 0) means no limit. |

### Right-click context menu

| Action | When to use |
|--------|-------------|
| **Toggle SKIP** | Exclude a row from the batch without deleting it. Toggle again to re-include. |
| **Re-queue (clear status)** | Clears DONE or FAILED status so the row runs again. Use after fixing a geometry issue. |

---

## 7. Live monitor

Click the **Monitor** tab in the right dock to watch the active case. Every stage updates in real time as the engine progresses.

```
┌ Monitor dock — case 3/8 ─────────────────────────────────────────┐
│                                                                   │
│  Case 3/8 — r005_aoa4_v30              AOA 4°  V 30 m/s          │
│                                                                   │
│  [✓ Geo+Mesh]→[✓ Fluent]→[✓ Setup]→[✓ Init]→[▶ Solve]→[ Extract] │
│                                                                   │
│  ████████████████████░░░░░░░░░  74%                              │
│                                                                   │
│  iter 742   CL= 0.48312   CD= 0.02184                            │
│                                                                   │
│  ┌────────────────────── CL ───────── CD ──────────────────┐    │
│  │  CL   ╭───────────────────                                │    │
│  │  CD      ╭─────────────────                               │    │
│  └──────┬──────┬──────┬──────┬──── iteration ─────────────┘   │
│        100    200    300    400                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Reading the monitor

| Element | Meaning |
|---------|---------|
| Stage chips | **Blue** = currently active · **Green** = done · **Teal** = cached (mesh reused, WB skipped) · **Red** = failed |
| Progress bar | Weighted: Geo+Mesh = 0–25%, Solve = 25–95%, Extract = 95–100% |
| iter N · CL= · CD= | Live values from the current chunk. Updated every ~100 iterations. |
| CL/CD plot | Convergence history. Flat tail = the solver has converged. The engine declares convergence when both CL and CD are flat within tolerance. |

> 💡 **What "converged" means:** The engine uses **force flatness**, not residuals. It checks that CL and CD change by less than a threshold over the last 50 samples. You'll see `Converged at iteration N` in the Log when it stops early — this is correct behaviour.

---

## 8. Results tab and charts

### Results table
Click the **Results** tab to see the full dataset. Click any column header to sort. Click a row to select that case (the Monitor and Images panels update). Click **Export CSV** to save the entire table.

### Charts tab — interactive polars

Three built-in presets cover the most common aero plots:

| Preset | X | Y | Color by | What it shows |
|--------|---|---|----------|--------------|
| **CL vs AOA** | AOA | CL | Velocity | Lift curve slope — should rise with AOA up to stall |
| **Drag polar** | CD | CL | AOA | Classic polar — lower-left = efficient |
| **L/D vs V** | Velocity | L/D | AOA | Aerodynamic efficiency by speed |

You can also set any **X / Y / Color by** combination manually using the dropdowns. **Hover over any point** to see the case ID and exact values. **Export PNG** saves a high-resolution chart image.

> ⚠️ **Current note — inverted AOA:** If your study shows CL *decreasing* with AOA and negative L/D, this is a **geometry rotation sign issue** in DesignModeler (positive P1 rotates nose-down instead of nose-up). The charts and data are correct — the sign convention just needs fixing. Open the Rotate body operation in DM, flip the axis direction, re-export `baseline.cas.h5`, and re-run.

### Statistics dock (bottom)
Shows count/mean/std/min/max for every output metric across all DONE cases, plus a headline **Best L/D** case. Visible alongside the Log in a tabbed dock — click **Statistics** to bring it forward.

---

## 9. Images and artifacts

The **Images** tab lets you browse every image file in a case's artifact folder — geometry screenshots, mesh previews, pressure and velocity contours.

### Step 1 — Select a case
Use the **Case dropdown** at the top to pick any case, or click a row in the Queue/Results table — the dropdown updates automatically.

### Step 2 — Browse thumbnails
Thumbnails appear on the left. Real ANSYS runs (with `capture_images: true`) generate 4 images per case:
- `geometry.png` — wireframe view of the wing
- `mesh.png` — surface mesh with black edges
- `pressure_contour.png` — static pressure on the wall
- `velocity_contour.png` — velocity magnitude on the wall

### Step 3 — Zoom and pan
- **Scroll wheel** to zoom in/out
- **Drag** to pan
- Press **Fit** to reset the view

### Step 4 — Open the folder
Click **Open folder** to see all case artifacts in Windows Explorer: `transcript.trn`, `cfdauto_history.out`, `result.json`, `case.log`, and any exported images.

> 💡 **Enabling real contour images:** To capture actual pressure/velocity contours from Fluent, open `config\config.yaml` and set:
> ```yaml
> fluent:
>   capture_images: true
> ```
> This triggers an experimental step after convergence. If it fails for any reason, the case still completes normally.

---

## 10. Edit experiments

Click the **Parameters** tab in the right dock (next to Queue and Monitor). Click any row in the Queue first to load it.

> ⚠️ **Lock rule:** Inputs can only be edited on rows that have **not produced results yet** (status PENDING, FAILED, or SKIP). Rows with status DONE show their values as read-only to protect provenance.

### Step 1 — Select a pending row in the Queue
Click the row. The Parameters panel loads its current AOA and Velocity values.

### Step 2 — Change the values
Adjust the **AOA [deg]** and **Velocity [m/s]** spinboxes (and any WBP parameter columns if present).

### Step 3 — Click Apply changes
The workbook is saved atomically. The Queue table updates immediately.

---

## 11. Add experiments

The **Add experiment** section in the Parameters panel adds new rows to the schedule without opening Excel.

| Button | What it does |
|--------|-------------|
| **＋ Add row** | Appends a new row with the AOA and Velocity values you've set in the spinboxes. Status is PENDING. |
| **Duplicate selected** | Copies the currently selected row (same AOA, velocity, and any extra parameters) as a new PENDING row. |

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
Then click **Reload Project** in the toolbar.

---

## 13. Panel reference guide

| Panel | Location | Purpose |
|-------|----------|---------|
| **Dashboard** | Central tab (default) | Status cards, overall progress, L/D chart, recent events, pipeline mirror |
| **Results** | Central tab | Full sortable dataset table · Export CSV |
| **Charts** | Central tab | X/Y/colour interactive plots · presets · hover · Export PNG |
| **Images** | Central tab | Browse and zoom case artifact images |
| **Explorer** | Left dock | Project tree: config, schedule, baseline case, all case folders |
| **Queue** | Right dock (top) | Schedule table + run controls + right-click actions |
| **Parameters** | Right dock (tab) | Edit inputs for selected row · add/duplicate rows |
| **Monitor** | Right dock (bottom) | Live pipeline stages + progress + CL/CD convergence plot |
| **Log** | Bottom dock (tab) | Full engine log stream — same as the old terminal output |
| **Statistics** | Bottom dock (tab) | Descriptive stats for all DONE cases + best L/D headline |

> 💡 **Rearranging panels:** Drag any dock by its title bar to move it. Panels can be tabbed together by dropping one on top of another. Use **View → Reset layout** to restore the default positions.

---

## 14. Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `F5` | Run All (start a batch) |
| `Shift+F5` | Stop after current case |
| `Ctrl+O` | Open Project |
| `Ctrl+R` | Reload Project (re-reads config + workbook) |
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
Close the Workbench GUI before running. Only one Workbench instance can have a project open at a time. Check the `runs\cases\<id>\wb_stdout.log` file for the actual error (visible in Explorer dock → double-click the file).

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

**Slipstream v0.8 · Apache-2.0 · Engine: cfdauto · GUI: PySide6 + pyqtgraph · No telemetry · No cloud required**
