# 01 - Project Overview: Slipstream

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## Executive Summary

Slipstream is a local-first desktop CFD study manager automating ANSYS Workbench + Fluent. Excel-driven sweeps, live telemetry, SQLite ledger, PySide6 UI (Neo v2.2).

v2.3.0-dev: template-driven architecture, 2 templates, 472 tests, zero TODOs, zero cyclic deps.

**Codebase:** ~23,756 lines (engine 7,970 + GUI 6,921 + tests 8,865). 40 commits.

---

## 1. Purpose

1. Define sweep in Excel
2. Run headlessly with telemetry
3. Monitor convergence
4. Resume after crashes
5. Analyze results
6. Compare against references

Local-first: no cloud, no telemetry.

---

## 2. Architecture

Two-Layer: gui/ (PySide6) -> cfdauto/ (engine) -> platform/ (metadata)

Dependency: all one-way. Platform has zero runtime/Qt imports.

---

## 3. Code Metrics

| Subsystem | Files | Lines |
|-----------|-------|-------|
| Engine | 26 | 7,970 |
| GUI | 38 | 6,921 |
| Tests | 43 | 8,865 |
| Total | 107 | 23,756 |

---

## 4. Templates

| Template | Params | Metrics |
|----------|--------|---------|
| External Aero | aoa, velocity | CL, CD, L/D, Lift, Drag |
| Internal Flow | inlet_velocity, fluid_density, viscosity, pipe_diameter, pipe_length | pressure_drop, reynolds, friction_factor |

---

## 5. Tech Stack

| Layer | Tech |
|-------|------|
| Language | Python 3.11/3.12 |
| GUI | PySide6 + pyqtgraph |
| Excel | openpyxl |
| Config | PyYAML |
| CFD | ansys-fluent-core |
| Packaging | PyInstaller |
| DB | sqlite3 (WAL) |
| Testing | pytest |
| CI | GitHub Actions |

---

## 6. Versions

| Version | Milestone | Tests |
|---------|-----------|-------|
| v0.8.0 | GUI foundation | ~100 |
| v0.9-M1/M2/M3 | Doctor, telemetry, ledger | ~250 |
| v1.0-alpha.1-7 | CI, errors, analytics, projects, packaging | ~300 |
| v1.0.0-rc1 | Release candidate | ~320 |
| v2.0 | Modernized GUI | ~350 |
| v2.2.0-dev | Neo v2.2 (Stages 1-6) | 397 |
| v2.3.0-dev | Phase 8A-8C | 472 |

---

## 7. Principles

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