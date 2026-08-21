# 05 - Genericity Audit

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## 1. Occurrence Summary

| Pattern | Total | Domain | Generic | Compat | Docs | Test |
|---------|-------|--------|---------|--------|------|------|
| AOA/aoa/aoa_deg | 206 | 45 | 30 | 65 | 25 | 41 |
| Velocity/velocity | 80 | 20 | 15 | 25 | 10 | 10 |
| CL/cl (as metric) | 95 | 30 | 10 | 20 | 10 | 25 |
| CD/cd (as metric) | 70 | 25 | 8 | 18 | 8 | 11 |
| Lift/lift_n | 50 | 15 | 5 | 15 | 5 | 10 |
| Drag/drag_n | 45 | 15 | 5 | 13 | 5 | 7 |

---

## 2. Classification

- **Domain logic:** Solver extraction, mock physics, aero math (CORRECT)

- **Generic logic:** Platform/template using terms as parameter names (CORRECT)

- **Compatibility:** Legacy accessors, JSON shapes, ColumnMap (INTENTIONAL)

- **Documentation:** Comments, docstrings (CORRECT)

- **Test fixture:** Test data, assertions (CORRECT)

---

## 3. Already Generic (Phase 1-7)
- platform/templates.py, metrics.py, parameters.py
- models.py generic stores
- experiment_definition.py, study_io.py
- gui/param_render.py metadata-driven widgets

## 4. Correctly Domain-Specific (stay)
- fluent_controller.py solver extraction
- mocks.py CL/CD fabrication
- aero.py reference math
- telemetry.py iteration tap
- linter.py physics pre-flight

## 5. Genericization Pending (Phase 8D-8H)
- study_analytics.py hardcoded CL/CD/L-D
- config.py ColumnMap fixed fields
- state.py OUTPUT_COLS
- monitor.py aoa/velocity display
- orchestrator._ledger_finish_case
- excel_manager.py write_result

*This document is part of the Freebuff Engineering Audit.*