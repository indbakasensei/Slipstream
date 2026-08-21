# 06 - Testing Audit

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## 1. Overview

| Metric | Value |
|--------|-------|
| Total test files | 43 |
| Total test lines | ~8,865 |
| Claimed passing | 397 |

---

## 2. Tests by Category

### Platform (Phases 1-8C): 14 files

| File | Focus |
|------|-------|
| test_platform.py | Templates, registry, parameters, metrics |
| test_simulation_context.py | Context resolution |
| test_study_definition.py | StudyParameter ordering |
| test_experiment_definition.py | Materialization, validation |
| test_generic_experiment_model.py | ParameterValue/MetricValue stores |
| test_study_io.py | Column resolution, interpret_row |
| test_internal_flow.py | Internal Flow template |
| test_execution_framework.py | Strategy dispatch, mesh caching |
| test_internal_flow_execution.py | Internal Flow execution |
| test_dynamic_ui.py | Metadata-driven UI rendering |
| test_project_template.py | Per-project template selection |
| test_phase8a_generic_identity.py | Template-driven identity/geometry |
| test_phase8b_generic_metrics.py | Generic CaseResult serialization |
| test_phase8c_excel_generic.py | Generic StudyIO output columns |

### GUI / Neo: 13 files

| File | Focus |
|------|-------|
| test_gui_smoke.py | Full GUI smoke test |
| test_adaptive_workspace.py | Queue collapse, Focus Mode |
| test_stage6_matrix.py | 13-cell responsive matrix |
| test_stage6_samples.py | Sample data builders |
| test_ui_foundation.py | Theme, tokens |
| test_sidebar.py | Navigation |
| test_neov2_milestone1.py | Dashboard foundation |
| test_neov2_milestone2.py | Queue + Charts |
| test_neov2_milestone3.py | Parameters + Images + Console |
| test_first_run_experience.py | First-run dialog |
| test_responsive_workspace.py | Responsive behavior |
| test_collapsible_section.py | Collapsible widget |
| test_project_selector_dialog.py | Project selector |

### Engine / Regression: 16 files

test_engine.py, test_v09_m1.py, test_v09_m2.py, test_v09_m3.py,
test_config.py, test_excel_manager.py, test_run_state.py,
test_error_formatting.py, test_mock_pipeline.py, test_doctor.py,
test_study_analytics.py, test_study_summary_panel.py,
test_project_manager.py, test_packaging.py,
test_validation_tools.py, test_validation_plots.py

---

## 3. Missing Test Areas

| Area | Gap | Priority |
|------|-----|----------|
| Internal Flow GUI | No smoke test with IF template loaded | Medium |
| Excel concurrent access | No stress test for locked workbook | Low |
| Ledger concurrent writes | No multi-threaded write test | Low |
| Plugin discovery | No third-party template registration test | Future |

## 4. Test Health: 8/10

*This document is part of the Freebuff Engineering Audit.*