# Slipstream v1.0 Product Backlog

**Scope:** this backlog covers only the work needed to reach a stable, well-documented **v1.0**. It intentionally excludes everything in the Blueprint's post-v1.0 horizon — 3D visualization, the DuckDB analytics platform, AI/local-LLM features, the plugin ecosystem, multi-worker/LAN/HPC distributed execution, the web dashboard, and the enterprise-optional layer. Those remain valid long-term direction (see `docs/CFD_PLATFORM_BLUEPRINT.md` §12–§16) but are out of scope here.

**Sources used:**
- `README.md` — current implementation, CLI/GUI reference, and its own "Roadmap → v1.0 (next)" section
- `docs/CFD_PLATFORM_BLUEPRINT.md` — long-term vision, Feature Matrix (§5), Version Roadmap (§13), Risk Analysis (§17)
- Direct inspection of the current repository (`cfdauto/`, `gui/`, `tools/`, `tests/`, `.github/workflows/`) — this repo does not contain separate "Gap Analysis," "Feature Dependency Graph," or "Project Inventory" documents, so that analysis is folded into the Status/Dependencies columns below rather than produced as standalone artifacts.

**Note on a scope conflict between sources:** the Blueprint's own "v1.0 — Slipstream Engine" section (§13) describes a larger rewrite (event protocol, SQLite-as-authority, PyInstaller packaging, HTML/PDF report engine, DOE generators) that was never carried out — the repository instead shipped a different, smaller v0.9 (M1/M2/M3) and defines its own, narrower "v1.0 (next)" list directly in `README.md`. Since the README reflects what actually exists today, **this backlog follows the README's v1.0 definition as authoritative** and uses the Blueprint only for vocabulary, architecture context, and dependency reasoning — not to pull forward its larger v1.0 scope (report engine and DOE generators in particular are explicitly deferred there and remain out of scope here).

**Status legend:** `Complete` — implemented and in the current codebase · `Partial` — implemented but incomplete, experimental, or not yet reliable enough for a v1.0 GA claim · `Planned` — not yet implemented, explicitly named as v1.0 scope in the README or directly implied by it.

---

## Table of contents

1. [Epic 1 — Study Execution Engine](#epic-1--study-execution-engine)
2. [Epic 2 — Environment Diagnostics & Physics Safety](#epic-2--environment-diagnostics--physics-safety)
3. [Epic 3 — Live Telemetry & Monitoring](#epic-3--live-telemetry--monitoring)
4. [Epic 4 — Data Provenance (SQLite Ledger)](#epic-4--data-provenance-sqlite-ledger)
5. [Epic 5 — Desktop GUI Shell](#epic-5--desktop-gui-shell)
6. [Epic 6 — Command-Line Interface & Automation](#epic-6--command-line-interface--automation)
7. [Epic 7 — Validation & Trust](#epic-7--validation--trust)
8. [Epic 8 — Documentation & Onboarding](#epic-8--documentation--onboarding)
9. [Epic 9 — Quality & Reliability Hardening](#epic-9--quality--reliability-hardening)
10. [Backlog summary table](#backlog-summary-table)

---

## Epic 1 — Study Execution Engine

The core automation loop: turn an Excel schedule into a sequence of Workbench + Fluent runs, safely, resumably, and without wasting compute on cases that don't need to re-run.

### 1.1 Excel-Driven Parametric Scheduling
- **Description:** Reads AOA/velocity/`WBP:`-prefixed extra parameter rows from the user's workbook, writes results back into the same layout (openpyxl, format-preserving), and treats the Status column as the run state machine.
- **Priority:** Critical
- **Status:** Complete
- **Dependencies:** None (foundational)

**User stories**
- As an engineer, I want to define my parameter sweep as rows in a spreadsheet I already know how to use, so that I don't have to learn a new configuration language to run a study.
- As an engineer, I want to add a new design variable by adding a `WBP:<name>` column, so that I can extend a study without any code changes.

### 1.2 Resume-Safe Crash Recovery
- **Description:** Status-column state machine (PENDING/RUNNING/DONE/FAILED/SKIP), single-instance lock file with dead-PID reclaim, and per-case `result.json` mirroring so a result is never lost even if the workbook is locked.
- **Priority:** Critical
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer, I want to kill the process at any point in an overnight batch and simply restart it, so that a crash costs me minutes, not hours of recomputation.
- As an engineer, I want rows left `RUNNING` by a crash to be automatically re-queued, so that I don't have to manually audit the spreadsheet after every interruption.

### 1.3 Geometry/Mesh Caching
- **Description:** Caches generated Fluent meshes by geometry key (AOA + extra WB parameters) so Workbench is skipped for rows that only vary velocity.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer, I want rows that only change velocity to reuse the existing mesh, so that a velocity sweep at one AOA doesn't cost N full re-meshes.

### 1.4 Mock Mode (ANSYS-free demo/dev)
- **Description:** Dependency-free mock Workbench/Fluent backends that fabricate realistic results, driving the entire pipeline (GUI and CLI) without ANSYS installed.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1, 1.2

**User stories**
- As a new user, I want to see the entire application working end-to-end without installing ANSYS, so that I can evaluate Slipstream before committing to a real setup.
- As a contributor, I want the test suite and CI to run without a licensed ANSYS install, so that I can verify my changes on any machine.

### 1.5 License-Lockout Cascade Detection
- **Description:** Halts the batch after 3 consecutive Fluent launch failures (the signature of a Student-license token lockout) instead of burning through the remaining queue.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 1.1, 1.2

**User stories**
- As an engineer on ANSYS Student, I want the batch to stop itself after repeated launch failures, so that I don't come back to 25 failed cases from a single stuck license token.

### 1.6 Multi-Version PyFluent Compatibility
- **Description:** Version-tolerant adapters absorbing API differences across Fluent 24, 25, and 26.1 (result extraction, UTF-8/UTF-16 transcript handling, stale history-file cleanup).
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer upgrading ANSYS versions, I want the same config and schedule to keep working, so that an ANSYS point-release doesn't force a rewrite of my study.

### 1.7 Contour Image Capture Hardening
- **Description:** Per-case pressure/velocity contour PNG capture. Currently shipped but marked `EXPERIMENTAL` in `config.py` ("version-fragile" — failures are logged and swallowed rather than raising) rather than a fully supported v1.0 capability.
- **Priority:** Medium
- **Status:** Partial
- **Dependencies:** 1.6

**User stories**
- As an engineer, I want image capture failures to be visible and diagnosable (not just silently absent), so that I can trust whether a case's contour PNGs are missing because of a real problem or by design.
- As an engineer, I want `capture_images` to work reliably across the Fluent versions Slipstream already supports, so that I can rely on it for every case in a study, not just some.

---

## Epic 2 — Environment Diagnostics & Physics Safety

Catches the two classes of mistake that cost the most real debugging time: a broken ANSYS/Fluent/Excel environment, and a physically unreasonable study definition.

### 2.1 `doctor` Environment Diagnosis
- **Description:** 14-check environment diagnosis (ANSYS paths, version pairing, licenses, locks, mesh cache health, orphaned processes, Python/GUI dependency stack) with a PASS/WARN/FAIL table and a CI-friendly exit code.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1, 1.2

**User stories**
- As an engineer, I want a single command that tells me exactly what's wrong with my setup, so that I don't have to decode an ANSYS stack trace to find a version-mismatch typo.
- As an engineer, I want `doctor` to catch a stale lock file left by a crash, so that I know it's safe to just rerun instead of hunting for a lock file to delete by hand.

### 2.2 Physics Pre-flight Linter
- **Description:** Pre-flight checks (post-stall AOA, Mach-limit violations, placeholder/default reference values, Student core-cap) run before a batch starts, surfaced in the CLI, GUI dry-run, and `doctor`.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer, I want to be warned before a 20-case overnight batch that half my AOA values are past stall for a RANS model, so that I don't waste a night of compute on physically meaningless results.

---

## Epic 3 — Live Telemetry & Monitoring

Real-time visibility into a running solve, and the recorded history that makes a converged (or diverged) case explainable after the fact.

### 3.1 Per-Iteration Telemetry Tap
- **Description:** Thread-safe background poller streaming CL/CD and residuals during a solve, with sub-chunk iteration for smooth updates.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.6

**User stories**
- As an engineer, I want to see CL/CD and residuals update live while a case solves, so that I can catch a diverging case early instead of discovering it 20 minutes later.

### 3.2 Live Residuals/Force Plots (GUI)
- **Description:** Tabbed Forces + Residuals plots (log-y residuals) in the GUI's Live Monitor, driven by the telemetry tap.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 3.1, 5.3

**User stories**
- As an engineer running the GUI, I want live convergence plots for the case currently solving, so that I can watch a batch progress without tailing a log file.

### 3.3 Transcript Encoding Auto-Detection
- **Description:** UTF-8 / UTF-16 LE / UTF-16 BE auto-detection for Fluent transcripts (Fluent 26.1 on Windows writes UTF-16).
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 3.1

**User stories**
- As an engineer on the latest ANSYS release, I want residual parsing to keep working regardless of transcript encoding, so that a Fluent point-release doesn't silently blank out my residuals plot.

---

## Epic 4 — Data Provenance (SQLite Ledger)

Every batch, case, and iteration recorded with config-hash provenance, so any result can be explained or diffed later. Excel stays the human-facing schedule; the ledger adds the audit trail.

### 4.1 Batch/Case/Iteration Ledger Schema
- **Description:** SQLite database (`runs/slipstream.db`) recording studies, config snapshots (hashed), batches, cases, and per-iteration telemetry — additive and non-fatal (a ledger failure never fails the batch).
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1, 1.2, 3.1

**User stories**
- As an engineer, I want every run's exact configuration recorded automatically, so that I can answer "what changed since the run that worked" without relying on memory.

### 4.2 Config-Hash Provenance & Diff
- **Description:** SHA-256 hash of the effective config recorded per batch; `diff-config` shows exactly which settings differ between two batches.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 4.1

**User stories**
- As an engineer, I want to diff today's broken run against yesterday's good run in one command, so that I can find the setting that silently drifted (a wrong `aoa_scale`, a mismatched `product_version`) in seconds instead of hours.

### 4.3 GUI Study Analytics Panel
- **Description:** A GUI panel backed by the SQLite ledger that lets a user browse past studies/batches and re-plot any historical case — explicitly named in the README's v1.0 roadmap ("Study analytics panel in the GUI (SQLite-backed, re-plot any past case)"). No GUI panel currently reads from the ledger; the existing Charts/Stats/Results panels operate on the current in-memory (Excel-derived) dataset only.
- **Priority:** High
- **Status:** Planned
- **Dependencies:** 4.1, 4.2, 5.6, 5.7

**User stories**
- As an engineer, I want to browse and re-plot the results of a study I ran last month without re-opening its original Excel file, so that historical comparisons don't depend on me keeping every workbook around.
- As an engineer, I want to compare two past batches' headline metrics side by side in the GUI, so that I don't have to hand-craft a SQL query against the ledger for a routine comparison.

---

## Epic 5 — Desktop GUI Shell

The PySide6 desktop application: the primary day-to-day interface for defining, running, and reviewing a study.

### 5.1 Project Explorer & Dashboard
- **Description:** Config/schedule/baseline browser and status-card dashboard (progress, live L/D chart, recent events, pipeline mirror).
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer, I want an at-a-glance view of how many cases are done, running, and failed, so that I can judge overnight-batch health in five seconds.

### 5.2 Queue Management
- **Description:** Live colour-coded schedule table with Run All / Run Selected / Stop / Retry FAILED.
- **Priority:** Critical
- **Status:** Complete
- **Dependencies:** 1.1, 1.2

**User stories**
- As an engineer, I want to stop a batch after the current case and retry only the failed rows, so that I can recover from a bad row without re-running everything that already succeeded.

### 5.3 Live Monitor Panel
- **Description:** Pipeline stage chips, weighted progress bar, and the tabbed Forces/Residuals plots for the case currently running.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 3.1, 3.2

**User stories**
- As an engineer, I want to see which pipeline stage (meshing, launching, solving) a case is in right now, so that a long-running case doesn't look indistinguishable from a hung one.

### 5.4 Parameters Editor
- **Description:** Edit AOA/velocity/WBP columns for any PENDING row directly in the GUI; add or duplicate rows.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 1.1, 5.2

**User stories**
- As an engineer, I want to add a new experiment row from the GUI, so that I don't have to switch to Excel mid-session to extend a study.

### 5.5 Results Table & CSV Export
- **Description:** Sortable results table with CSV export.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 1.1

**User stories**
- As an engineer, I want to export finished results to CSV, so that I can hand them to a colleague who doesn't use Slipstream.

### 5.6 Interactive Charts Panel
- **Description:** CL-vs-AOA, drag polar, and L/D-vs-V presets plus custom X/Y/colour selection, hover-identify, PNG export.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 5.5

**User stories**
- As an engineer, I want to build a drag polar from my current study without leaving the app, so that I don't have to hand-build the same chart in Excel every time.

### 5.7 Statistics Dock
- **Description:** Mean/std/min/max per metric plus a best-L/D headline.
- **Priority:** Low
- **Status:** Complete
- **Dependencies:** 5.5

**User stories**
- As an engineer, I want a quick summary of the best-performing case in a study, so that I don't have to scan the whole results table by eye.

### 5.8 Image Browser
- **Description:** Thumbnails plus zoom/pan viewer for per-case geometry/mesh/pressure/velocity contour PNGs.
- **Priority:** Low
- **Status:** Complete
- **Dependencies:** 1.7

**User stories**
- As an engineer, I want to browse contour images for every case in one panel, so that I don't have to open each case's artifact folder individually.

### 5.9 Mock-Mode Visual Indicators
- **Description:** Orange banner, toolbar highlight, and `[MOCK MODE]` title bar text so mock mode is never mistaken for a real run.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 1.4

**User stories**
- As an engineer, I want it to be visually unmistakable when I'm looking at fabricated mock data, so that I never mistake a demo result for a real one.

---

## Epic 6 — Command-Line Interface & Automation

The headless entry point the engine is built around — every GUI action is also a CLI-scriptable one.

### 6.1 Core CLI Commands
- **Description:** `gui`, `doctor`, `run` (`--dry-run`, `--max-cases`, `--retry-failed`, `--config`), `wb-info`, `init-template`.
- **Priority:** Critical
- **Status:** Complete
- **Dependencies:** 1.1, 1.2, 2.1

**User stories**
- As an engineer, I want to run a full study from a terminal with no GUI involved, so that I can script Slipstream as part of a larger automated workflow.
- As an engineer, I want to preview what a run would do with `--dry-run`, so that I can catch a bad schedule before committing compute time.

### 6.2 Ledger Query CLI
- **Description:** `studies`, `batches [--study NAME]`, `query "<SQL>"` (read-only), `diff-config`, `export-study` commands against the SQLite ledger.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** 4.1, 4.2

**User stories**
- As an engineer, I want to export every case in a study to CSV from the command line, so that I can feed results into another tool's pipeline without touching the GUI.
- As a power user, I want to run an arbitrary read-only SQL query against the ledger, so that I can answer a one-off question the built-in commands don't cover.

### 6.3 Continuous Integration Pipeline
- **Description:** GitHub Actions workflow running the full test suite on Ubuntu + Windows across Python 3.11/3.12 with offscreen-Qt GUI tests. **Already implemented** (`.github/workflows/tests.yml`) — this resolves the item listed as still-pending in the README's own "v1.0 (next)" roadmap section, which appears to be stale relative to the current repository state.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.4, 9.1

**User stories**
- As a contributor, I want every pull request to be automatically tested on both Windows and Linux, so that a platform-specific regression is caught before merge, not after.

---

## Epic 7 — Validation & Trust

Proof that the engine produces physically credible results on more than one geometry — the "portfolio proof point" the README's v1.0 roadmap calls for.

### 7.1 NACA 0012 Validation Case
- **Description:** A second, publicly-documented geometry (NACA 0012) set up as a bundled validation study, with results compared against published polar data — named directly in the README's v1.0 roadmap ("NACA 0012 validation as a second-geometry portfolio proof point"). No NACA-related project, config, or geometry currently exists in the repository.
- **Priority:** High
- **Status:** Planned
- **Dependencies:** 1.1–1.6, 2.2, 3.1

**User stories**
- As a prospective user evaluating Slipstream, I want to see a published, checkable validation case (not just the author's own wing geometry), so that I can trust the engine's aerodynamic results before pointing it at my own project.
- As an engineer, I want a second working example project bundled with the repository, so that I have a template to copy from when setting up a new geometry.

---

## Epic 8 — Documentation & Onboarding

Getting a new user (or contributor) productive without needing to ask the author questions directly — the README's v1.0 roadmap calls this out as "README/USAGE/CONTRIBUTING polish."

### 8.1 README Quickstart & Reference
- **Description:** Installation, 30-second quickstart, GUI/CLI reference, full configuration reference, Excel schedule format, ledger reference, architecture overview, troubleshooting matrix, and roadmap.
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** None

**User stories**
- As a new user, I want a single document that gets me from `git clone` to a running mock-mode demo, so that I can evaluate Slipstream in minutes.

### 8.2 Dedicated Usage Guide
- **Description:** A standalone `USAGE.md` (or equivalent) going deeper than the README's quickstart into real (non-mock) study setup and day-to-day operation — named alongside "README" and "CONTRIBUTING" in the v1.0 roadmap. No separate usage document currently exists (`docs/slipstream_tutorial.md` covers the GUI walkthrough specifically; a dedicated usage reference is distinct from that).
- **Priority:** Medium
- **Status:** Planned
- **Dependencies:** 8.1, 8.4

**User stories**
- As an engineer setting up my first real (non-mock) study, I want a task-oriented usage guide that goes beyond the README's quickstart, so that I'm not reverse-engineering workflow details from the config reference alone.

### 8.3 Contributing Guide
- **Description:** A standalone `CONTRIBUTING.md` — currently, contribution guidance (branching, test requirements, code style) lives only as a short section inside `README.md`.
- **Priority:** Low
- **Status:** Planned
- **Dependencies:** 8.1, 9.1

**User stories**
- As a prospective contributor, I want a dedicated contributing guide with clear expectations (tests, style, PR process), so that I know what's expected before I open a pull request.

### 8.4 Slipstream Tutorial (GUI Walkthrough)
- **Description:** Full GUI walkthrough with troubleshooting, available as both HTML and Markdown (`docs/slipstream_tutorial.{html,md}`).
- **Priority:** Medium
- **Status:** Complete
- **Dependencies:** Epic 5

**User stories**
- As a new GUI user, I want a guided walkthrough of every panel, so that I don't have to discover the interface by trial and error.

---

## Epic 9 — Quality & Reliability Hardening

Non-functional work protecting the guarantees the rest of this backlog depends on — directly reflects the Blueprint's philosophy that provenance and "never lose a result" are platform invariants, not features (Blueprint §2, P3/P8).

### 9.1 Core Utility Test Coverage
- **Description:** Behavioral test coverage for the configuration loader, Excel manager, run-state/crash-recovery, and environment-diagnosis modules (retry/lock/resume/validation paths). **Complete** as of the most recent hardening pass — 69/69 tests passing, covering `config.py`, `excel_manager.py`, `state.py`, and the pure-logic checks in `doctor.py`.
- **Priority:** High
- **Status:** Complete
- **Dependencies:** 1.1, 1.2, 2.1

**User stories**
- As a contributor, I want the crash-recovery and Excel-locking logic to have direct test coverage, so that a future refactor can't silently break the "never lose a result" guarantee without a test failing.

### 9.2 Engine Core Test Coverage
- **Description:** The two largest and most complex modules in the codebase — `fluent_controller.py` (~1,070 lines: PyFluent adapters, solve loop, convergence, image capture) and `orchestrator.py` (~440 lines: the main run loop, cascade detector, ledger writes) — currently have no dedicated unit tests; coverage is indirect, via the mock-mode end-to-end pipeline tests only.
- **Priority:** High
- **Status:** Planned
- **Dependencies:** 9.1

**User stories**
- As a contributor, I want the version-tolerant Fluent adapters to have direct regression tests against captured real payloads, so that an ANSYS point-release doesn't silently reintroduce a bug the mock backend can't detect.

### 9.3 Repository Hygiene
- **Description:** Small, low-risk cleanup items explicitly deferred during recent hardening work — most concretely, an exact duplicate diagnostic script present in two locations (`cfdauto/inspect_fluent_mesh_api.py` and `tools/inspect_fluent_mesh_api.py`).
- **Priority:** Low
- **Status:** Planned
- **Dependencies:** None

**User stories**
- As a contributor, I want no duplicate, unreferenced files in the engine package, so that I don't waste time figuring out which copy is authoritative.

---

## Backlog summary table

| Epic | Feature | Priority | Status |
|---|---|---|---|
| 1. Execution Engine | 1.1 Excel-Driven Parametric Scheduling | Critical | Complete |
| 1. Execution Engine | 1.2 Resume-Safe Crash Recovery | Critical | Complete |
| 1. Execution Engine | 1.3 Geometry/Mesh Caching | High | Complete |
| 1. Execution Engine | 1.4 Mock Mode | High | Complete |
| 1. Execution Engine | 1.5 License-Lockout Cascade Detection | Medium | Complete |
| 1. Execution Engine | 1.6 Multi-Version PyFluent Compatibility | High | Complete |
| 1. Execution Engine | 1.7 Contour Image Capture Hardening | Medium | Partial |
| 2. Diagnostics & Safety | 2.1 `doctor` Environment Diagnosis | High | Complete |
| 2. Diagnostics & Safety | 2.2 Physics Pre-flight Linter | High | Complete |
| 3. Telemetry & Monitoring | 3.1 Per-Iteration Telemetry Tap | High | Complete |
| 3. Telemetry & Monitoring | 3.2 Live Residuals/Force Plots (GUI) | High | Complete |
| 3. Telemetry & Monitoring | 3.3 Transcript Encoding Auto-Detection | Medium | Complete |
| 4. Data Provenance | 4.1 Batch/Case/Iteration Ledger Schema | High | Complete |
| 4. Data Provenance | 4.2 Config-Hash Provenance & Diff | Medium | Complete |
| 4. Data Provenance | 4.3 GUI Study Analytics Panel | High | **Planned** |
| 5. GUI Shell | 5.1 Project Explorer & Dashboard | High | Complete |
| 5. GUI Shell | 5.2 Queue Management | Critical | Complete |
| 5. GUI Shell | 5.3 Live Monitor Panel | High | Complete |
| 5. GUI Shell | 5.4 Parameters Editor | Medium | Complete |
| 5. GUI Shell | 5.5 Results Table & CSV Export | Medium | Complete |
| 5. GUI Shell | 5.6 Interactive Charts Panel | Medium | Complete |
| 5. GUI Shell | 5.7 Statistics Dock | Low | Complete |
| 5. GUI Shell | 5.8 Image Browser | Low | Complete |
| 5. GUI Shell | 5.9 Mock-Mode Visual Indicators | Medium | Complete |
| 6. CLI & Automation | 6.1 Core CLI Commands | Critical | Complete |
| 6. CLI & Automation | 6.2 Ledger Query CLI | Medium | Complete |
| 6. CLI & Automation | 6.3 Continuous Integration Pipeline | High | Complete |
| 7. Validation & Trust | 7.1 NACA 0012 Validation Case | High | **Planned** |
| 8. Documentation | 8.1 README Quickstart & Reference | Medium | Complete |
| 8. Documentation | 8.2 Dedicated Usage Guide | Medium | **Planned** |
| 8. Documentation | 8.3 Contributing Guide | Low | **Planned** |
| 8. Documentation | 8.4 Slipstream Tutorial | Medium | Complete |
| 9. Quality & Reliability | 9.1 Core Utility Test Coverage | High | Complete |
| 9. Quality & Reliability | 9.2 Engine Core Test Coverage | High | **Planned** |
| 9. Quality & Reliability | 9.3 Repository Hygiene | Low | **Planned** |

**Remaining work for v1.0 (bolded above):** 4.3 GUI Study Analytics Panel, 7.1 NACA 0012 Validation Case, 8.2 Dedicated Usage Guide, 8.3 Contributing Guide, 9.2 Engine Core Test Coverage, 9.3 Repository Hygiene — plus hardening 1.7 Contour Image Capture out of its current experimental state.
