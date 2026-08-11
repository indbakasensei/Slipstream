# Changelog

All notable changes to Slipstream are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is close to [Semantic Versioning](https://semver.org/) — pre-1.0,
so minor/alpha increments may still include what would be breaking changes
post-1.0. `cfdauto.__version__` (`cfdauto/__init__.py`) is the single
authoritative version source; every version shown in the window title,
status bar, About dialog, and packaging metadata derives from it.

## [2.2.0-dev] — Unreleased (development)

> Development version. The Neo v2.2 UI milestone is **feature-complete**
> (Stages 1–6). Platform **Phase 8 remains partial** and is *not* part of
> this release — see [`docs/PLATFORM_ARCHITECTURE.md`](docs/PLATFORM_ARCHITECTURE.md).

### Added — Neo v2.2 UI (Stages 1–6)

- **Neo desktop shell & design system** — a modern, information-first
  engineering interface (tokens, palette, typography, shared card/chip
  components) defined in `docs/UI_DESIGN_SYSTEM.md` and implemented in
  `gui/theme.py`.
- **Dashboard redesign** — status cards, overall progress, live charts, Study
  Overview (per-input range rows), Study Summary, recent events.
- **Monitor redesign** — information-first cards: current study, solver
  pipeline, live metrics, convergence, timeline.
- **Queue redesign** — persistent, colour-coded schedule table with run controls.
- **Charts redesign** — interactive presets plus custom X/Y/colour, hover, PNG
  export.
- **Parameters redesign** — metadata-driven form generated from the active
  template.
- **Images workspace** — thumbnail browser + zoom/pan viewer for case artefacts.
- **Console** — engine-log console panel.
- **Adaptive Workspace (Stage 5)** — user-initiated **Queue collapse** and
  **Focus Mode** (hides the sidebar, Queue, and docks so the current page fills
  the window; exact layout restoration on exit).
- **Responsive workspace hardening (Stage 6)** — dock sizing, flow-layout
  wrapping, and a stress matrix verified offscreen across desktop/narrow/short
  window sizes (16 verified screenshots).

### Added — platform / template work that landed before this release

- **Template-driven architecture** — `cfdauto/platform/` pure-metadata models
  (`ParameterDefinition`, `MetricDefinition`, `SimulationTemplate`,
  `TemplateRegistry`, `StudyDefinition`) and the External Aerodynamics template.
- **Project template selection** — a `runtime.template` config field resolved
  through the registry; new projects pick a template and restore it on load.
- **Internal Flow template + execution strategy** — a second, domain-different
  reference template with an executable (analytical) Internal Flow workflow
  through the same strategy framework.
- **Generic experiment/model improvements** — `ParameterValue`/`MetricValue`
  containers; `Experiment`/`CaseResult` store generically with the airfoil-named
  fields kept as compatibility accessors (byte-identical serialization verified).
- **Template-driven StudyIO / UI behavior** — `StudyIO` maps template metadata
  to/from the spreadsheet; the GUI's parameters, queue, charts, and validation
  render from template metadata.

### Changed

- `cfdauto.__version__` bumped to `2.2.0-dev` — the single authoritative
  version source for the window title, status bar, About dialog, and packaging.

### Status

- **Neo v2.2 UI: feature-complete** (Stages 1–6). 397 tests passing.
- **Platform Phase 8: partial** — the remaining airfoil-shaped identity/write
  paths (`case_id`/`geometry_key`/`validate`, `ColumnMap` output columns,
  ledger schema, orchestrator event payloads, linter dispatch, analytics
  architecture) are scheduled future work, not part of this release.

## [1.0.0-rc1] — Release Candidate 1

### Changed
- Documentation audit across `README.md`, `docs/RELEASE_CHECKLIST.md`,
  `GITHUB_SETUP.md`, and `docs/PRODUCT_BACKLOG.md`: corrected stale test
  counts (33 → 146), one broken internal link, a stale version string in
  an illustrative mockup, and rewrote the README's Roadmap section to
  reflect everything actually shipped since v0.9.
- `cfdauto.__version__` bumped to `1.0.0-rc1`.

### Added
- `docs/RELEASE_NOTES_v1.0.0-rc1.md` — this release's detailed notes.
- `docs/QA_GUIDE.md` — manual verification walkthrough.
- `docs/RELEASE_METADATA.md` — release name, version, supported
  Python/ANSYS/OS versions, primary dependencies, license.
- `CHANGELOG.md` (this file).

## [1.0.0-alpha.7] — Benchmark Validation Framework

### Added
- `tools/validation/compare.py` — deterministic, stdlib-only comparison of
  a Slipstream export against a reference CSV: Mean Absolute Error, Root
  Mean Square Error, and Maximum Absolute Error per metric, written to
  `comparison_summary.json` and `comparison_table.csv`.
- `tools/validation/plots.py` — deterministic CL/CD/L-D comparison plots
  (matplotlib; isolated from the metrics tool via `requirements-validation.txt`).
- `docs/validation/VALIDATION.md` — engineering validation report template.
- `docs/validation/benchmark/` — standard `reference/`/`slipstream/`/`plots/`
  layout for benchmark data (no data checked in yet — placeholders only).
- `docs/RELEASE_CHECKLIST.md` — validation section.

Standalone tooling only — never wired into the runtime engine, CLI, or GUI.

## [1.0.0-alpha.6] — Packaging & Release Infrastructure

### Added
- `build/slipstream.spec` — PyInstaller one-folder Windows build (kept
  one-folder, not one-file, for PySide6/Qt LGPLv3 compliance).
- `build/build.ps1`, `build/clean.ps1`, `build/release.ps1` — build, clean,
  and versioned-release-zip scripts.
- `build/make_version_info.py` — generates the `.exe`'s Windows version
  resource from `cfdauto.__version__`.
- `docs/RELEASE_CHECKLIST.md` — first version of the manual pre-release checklist.
- GUI: a first-run experience — the existing Project Selector now opens
  automatically when no project is loaded at startup, instead of a bare
  empty dashboard.

### Fixed
- `cfdauto.__version__` corrected from a stale `0.9.0.dev3` to
  `1.0.0-alpha.6`, bringing the single source of truth in line with the
  work already shipped.

## [1.0.0-alpha.5] — Project & Study Management

### Added
- `cfdauto/project_manager.py` — project folders (`config/ data/ docs/
  outputs/ runs/` + `project.json`), tolerant metadata loading, and
  recent-projects tracking (`get_user_data_directory()`, overridable for tests).
- `gui/project_selector_dialog.py` — Open Recent / Open Existing / Create
  New, wired into the existing `config.yaml` load flow unchanged.

## [1.0.0-alpha.4] — Study Summary Dashboard Widget

### Added
- `gui/widgets/study_summary_panel.py` — read-only Dashboard widget
  rendering `Orchestrator.current_study_summary` (added as a public,
  read-only property this release): total/successful/failed/retries, best
  L/D, highest lift, lowest drag, fastest convergence, and warnings in a
  fixed, deterministic display order, with a "last updated" timestamp.

## [1.0.0-alpha.3] — Study Analytics

### Added
- `cfdauto/study_analytics.py` — `StudySummary` / `StudyWarning` /
  `WarningCode` and `analyze_study()`: a purely computational, read-only
  post-batch summary (no logging, no Excel writes), computed once at the
  end of every `Orchestrator.run()` call.

## [1.0.0-alpha.2] — Centralized Error Formatting

### Added
- `cfdauto/error_formatting.py` — `format_error()` / `FormattedError`: one
  exception-type-driven explanation format (title, possible reasons,
  suggested next step, and a "need more information?" log/artifact
  pointer), reused by the CLI, GUI dialogs, the orchestrator's per-case
  log, and `doctor`'s unexpected-failure path.

## [1.0.0-alpha.1] — Behavioral Test Hardening

### Added
- Behavioral test coverage for `cfdauto/config.py`, `excel_manager.py`,
  `state.py`, and the pure-logic checks in `doctor.py`.
- `docs/PRODUCT_BACKLOG.md` — v1.0 Epics/Features/User Stories backlog.

## [0.9.0] — Engine Hardening (M1–M3)

### Added
- **M1** — `aoa_scale` config knob (inverted DesignModeler rotation fix),
  `slipstream doctor` (14-check environment diagnosis), physics pre-flight
  linter, mesh-cache corruption hardening.
- **M2** — per-iteration telemetry tap (live CL/CD/residuals), UTF-8/UTF-16
  LE/BE transcript auto-detection, sub-chunk solve iteration, stale
  history-file cleanup, license-lockout cascade detector.
- **M3** — SQLite provenance ledger (studies/configs/batches/cases/
  iterations), config-hash diffing (`diff-config`), ledger query CLI
  (`studies`, `batches`, `query`, `export-study`).

## [0.8.0] — Desktop GUI Foundation

### Added
- PySide6 desktop shell over the existing `cfdauto` engine: Dashboard,
  Project Explorer, Queue, Live Monitor, Parameters editor, Results table,
  Interactive charts, Statistics dock, Image browser, Log console, Mock
  mode with unmistakable visual indicators.
- `EngineWorker` / `EventBus` bridge running the engine on a background
  thread with live event streaming to the UI.
