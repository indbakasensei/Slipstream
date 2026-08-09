# Slipstream Neo — UI Design System

**Status: v2.2-dev, UX Milestone 2 (Queue + Charts).** This document defines Slipstream's
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
