# Slipstream Neo — UI Design System

**Status: v2.2-dev, UX Milestone 3 (Workspace Revolution).** This document defines Slipstream's
visual language: the token scales, colour palette, typography, components, and
layout philosophy that every screen is built from. It is the single reference
for "what should this look like." The implementation lives in
[`gui/theme.py`](../gui/theme.py) (tokens + the application-wide stylesheet) and
the shared widgets under `gui/widgets/`.

> **Scope contract.** Neo is a *presentation* layer. It changes how Slipstream
> looks — not what it does. Business logic, `AppState`, controllers, the
> platform, execution, signals/slots, and workflows are frozen. Every public
> widget attribute the app and tests depend on is preserved.

---

## 1. Design philosophy

Slipstream is a professional engineering tool used for long sessions. The
interface takes its cues from **Linear, VS Code, JetBrains IDEs, Fusion 360,
and ANSYS Discovery** — elegant, minimal, high-contrast, information-first. It
is deliberately **not** a gaming / cyberpunk / neon aesthetic.

Four principles:

1. **Information first.** Engineering data is always the focus; chrome is
   quiet and secondary.
2. **Beautiful but professional.** Elegant, minimal, premium — comfortable to
   look at for eight hours.
3. **Consistency.** One spacing system, one type system, one card system, one
   colour system. Panels read tokens; they never invent their own values.
4. **Responsive.** Every screen is correct from the minimum window size to
   fullscreen. Nothing clips, nothing disappears.

---

## 2. Spacing scale

A single 4-based scale, used for every margin, padding, and gap:

| Token | px | Typical use |
|---|---|---|
| `SPACE_XS` | 4 | icon/label gaps, tight stacks |
| `SPACE_SM` | 8 | control gaps, list item padding |
| `SPACE_MD` | 12 | panel padding, card body gaps |
| `SPACE_LG` | 16 | card padding, section spacing |
| `SPACE_XL` | 24 | between major sections |
| `SPACE_2XL` | 32 | page-level breathing room |
| `SPACE_3XL` | 48 | hero spacing |

Semantic aliases: `CARD_MARGIN` (16), `PANEL_MARGIN` (12),
`SECTION_SPACING` (16), `CONTROL_SPACING` (8).

## 3. Corner radius

| Token | px | Use |
|---|---|---|
| `RADIUS_SM` | 6 | inputs, buttons, chips |
| `RADIUS` | 8 | cards, panels, tables |
| `RADIUS_LG` | 12 | hero cards, dialogs |

## 4. Typography

Family: `Segoe UI / Inter / system-ui`. Monospace: `Cascadia Code / JetBrains
Mono / Consolas` (logs, metric readouts).

| Role | Token | px / weight | Use |
|---|---|---|---|
| Display | `FONT_SIZE_DISPLAY` | 26 / 700 | hero numbers |
| Heading (H1) | `FONT_SIZE_H1` | 19 / 700 | page & card titles |
| Subheading (H2) | `FONT_SIZE_H2` | 13 / 600 | group labels |
| Body | `FONT_SIZE_BODY` | 12 / 400 | default text |
| Small | `FONT_SIZE_SMALL` | 11 | hints, mono log |
| Caption | `FONT_SIZE_CAPTION` | 10 / uppercase | metadata labels |
| Stat | `FONT_SIZE_STAT` | 26 / 700 | stat-card numbers |

Applied via QLabel properties: `display`, `h1`, `h2`, `caption`, `hint`,
`stat`, `metric`.

## 5. Colour tokens

A layered dark palette — an elevation ladder plus one restrained accent and
semantic status hues. High enough contrast for readability and accessibility.

**Surfaces (elevation ladder):**

| Token | Hex | Layer |
|---|---|---|
| `BG_WINDOW` | `#17181b` | app background |
| `BG_PANEL` / `SURFACE` | `#1d1f23` | docks, sidebar, toolbar |
| `BG_FIELD` | `#212429` | inputs, tables, plots |
| `BG_CARD` | `#202226` | elevated cards |
| `BG_ELEVATED` / `SURFACE_ELEVATED` | `#282b31` | menus, popovers |
| `BG_HOVER` / `BG_PRESSED` | `#2b2e34` / `#323640` | interaction states |

**Lines & text:** `BORDER` `#31343b`, `BORDER_STRONG` `#454a54`, `GRID`
`#282b31`; `TEXT` `#e4e6eb`, `TEXT_DIM` `#9aa1ad`, `TEXT_FAINT` `#697079`.

**Accent & status:** `ACCENT` `#5b8cff` (+ `ACCENT_HOVER`, `ACCENT_DIM`),
`SUCCESS` `#3fbf7f`, `WARNING` `#e8a33d`, `ERROR` `#e5534b`, `INFO` `#4fb3d9`.
`FOCUS` = accent, `SELECTION` = `ACCENT_DIM`.

Status vocabulary (`STATUS_COLORS`) is shared by the queue, pipeline chips,
stat cards, and the monitor status chip so a state reads the same colour
everywhere. Chart series use a tuned 8-colour categorical set (`CHART_SERIES`).

## 6. Components

- **Card** (`gui/widgets/card.py`) — the one elevated surface: optional header
  (title + caption + right-side accessory) over a `body` content area. Same
  radius, border, padding everywhere. Used by the Monitor (and available to
  the Dashboard and Parameters).
- **StatCard** (`gui/widgets/cards.py`) — big number + caption for dashboard
  status tiles.
- **StatusChip** (`gui/widgets/status_chip.py`) — a colour-coded pill for a
  state (Idle / Running / Converged / Failed).
- **PipelineWidget** — the Mesh → Workbench → Fluent → Post stage strip.
- **SectionHeader / CollapsibleSection** — consistent section titles and
  toggle-able blocks.

All cards/sections are styled through QSS properties (`card`, `section`,
`hero`, `badge`, `divider`) rather than per-widget stylesheets, so the look is
consistent and themable from one place.

### Stage 2 additions

- **Queue filter pills** (`queueFilter` / `queueFilters`) — compact
  uppercase status tabs (ALL / PENDING / RUNNING / DONE / FAILED); the active
  pill fills with the accent colour. Pure presentation — rows are hidden via
  `setRowHidden`, the data model is never touched.
- **Queue summary line** (`queueSummary` / `queueSummaryValue` /
  `queueSummaryCaption`) — the header's compact status readout ("8 cases ·
  8 done"), computed from `df` on every refresh.
- **Chart toolbar** (`chartToolbar`) — the charts page's grouped axis-control
  strip (X / Y / Colour selectors + presets + export), styled as one
  analytical surface with the same radius/border as panels.
- **Chart empty state** (`chartEmpty`, `chartEmptyTitle`, `chartEmptyHint`) —
  a dashed engineering empty state shown in place of the plot when no DONE
  result data exists.

### Stage 3 additions

- **Parameter name/meta** (`paramName`, `paramMeta`) — QSS for the engineering
  control panel's rich parameter rows: bold display name + uppercase range
  captions.
- **Image surface/meta/empty** (`imageSurface`, `imageMetaCaption`,
  `imageMetaValue`, `imageEmptyTitle`, `imageEmptyHint`) — metadata bar and
  empty state styling for the images workspace.
- **Console surface** (`CONSOLE_BG`, `CONSOLE_TEXT`, `CONSOLE_PROMPT`,
  `[console="true"]`, `[consoleInput="true"]`) — the engineering terminal's
  monospace dark surface with coloured prompt and input bar.

## 7. Layout philosophy

- **Cards group related information.** A screen is a vertical stack (or grid)
  of cards, each answering one question.
- **Responsive floors.** Shared minimums (`MIN_SIDEBAR_WIDTH`,
  `MIN_CENTER_WIDTH`, `MIN_QUEUE_WIDTH`, `MIN_PANEL_WIDTH`, `MIN_PLOT_HEIGHT`,
  `MIN_CONTROL_HEIGHT`) prevent any region collapsing to an unreadable sliver;
  the main splitter is non-collapsible.
- **Scroll, don't clip.** Panels that can overflow (Monitor, Parameters,
  Dashboard) live inside a `QScrollArea` so a short window scrolls rather than
  truncating content.
- **Plots have a height floor** (`MIN_PLOT_HEIGHT`) and expand to fill spare
  space.

## 8. The Monitor (reference implementation)

The Monitor is the fullest expression of the system — five cards:

1. **Current Study** — case title, details, overall progress, a status chip,
   and estimated time remaining.
2. **Pipeline** — the stage strip.
3. **Live Metrics** — iteration, min-residual, and the template's force metrics
   as caption-over-value tiles.
4. **Convergence** — Forces / Residuals plots (tabbed).
5. **Timeline** — a newest-first event feed (mesh generated, solver started,
   convergence, results written, finished).

It renders entirely from engine events; no business logic was added.

## 8a. The Queue (reference implementation — Stage 2)

The Queue is an engineering worklist, not an embedded spreadsheet:

1. **Header row** — section title with a painted icon, a compact status
   summary (total · done · running · pending · failed, computed from `df`),
   and the preserved run controls grouped as one `ToolbarSection`.
2. **Filter pills** — ALL / PENDING / RUNNING / DONE / FAILED status tabs
   implemented entirely through row visibility; the data model is never
   modified, so `table.rowCount()` still reports the full unfiltered count.
3. **The table** — template-driven columns, compact 30 px rows, status cells
   painted as colour-coded badges (`StatusBadgeDelegate`), a soft tint for
   RUNNING rows, `ResizeToContents` + stretched last column.
4. **Empty state** — a full-panel "No simulation cases in queue" message shown
   when the table is empty or a filter hides every row.

Every public attribute, signal, and method (run controls, `columns()`,
`selected_rows()`, context menu) is preserved; the input columns still come
from the runtime `ExperimentDefinition`.

## 8b. The Charts (reference implementation — Stage 2)

The Charts page is the primary analytical workspace — the plot dominates:

1. **Analytical toolbar** — one grouped strip holding the X / Y / Colour
   axis selectors, the study's preset buttons (labels built from the loaded
   template's display names, never literal parameter names), and Export PNG.
2. **The plot surface** — pyqtgraph untouched: `X`/`Y` axis labels from the
   active axes, faint grid, colour-coded series with a legend, hover
   identification.
3. **Empty state** — a dashed "No Result Data / Run a study to populate
   engineering plots" frame shown in place of the plot when there are no DONE
   rows to plot. A `QStackedLayout` toggles between the two.

No analytics were touched; `series_groups` remains the single source of chart
series shared with the Dashboard.

## 8c. Parameters — engineering control panel (Stage 3)

The Parameters dock is an engineering control panel for viewing and editing the
selected experiment's inputs. It remains fully metadata-driven — every editor,
label, range, unit, and default is generated from the active template's
`ParameterDefinition` via `gui.param_render`. No parameter names are hardcoded.

Layout:
1. **Section header** — `SectionHeader("Parameters", icon_name="settings")` with
   a hint line explaining that editors come from template metadata.
2. **Selected experiment** — a `QGroupBox` containing a `QFormLayout` of rich
   parameter rows. Each row has a **label column** (display name + allowed range)
   and a **field column** (spin box + unit/default caption), all built by
   `_build_row()`. The selection caption (`sel_lbl`) shows the active row's
   CaseID and status; locked rows (DONE/FAILED) are disabled. Apply and Skip
   buttons sit below the form with painted icons.
3. **Add experiment** — a parallel `QGroupBox` of the same rich rows for new
   values, with Add Row and Duplicate Selected buttons.

Public API preserved: `sel_box`, `add_box`, `form`, `_sel_rows`, `_add_rows`,
`_wbp_spins`, `_rebuild_wbp()`, `_load_row()`, `_apply()`, `_skip()`, `_add()`,
`_duplicate()`, `_validate()`, `_guard()`, `_scroll`, `minimumWidth`,
and all signals. WBP columns use `plain_spin()` (no metadata bounds) and are
still removed via `form.removeRow(spin)` in `_rebuild_wbp()`.

Design tokens: `paramName` (body weight 600), `paramMeta` (caption uppercase +
letter-spacing) for range / unit / default captions.

## 8d. Images — engineering visualization workspace (Stage 3)

The Images panel is an engineering image inspection workspace for viewing CFD
contour plots, velocity fields, and post-processing artifacts.

Layout:
1. **Section header** — `SectionHeader("Image Viewer", icon_name="images")`.
2. **Toolbar** — case selector combo + refresh / open-folder / fit-to-window
   buttons, all using painted vector icons.
3. **Workspace** — a `QStackedLayout` toggling between:
   - **Workspace (index 0)**: a thumbnail strip (`list`) on the left, a zoomable
     graphics view (`view` + `scene` + `pix_item`) on the right, and a metadata
     bar at the bottom showing filename, pixel dimensions, and file size.
   - **Empty state (index 1)**: a dashed engineering frame with title "No
     Artifacts Yet" and a hint to run a study and select a case.
4. **Path bar** — the full artifact path at the bottom.

`_meta_show()` updates the metadata bar when a new image is loaded;
`_meta_clear()` resets it. `_fmt_size()` formats bytes into human-readable
strings.

Public API preserved: `case_box`, `list`, `scene`, `pix_item`, `view`,
`path_lbl`, `refresh()`, `show_file()`, `image_files()`.

## 8e. Console — engineering command terminal (Stage 3)

The Console is a presentation-only command terminal docked in the bottom panel
(tabbed with Log and Statistics). It maps typed commands to signals that
MainWindow connects to existing public actions — no eval, exec, or backend
access.

Structure:
1. **Header** — "CONSOLE" caption + Clear button.
2. **Terminal** — a `QPlainTextEdit` (property `console="true"`) with 4000-line
   cap, monospace font, coloured log output by level.
3. **Input bar** — `QLineEdit` (property `consoleInput="true"`) with a
   `QCompleter` over sorted command names, and a `slipstream ›` prompt label.

Commands: `help`, `open`, `run`, `stop`, `reload`, `mock on|off|toggle`, `clear`.
Each command is echoed, dispatched, and the result appended to the terminal.
Up/Down arrow keys navigate command history.

Signals emitted by ConsolePanel:
- `openRequested` → `MainWindow._open_dialog`
- `runRequested` → `MainWindow.start_run`
- `stopRequested` → `MainWindow._stop`
- `reloadRequested` → `MainWindow._reload`
- `mockSet(bool)` → `MainWindow._on_mock_toggled`
- `mockToggleRequested` → `MainWindow._toggle_mock`

MainWindow also connects `runStateChanged` → `_console_run_state()`, which
prints "batch running" / "batch idle" status lines to the console.

Design tokens: `CONSOLE_BG` (#141519), `CONSOLE_TEXT` (#c9cdd6),
`CONSOLE_PROMPT` (ACCENT), QSS for `[console="true"]` and `[consoleInput="true"]`.

## 8f. Adaptive Workspace (Stage 5)

Slipstream behaves like a professional engineering workstation: the **primary
engineering task is always visually dominant**, and secondary UI never
permanently starves it of space. This is the *workspace-allocation* layer that
sits on top of the existing `QSplitter` / `QStackedWidget` / `QDockWidget`
architecture — no new docking framework, no floating-window model.

### Panel classification

| Panel | Class | Behaviour |
|---|---|---|
| Dashboard | PRIMARY WORKSPACE | always gets the flexible center space |
| Charts | PRIMARY WORKSPACE + Focus | plot dominates; Focus Mode maximizes it |
| Images | PRIMARY WORKSPACE + Focus | viewer dominates; Focus Mode maximizes it |
| Results | PRIMARY WORKSPACE | full-width table |
| Queue | SECONDARY-COLLAPSIBLE | user-initiated hide/show via the header toggle |
| Parameters | SECONDARY-COLLAPSIBLE | right dock, hidden by default, View-menu toggle |
| Monitor | SECONDARY-COLLAPSIBLE | right dock, hidden by default, View-menu toggle |
| Log / Statistics / Console | UTILITY | bottom docks, View-menu toggle |

### Queue collapse

- The Queue is **visible by default** — existing workflow is unchanged.
- The header's Queue toggle (`queue_btn`, icon = queue) hides it on click; the
  freed horizontal space is reclaimed by the center workspace because the
  splitter gives the center the flexible stretch factor.
- Restoring returns the Queue at its **previous width** (the splitter geometry
  is captured at collapse), never the old fixed 30% rule.
- Collapse is **user-initiated only** — window resizing never hides the Queue.

### Focus Mode

The header's Focus toggle (`focus_btn`, icon = zoom) is presentation-only:

- **Enter** hides Sidebar, Queue, and every dock so the current primary
  workspace (Dashboard / Charts / Images / Monitor) receives the full window.
- **Exit restores the exact previous layout state** — which Queue state
  (visible/collapsed), which sidebar state, and the per-dock visibility map
  (including which tab of a tabified group was raised).
- The tooltip is page-aware: *Focus Charts*, *Focus Images*, *Focus Monitor*,
  *Focus Workspace*. The button is disabled until a project is loaded.
- While Focus is active the Queue toggle is disabled (the Queue is managed by
  Focus Mode) and the focus button reads *"Exit Focus Mode"*.

### State restoration rules

- Queue collapsed before Focus → stays collapsed after Focus exit.
- Queue visible before Focus → returns visible at its previous width.
- Monitor / Parameters / Console open before Focus → return open after exit;
  closed before → stay closed.
- No automatic panel hiding based purely on window resizing.

### Responsive rules

There are **no aggressive automatic breakpoints**. The transition from
"wide with Queue" to "center-only" is driven by the user's Queue toggle, not by
a resize listener. The shared minimum-width floors (`MIN_SIDEBAR_WIDTH`,
`MIN_CENTER_WIDTH`, `MIN_QUEUE_WIDTH`) keep every region usable at narrow
widths; long content scrolls rather than being clipped.

### Scroll behaviour

Unchanged from earlier stages — only naturally-long content scrolls:

- Monitor / Parameters → `QScrollArea`; Queue → native table scrolling;
- Console / Log → `QPlainTextEdit`.
- Dashboard, Charts, Images do **not** scroll the whole page; their content
  scales with the container.

### Public API (additive)

`MainWindow.toggle_queue()` · `MainWindow.queue_collapsed` ·
`MainWindow.toggle_focus_mode()` · `MainWindow.focus_mode` ·
`WorkspaceHeader.queueToggleRequested` · `focusToggleRequested` ·
`set_queue_visible()` · `set_focus_active()` · `set_focus_enabled()` ·
`set_focus_label()`. Every pre-existing attribute, signal, and test contract is
preserved.

Design tokens: `HEADER_TOGGLE_SIZE` (28), QSS role `[headerToggle="true"]`
(compact ghost button, accent-tinted while active).

## 8g. Responsive Workspace Hardening (Stage 6)

Stage 6 is the *stress* layer: every responsive rule from Stage 5 is verified
against a real matrix of window sizes and user sequences, and the layout's
behaviour at the extremes (narrow, short, narrow+short, many docks, 64-row
queues) is locked by an explicit test contract. It adds **no new chrome** —
it hardens the existing allocation rules so nothing clips, crushes, or
auto-hides at any reachable size.

### Responsive rules

There are **no aggressive automatic breakpoints and no resize-listener
reflow.** The window's behaviour is a small set of floors plus Qt's own layout
minimums:

- Every region has a floor: `MIN_SIDEBAR_WIDTH`, `MIN_CENTER_WIDTH`
  (the center workspace is asserted **≥ 300 px** at every matrix cell),
  `MIN_QUEUE_WIDTH`, `MIN_PANEL_WIDTH`, `MIN_DOCK_WIDTH`, `MIN_PLOT_HEIGHT`,
  `MIN_CONTROL_HEIGHT`.
- The main splitter is **non-collapsible** — no region can be squeezed to a
  sliver by resizing.
- Widgets render **at their size hint** rather than being compressed; where
  the hint exceeds the space, the content **scrolls** instead of clipping.
- **Visibility changes only through the user's explicit actions** (Queue
  toggle, Focus Mode, View-menu dock toggles). Window resizing never hides a
  panel.

### Primary workspace protection

The primary engineering task stays visually dominant at every size:

- The center workspace (Dashboard / Charts / Images / Results) holds a
  **flexible stretch factor** in the main splitter and a hard floor, so it
  reclaims every pixel the Queue or a dock frees.
- Collapsing the Queue gives its full width to the center — there is no
  "wide" vs "narrow" mode, just the user's chosen allocation.
- Focus Mode (`8f`) gives the current primary workspace the **entire
  window** (Sidebar, Queue, and every dock hidden) and restores the exact
  prior layout on exit.
- Queue run controls (Run All / Run Selected / Stop) are asserted to **never
  be crushed below their size hint** while the Queue is visible — the most
  safety-critical controls are also the most protected.

### Dock sizing philosophy

Docks are auxiliary and opt-in:

- Parameters, Monitor, and Console are **hidden by default**; opening one
  (View menu, or the dashboard quick actions) docks it on the right with a
  minimum readable width (`MIN_DOCK_WIDTH`).
- Two docks in the same area **split the available width evenly**; a single
  dock takes the full dock area. Both are captured in the visual samples.
- A dock the user opened **stays visible through resizing** — the matrix
  asserts positive, within-window geometry for every opened dock after a
  resize, and no auto-hide.

### Scrolling rules

Only naturally-long content scrolls; the page never clips:

- **Dashboard / Parameters** → `QScrollArea` (a short window scrolls).
- **Queue** → native table scrolling; the table genuinely overflows and
  scrolls at 64 rows on a 1080 px window (verified in the T7 large-queue
  sample).
- **Log / Console** → `QPlainTextEdit`.
- **Charts / Images** → the plot and viewer scale with the container; their
  toolbars are grouped strips that fit constrained widths (verified at
  1000 px).

### Window-size behaviour

Qt clamps any `resize()` below the layout's usable minimum rather than
rendering a broken layout, so the *reachable* sizes are what matter:

- With the default bottom group (Log / Statistics / Console) visible, the
  window clamps at **≈ 773 px** tall (menubar + toolbar + center + bottom
  group + status bar).
- A user on a short screen closes the bottom group (the same View-menu
  toggle as Stage 5); the window then reaches **≈ 555 px**.
- The T6 visual samples cover the honest reachable extremes: normal
  **1480×900**, narrow **1000×700**, short **1400×520** (bottom group
  closed), and narrow+short **1000×520** (bottom group closed).

### Stress-test matrix (T4)

Thirteen cells (A–M) exercise every allocation state against real sizes —
`tests/test_stage6_matrix.py`:

| Cell | Size | State exercised |
|---|---|---|
| A | 1920×1080 | large desktop |
| B | 1480×900 | normal desktop |
| C | 1000×700 | narrow desktop |
| D | 1400×520 | short (request clamps to the window minimum with the bottom group visible) |
| E | 1000×520 | narrow + short (same clamp) |
| F | 1920×1080 | large with full Queue |
| G | 1920×1080 | + Parameters dock |
| H | 1920×1080 | + Monitor dock |
| I | 1920×1080 | + Parameters, Monitor, Console |
| J | 1480×900 | Focus Mode |
| K | 1480×900 → 1000×700 | Focus Mode while resizing |
| L | 1480×900 → 1000×700 | Queue collapsed while resizing |
| M | 1480×900 → 1000×700 | Queue collapse → restore then resize |

Every cell is asserted for: positive within-window geometry, center ≥ 300 px,
no unintended auto-hide, queue controls not crushed, scroll areas present,
and open docks staying visible.

### User-interaction matrix (T5)

One full realistic sequence drives the window through every feature the user
actually touches — `test_user_interaction_sequence`: open project → run mock
batch to completion → collapse Queue → Charts → enter Focus → resize while
focused → exit Focus (exact Stage 5 restoration, Queue still collapsed) →
restore Queue → open Parameters → select a row → resize with the dock open →
open Monitor and Console → Images → back to Dashboard. The invariants above
are asserted at every step.

### Regression guarantees

- The Stage 5 contract suite (`tests/test_adaptive_workspace.py`) is **run
  unchanged** and still passes — Stage 6 never weakens a Stage 5 assertion.
- Stage 5 restoration is re-verified inside the Stage 6 matrix: Focus exit
  restores the exact prior layout, Queue collapse/restore preserves width,
  dock visibility survives resizing.
- The T7 sample-data builders (`_screens/stage6_samples.py`) are locked by
  `tests/test_stage6_samples.py`: each sample must load through the real
  GUI dataset path with its advertised row count, status mix, WBP columns,
  and template — including Internal Flow, which exercises the metadata-driven
  `CaseID` fallback and guarantees the same UI renders both templates.
- The full suite runs offscreen (`QT_QPA_PLATFORM=offscreen`); the sixteen
  Stage 6 screenshots in `_screens/stage6_*.png` are regenerated from the
  live path by `_screens/capture_stage6.py` and are the visual record of
  every matrix cell and data variety.

## 9. Motion & performance

Motion is subtle and cheap: hover/selection/focus state changes and
show/hide toggles — no continuous animation, no expensive effects, no
unnecessary repaints. The stylesheet is applied once at startup
(`apply_theme`); pyqtgraph is configured to match the palette.

## 10. Accessibility

High-contrast text on dark surfaces (primary text `#e4e6eb`), a visible focus
colour on inputs, generous touch targets (`MIN_CONTROL_HEIGHT` 28px), and
readable minimum type sizes. Layout scales with the window and honours the OS
display scaling Qt provides.
