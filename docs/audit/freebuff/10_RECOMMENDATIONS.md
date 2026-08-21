# 10 - Recommendations

**Audit Version:** v2.3.0-dev | **Date:** 2026-08-21 | **Auditor:** Freebuff

---

## 1. Top 20 Recommendations

### Priority 1 (Immediate)

1. **Create CLAUDE.md** - Critical context engineering gap
2. **Genericize study_analytics.py** - Phase 8D target
3. **Add StudySummary to Ledger** - Persist for cross-batch comparison

### Priority 2 (Phase 8D)

4. Generic StudySummary - template-driven best-case metrics
5. Generic warning rules - remove airfoil-specific codes
6. Add template parameter to analyze_study()

### Priority 3 (Phase 8E)

7. Genericize ColumnMap - dynamic metric columns
8. Genericize excel_manager.write_result - use StudyIO.output_metric_columns()
9. Genericize orchestrator._ledger_finish_case - template metrics
10. Genericize state.py OUTPUT_COLS - derive from template

### Priority 4 (Phase 8F)

11. Genericize telemetry.py - template-driven extraction
12. Genericize linter.py - remove airfoil physics rules
13. Genericize events.py - template-aware payloads

### Priority 5 (Productization)

14. Create application icon
15. Add NSIS/MSI installer
16. Persist workspace layout
17. Add crash reporting

### Priority 6 (Future)

18. Phase 8G Plugin system
19. Phase 8H Internal Flow E2E
20. PDF report generator

---

## 2. Phase 8D Readiness

**Prerequisites Met:**
- [x] Phase 8A (generic identity) complete
- [x] Phase 8B (generic metrics) complete
- [x] Phase 8C (generic Excel StudyIO) complete
- [x] study_analytics.py is pure computational
- [x] StudySummary dataclass has clear interface
- [x] Template.supported_metrics provides metric vocabulary

**Phase 8D Scope:**
- Genericize study_analytics.py to use template metrics
- Preserve byte-identical External Aerodynamics summary
- Support Internal Flow metrics (pressure_drop, reynolds_number, friction_factor)
- Add template parameter to analyze_study() and StudySummary
- Update gui/widgets/study_summary_panel.py for template-agnostic rendering

**Risk: Low** - study_analytics.py is isolated, StudySummary additive.
**Estimated effort: ~160 lines**

---

## 3. Phase Order

Phase 8D should proceed **immediately**. All prerequisites met.
study_analytics.py is the most isolated remaining airfoil coupling.
Small, low-risk change. Unblocks Phase 8E.

**Recommended: 8D -> 8E -> 8F -> 8G -> 8H**

---

## 4. Overall Architecture Health: 8.7/10

Excellent architecture with clear boundaries. Template-driven approach validated
with two domain-different templates. Remaining work precisely scoped to 8 coupling

*This document is part of the Freebuff Engineering Audit.*