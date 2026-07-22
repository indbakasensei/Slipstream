# Changelog

All notable changes to Slipstream are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is close to [Semantic Versioning](https://semver.org/) — pre-1.0,
so minor/alpha increments may still include what would be breaking changes
post-1.0. `cfdauto.__version__` (`cfdauto/__init__.py`) is the single
authoritative version source; every version shown in the window title,
status bar, About dialog, and packaging metadata derives from it.

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
