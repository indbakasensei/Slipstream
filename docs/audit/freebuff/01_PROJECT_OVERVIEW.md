# 01 - Project Overview: Slipstream

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## Executive Summary

Slipstream is a local-first desktop CFD study manager automating ANSYS Workbench + Fluent workflows. Excel-driven parametric sweeps, live-streaming simulation monitor, SQLite provenance ledger, and a professional PySide6 desktop UI (Neo v2.2).

At v2.3.0-dev (Phase 8C complete): template-driven architecture, 2 registered templates, 472 tests, zero TODOs, zero cyclic dependencies.

**Codebase:** ~23,756 lines Python (engine 7,970 + GUI 6,921 + tests 8,865). 40 git commits.

---

## 1. Project Purpose

1. **Define** a sweep in Excel (AOA x Velocity x Workbench params)
2. **Run** headlessly with live telemetry
3. **Monitor** convergence via CL/CD and residual plots
4. **Resume** after crashes
5. **Analyze** with post-batch analytics
6. **Compare** against reference datasets

Local-first: no cloud, no telemetry, no account.

---

## 2. Architecture

**Two-Layer:** gui/ (PySide6) -> cfdauto/ (engine) -> platform/ (pure metadata)

**Dependency (strictly enforced):**
- gui/ -> AppState (public API only)
- orchestrator -> execution -> platform (one-way)
- excel_manager -> study_io -> experiment_definition -> platform (one-way)
- platform -> nothing (pure metadata)

**Platform layer:** ParameterDefinition, MetricDefinition, SimulationTemplate, StudyDefinition. Zero runtime, zero Qt.

**Execution framework:** Strategy pattern with registry dispatch. No template branching.

**Runtime models:** Generic ParameterValue/MetricValue stores with legacy accessors.

---

## 3. Code Metrics

| Subsystem | Files | Lines | Largest |
|-----------|-------|-------|---------|
| Engine | 26 | 7,970 | fluent_controller.py (1,070) |
| GUI | 38 | 6,921 | main_window.py (788) |
| Tests | 43 | 8,865 | test_phase8c_excel_generic.py (583) |
| **Total** | **107** | **23,756** | |

---

## 4. Templates

| Template | Params | Metrics | Sweep |
|----------|--------|---------|-------|
| External Aerodynamics | aoa, velocity | CL, CD, L/D, Lift, Drag | 4x2=8 |
| Internal Flow | inlet_velocity, fluid_density, viscosity, pipe_diameter, pipe_length | pressure_drop, reynolds_number, friction_factor | 4x2=8 |

---

## 5. Technology Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11/3.12 |
| GUI | PySide6 + pyqtgraph |
| Excel | openpyxl |
| Data | pandas |
| Config | PyYAML |
| CFD | ansys-fluent-core |
| Packaging | PyInstaller |
| Database | sqlite3 (WAL) |
| Testing | pytest |
| CI | GitHub Actions |

---

## 6. Version History

| Version | Milestone | Tests |
|---------|-----------|-------|
| v0.8.0 | GUI foundation | ~100 |
| v0.9-M1/M2/M3 | Doctor, telemetry, ledger | ~250 |
| v1.0-alpha.1-7 | CI, errors, analytics, projects, packaging | ~300 |
| v1.0.0-rc1 | Release candidate | ~320 |
| v2.0 | Modernized GUI | ~350 |
| v2.2.0-dev | Neo v2.2 (Stages 1-6) | 397 |
| v2.3.0-dev | Phase 8A-8C complete | 472 |

---

## 7. Engineering Principles

1. Information first
2. Beautiful but professional
3. Consistency (one token system)
4. Responsive (correct at every size)
5. Local-first
6. Crash-safe
7. Template-driven
8. Byte-identical guardrails

---

## 8. Remaining Work

| Phase | Description |
|-------|-------------|
| Phase 8D | Generic Analytics |
| Phase 8E | Generic Ledger/Storage |
| Phase 8F | Generic Events+Linter |
| Phase 8G | Plugin System |
| Phase 8H | Internal Flow E2E |

---

*Freebuff Engineering Audit v2.3.0-dev*
