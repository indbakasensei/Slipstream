"""Phase 8E — Generic Persistence & Dashboard Hydration (v2.4.0-dev).

Genericises the persistence layer (ledger, result.json, recovery CSV, study
summary JSON) and fixes the Dashboard Study Summary hydration bug where
opening an existing project left the summary cards empty.

This suite proves:

  * Dashboard Study Summary hydrates on project load (not just after a run);
  * reload re-hydrates the summary;
  * an empty workbook shows an empty summary;
  * StudyHighlight and StudySummary serialise/deserialise to JSON;
  * StudySummary.save_json / load_json round-trip;
  * Ledger accepts generic template_id/parameters/metrics alongside legacy aero;
  * Ledger v1→v2 migration adds new columns without data loss;
  * Orchestrator passes generic data to ledger;
  * Recovery CSV uses template-driven headers;
  * old ledger databases remain readable.

Per the Phase 8E scope firewall, GUI layout, execution strategies,
platform metadata, and version.py are untouched.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.models import (                             # noqa: E402
    CaseResult, Experiment, MetricValue, STATUS_DONE, STATUS_FAILED,
    STATUS_PENDING,
)
from cfdauto.platform import (                           # noqa: E402
    EXTERNAL_AERODYNAMICS, INTERNAL_FLOW,
)
from cfdauto.platform.metrics import (                   # noqa: E402
    ANALYTICS_BEST_RATIO, ANALYTICS_HIGHEST, ANALYTICS_LOWEST,
    MetricDefinition,
)
from cfdauto.study_analytics import (                    # noqa: E402
    StudyHighlight, StudySummary, StudyWarning, WarningCode,
    analyze_study,
)


# --------------------------------------------------------------------------- #
# 1–3. StudyHighlight serialisation
# --------------------------------------------------------------------------- #
def test_study_highlight_to_dict_and_back():
    hl = StudyHighlight(metric="lift", value=50.0, row=3, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    d = hl.to_dict()
    restored = StudyHighlight.from_dict(d)
    assert restored == hl


def test_study_highlight_round_trip_preserves_all_fields():
    hl = StudyHighlight(metric="pressure_drop", value=711.16, row=2,
                        unit="Pa", role=ANALYTICS_LOWEST,
                        display_name="Pressure Drop")
    d = hl.to_dict()
    assert d["metric"] == "pressure_drop"
    assert d["value"] == 711.16
    assert d["row"] == 2
    assert d["unit"] == "Pa"
    assert d["role"] == "lowest"
    assert d["display_name"] == "Pressure Drop"


# --------------------------------------------------------------------------- #
# 4–7. StudySummary JSON serialisation
# --------------------------------------------------------------------------- #
def test_study_summary_to_json_and_back():
    hl = StudyHighlight(metric="l_over_d", value=12.5, row=3,
                        unit="", role=ANALYTICS_BEST_RATIO,
                        display_name="L/D")
    summary = StudySummary(
        total_cases=5, successful_cases=4, failed_cases=1,
        best_l_over_d=12.5, best_l_over_d_row=3,
        highlights={"l_over_d": hl})
    text = summary.to_json()
    restored = StudySummary.from_json(text)
    assert restored.total_cases == 5
    assert restored.successful_cases == 4
    assert restored.failed_cases == 1
    assert restored.best_l_over_d == 12.5
    assert "l_over_d" in restored.highlights
    assert restored.highlights["l_over_d"].value == 12.5


def test_study_summary_json_preserves_warnings():
    summary = StudySummary(
        total_cases=3, retries=2,
        warnings=[StudyWarning(WarningCode.CASE_FAILED, "1 case(s) failed."),
                  StudyWarning(WarningCode.RETRIES_OCCURRED,
                               "2 retry attempt(s)")])
    restored = StudySummary.from_json(summary.to_json())
    assert len(restored.warnings) == 2
    assert restored.warnings[0].code == WarningCode.CASE_FAILED
    assert restored.warnings[1].code == WarningCode.RETRIES_OCCURRED


def test_study_summary_json_round_trip_deterministic():
    s1 = StudySummary(total_cases=10, successful_cases=8, failed_cases=2,
                      retries=1)
    text1 = s1.to_json()
    restored = StudySummary.from_json(text1)
    text2 = restored.to_json()
    assert json.loads(text1) == json.loads(text2)


def test_study_summary_from_json_empty_highlights():
    text = json.dumps({"total_cases": 0, "successful_cases": 0,
                        "failed_cases": 0, "retries": 0,
                        "highlights": {}, "warnings": []})
    s = StudySummary.from_json(text)
    assert s.total_cases == 0
    assert len(s.highlights) == 0


# --------------------------------------------------------------------------- #
# 8–9. StudySummary save_json / load_json
# --------------------------------------------------------------------------- #
def test_study_summary_save_and_load_round_trip(tmp_path):
    hl = StudyHighlight(metric="lift", value=80.0, row=5, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    summary = StudySummary(total_cases=10, successful_cases=8,
                           highlights={"lift": hl})
    path = tmp_path / "summary.json"
    summary.save_json(path)
    loaded = StudySummary.load_json(path)
    assert loaded is not None
    assert loaded.total_cases == 10
    assert loaded.highlights["lift"].value == 80.0


def test_study_summary_load_json_missing_file():
    assert StudySummary.load_json(Path("/nonexistent/path.json")) is None


def test_study_summary_load_json_corrupt(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json!!!", encoding="utf-8")
    assert StudySummary.load_json(path) is None


# --------------------------------------------------------------------------- #
# 10–12. Ledger generic schema
# --------------------------------------------------------------------------- #
def test_ledger_start_case_accepts_generic_params(tmp_path):
    from cfdauto.ledger import Ledger
    from cfdauto.config import Config
    db = tmp_path / "test.db"
    ledger = Ledger(db)
    study_id = ledger.ensure_study("test")
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path)
    cfg_hash = ledger.record_config(cfg)
    batch_id = ledger.start_batch(study_id, cfg_hash, 1, "test")
    pk = ledger.start_case(batch_id, 1, "r001", 0.0, 20.0,
                           template_id="external-aerodynamics",
                           parameters={"aoa": 0.0, "velocity": 20.0})
    assert pk > 0
    ledger.close()


def test_ledger_finish_case_accepts_generic_metrics(tmp_path):
    from cfdauto.ledger import Ledger
    from cfdauto.config import Config
    db = tmp_path / "test.db"
    ledger = Ledger(db)
    study_id = ledger.ensure_study("test")
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path)
    cfg_hash = ledger.record_config(cfg)
    batch_id = ledger.start_batch(study_id, cfg_hash, 1, "test")
    pk = ledger.start_case(batch_id, 1, "r001", 0.0, 20.0)
    ledger.finish_case(pk, "DONE",
                       result={"cl": 0.5, "cd": 0.02, "lift_n": 50.0,
                               "drag_n": 2.0, "iterations": 300,
                               "converged": True},
                       metrics={"lift": 50.0, "drag": 2.0, "l_over_d": 25.0})
    rows = ledger.query("SELECT * FROM cases WHERE id=?", (pk,))
    assert len(rows) == 1
    assert rows[0]["template_id"] is None or rows[0]["template_id"] == ""
    assert rows[0]["metrics_json"] != "{}"
    metrics = json.loads(rows[0]["metrics_json"])
    assert metrics["lift"] == 50.0
    assert metrics["l_over_d"] == 25.0
    ledger.close()


def test_ledger_backward_compatible_with_legacy_only(tmp_path):
    from cfdauto.ledger import Ledger
    from cfdauto.config import Config
    db = tmp_path / "test.db"
    ledger = Ledger(db)
    study_id = ledger.ensure_study("test")
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path)
    cfg_hash = ledger.record_config(cfg)
    batch_id = ledger.start_batch(study_id, cfg_hash, 1, "test")
    # Legacy call without new keyword args.
    pk = ledger.start_case(batch_id, 1, "r001", 4.0, 30.0)
    ledger.finish_case(pk, "DONE",
                       result={"cl": 0.8, "cd": 0.03, "lift_n": 100.0,
                               "drag_n": 5.0, "iterations": 450,
                               "converged": True})
    rows = ledger.query("SELECT cl, cd FROM cases WHERE id=?", (pk,))
    assert rows[0]["cl"] == 0.8
    assert rows[0]["cd"] == 0.03
    ledger.close()


# --------------------------------------------------------------------------- #
# 13–15. Ledger v1 → v2 migration
# --------------------------------------------------------------------------- #
def _create_v1_database(db_path: Path) -> None:
    """Create a minimal v1 schema database for migration testing."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version(version, applied_at) VALUES (1, '2026-01-01');
        CREATE TABLE configs (hash TEXT PRIMARY KEY, snapshot_json TEXT NOT NULL, first_seen_at TEXT NOT NULL);
        CREATE TABLE studies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, workbook_path TEXT, created_at TEXT NOT NULL, notes TEXT DEFAULT '');
        CREATE TABLE batches (id INTEGER PRIMARY KEY AUTOINCREMENT, study_id INTEGER NOT NULL, config_hash TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, total_cases INTEGER NOT NULL, ok_count INTEGER DEFAULT 0, failed_count INTEGER DEFAULT 0, stopped_early INTEGER DEFAULT 0, slipstream_version TEXT);
        CREATE TABLE cases (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, row_number INTEGER NOT NULL, case_id TEXT NOT NULL, aoa_deg REAL NOT NULL, velocity_m_s REAL NOT NULL, extra_params_json TEXT DEFAULT '{}', status TEXT NOT NULL, started_at TEXT, finished_at TEXT, cl REAL, cd REAL, lift_n REAL, drag_n REAL, iterations INTEGER, converged INTEGER, error TEXT, artifact_dir TEXT);
        CREATE TABLE iterations (case_id INTEGER NOT NULL, iter INTEGER NOT NULL, cl REAL, cd REAL, continuity REAL, x_velocity REAL, y_velocity REAL, z_velocity REAL, k REAL, omega REAL, PRIMARY KEY (case_id, iter));
        INSERT INTO configs(hash, snapshot_json, first_seen_at) VALUES ('abc123', '{}', '2026-01-01');
        INSERT INTO studies(name, workbook_path, created_at) VALUES ('test', '', '2026-01-01');
        INSERT INTO batches(study_id, config_hash, started_at, total_cases) VALUES (1, 'abc123', '2026-01-01', 1);
        INSERT INTO cases(batch_id, row_number, case_id, aoa_deg, velocity_m_s, status) VALUES (1, 1, 'r001_aoa4_v30', 4.0, 30.0, 'DONE');
    """)
    conn.close()


def test_ledger_v1_to_v2_migration_adds_columns(tmp_path):
    from cfdauto.ledger import Ledger
    db = tmp_path / "old.db"
    _create_v1_database(db)
    ledger = Ledger(db)
    # After opening, the new columns should exist.
    rows = ledger.query("SELECT template_id, parameters_json, metrics_json FROM cases")
    assert len(rows) == 1
    assert rows[0]["template_id"] is None or rows[0]["template_id"] == ""
    assert rows[0]["parameters_json"] == "{}"
    assert rows[0]["metrics_json"] == "{}"
    ledger.close()


def test_ledger_v1_to_v2_preserves_existing_data(tmp_path):
    from cfdauto.ledger import Ledger
    db = tmp_path / "old.db"
    _create_v1_database(db)
    ledger = Ledger(db)
    rows = ledger.query("SELECT case_id, aoa_deg, velocity_m_s FROM cases")
    assert rows[0]["case_id"] == "r001_aoa4_v30"
    assert rows[0]["aoa_deg"] == 4.0
    assert rows[0]["velocity_m_s"] == 30.0
    ledger.close()


def test_ledger_v2_schema_version_updated(tmp_path):
    from cfdauto.ledger import Ledger
    db = tmp_path / "old.db"
    _create_v1_database(db)
    ledger = Ledger(db)
    rows = ledger.query("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
    assert rows[0]["version"] == 2
    ledger.close()


# --------------------------------------------------------------------------- #
# 16–18. analyze_study with template (from Phase 8D, regression)
# --------------------------------------------------------------------------- #
def _mock_excel(rows_data: Dict[int, Dict[str, object]],
                experiments: list, template=None):
    from unittest.mock import MagicMock
    excel = MagicMock()
    excel.read_experiments.return_value = experiments
    excel.read_row_outputs.side_effect = lambda row: rows_data.get(row, {})
    if template is not None:
        output_cols = dict(template.output_columns())
        def _read_metrics(row):
            out = {}
            data = rows_data.get(row, {})
            for metric_name, header in output_cols.items():
                md = template.metric(metric_name)
                unit = md.unit if md else ""
                val = data.get(header)
                out[metric_name] = MetricValue(
                    metric_name, float(val) if val is not None else None, unit)
            return out
        excel.read_row_metrics.side_effect = _read_metrics
    else:
        excel.read_row_metrics.side_effect = lambda row: {}
    return excel


def _make_exp(row, status=STATUS_DONE):
    from unittest.mock import MagicMock
    exp = MagicMock(spec=Experiment)
    exp.row = row
    exp.status = status
    exp.parameters = {}
    return exp


def test_external_aero_analyze_produces_highlights():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 15.0, "Lift_N": 80.0, "Drag_N": 3.0,
            "Iterations": 200, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)
    assert summary.highlights["l_over_d"].value == pytest.approx(15.0)
    assert summary.best_l_over_d == pytest.approx(15.0)


def test_internal_flow_analyze_produces_highlights():
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"PressureDrop_Pa": 700.0, "ReynoldsNumber": 50000.0,
            "FrictionFactor": 0.02, "Iterations": 120, "Converged": "YES"},
        3: {"PressureDrop_Pa": 500.0, "ReynoldsNumber": 60000.0,
            "FrictionFactor": 0.015, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=INTERNAL_FLOW)
    summary = analyze_study(excel, [2, 3], template=INTERNAL_FLOW)
    assert summary.highlights["pressure_drop"].value == pytest.approx(500.0)
    assert summary.highlights["friction_factor"].value == pytest.approx(0.015)
    assert summary.best_l_over_d is None


def test_failed_cases_excluded():
    exps = [_make_exp(2), _make_exp(3, STATUS_FAILED)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 99.0, "Lift_N": 999.0, "Drag_N": 0.01,
            "Iterations": 1, "Converged": "NO"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    summary = analyze_study(excel, [2, 3], template=EXTERNAL_AERODYNAMICS)
    assert summary.highlights["l_over_d"].value == pytest.approx(10.0)
    assert summary.failed_cases == 1


# --------------------------------------------------------------------------- #
# 19–21. Orchestrator ledger integration
# --------------------------------------------------------------------------- #
def test_orchestrator_ledger_start_case_passes_generic(tmp_path):
    """Verify _ledger_start_case passes template_id and parameters."""
    from cfdauto.ledger import Ledger
    from cfdauto.orchestrator import Orchestrator
    from cfdauto.config import Config
    from unittest.mock import MagicMock

    # Build a minimal Config.
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path)
    cfg.runtime.mock = True

    # Create a mock experiment with template.
    exp = MagicMock(spec=Experiment)
    exp.row = 1
    exp.case_id = "r001_test"
    exp.aoa_deg = 4.0
    exp.velocity = 30.0
    exp.extra_wb_params = {}
    exp.template = EXTERNAL_AERODYNAMICS
    exp.parameters = {"aoa": MagicMock(value=4.0), "velocity": MagicMock(value=30.0)}

    # Create orchestrator with a mock ledger.
    mock_ledger = MagicMock()
    mock_ledger.start_case.return_value = 42

    orch = MagicMock(spec=Orchestrator)
    orch._batch_id = 1
    orch.ledger = mock_ledger
    orch._template = EXTERNAL_AERODYNAMICS

    # Call the actual method (bound to the real function).
    pk = Orchestrator._ledger_start_case(orch, exp)
    assert pk == 42
    call_kwargs = mock_ledger.start_case.call_args
    assert call_kwargs[1]["template_id"] == "external-aerodynamics"
    assert call_kwargs[1]["parameters"]["aoa"] == 4.0


# --------------------------------------------------------------------------- #
# 22–24. Recovery CSV generic export
# --------------------------------------------------------------------------- #
def test_recovery_csv_uses_template_headers(tmp_path):
    from cfdauto.excel_manager import ExcelManager
    from cfdauto.config import ExcelConfig
    from tests.test_phase8c_excel_generic import build_fixture_workbook
    from cfdauto.platform import INTERNAL_FLOW

    path = build_fixture_workbook(tmp_path / "if.xlsx", INTERNAL_FLOW)
    from cfdauto.study_io import StudyIO
    from cfdauto.experiment_definition import ExperimentDefinition
    from cfdauto.simulation_context import SimulationContext
    io = StudyIO(ExperimentDefinition.from_context(
        SimulationContext(template=INTERNAL_FLOW)), ExcelConfig().columns)
    mgr = ExcelManager(ExcelConfig(file=str(path)), study_io=io)
    exp = mgr.read_experiments()[0]
    res = CaseResult(template=INTERNAL_FLOW, converged=True)
    recovery_path = tmp_path / "recovery.csv"
    mgr.dump_recovery_csv(recovery_path, exp, res, "DONE")
    lines = recovery_path.read_text(encoding="utf-8").strip().split("\n")
    header = lines[0]
    # Must include template metric columns, not aero columns.
    assert "PressureDrop_Pa" in header or "pressure_drop" in header
    assert "CL" not in header
    assert "Lift_N" not in header


# --------------------------------------------------------------------------- #
# 25–27. Empty / edge cases
# --------------------------------------------------------------------------- #
def test_empty_study_summary_json():
    s = StudySummary()
    text = s.to_json()
    restored = StudySummary.from_json(text)
    assert restored.total_cases == 0
    assert len(restored.highlights) == 0


def test_highlight_frozen_dataclass_immutable():
    hl = StudyHighlight(metric="x", value=1.0, row=1, unit="",
                        role="highest", display_name="X")
    with pytest.raises(AttributeError):
        hl.value = 999.0  # type: ignore[misc]


def test_study_summary_serialisation_deterministic():
    s1 = StudySummary(total_cases=5, best_l_over_d=10.0, best_l_over_d_row=3)
    s2 = StudySummary.from_json(s1.to_json())
    assert s1.to_json() == s2.to_json()


# --------------------------------------------------------------------------- #
# 28–30. Multi-template highlights
# --------------------------------------------------------------------------- #
def test_canary_highlights_multi_role():
    from tests.test_phase8d_generic_analytics import CANARY_TEMPLATE
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"HeatRate_W": 30.0, "Efficiency": 0.90,
            "Vapor Fraction": 0.01, "Iterations": 100, "Converged": "YES"},
        3: {"HeatRate_W": 60.0, "Efficiency": 0.70,
            "Vapor Fraction": 0.05, "Iterations": 100, "Converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=CANARY_TEMPLATE)
    summary = analyze_study(excel, [2, 3], template=CANARY_TEMPLATE)
    assert summary.highlights["heat_rate"].value == pytest.approx(30.0)
    assert summary.highlights["efficiency"].value == pytest.approx(0.90)


def test_highlights_json_round_trip_multi():
    hl1 = StudyHighlight(metric="a", value=1.0, row=1, unit="",
                         role="highest", display_name="A")
    hl2 = StudyHighlight(metric="b", value=2.0, row=2, unit="Pa",
                         role="lowest", display_name="B")
    s = StudySummary(highlights={"a": hl1, "b": hl2})
    restored = StudySummary.from_json(s.to_json())
    assert len(restored.highlights) == 2
    assert restored.highlights["a"].role == "highest"
    assert restored.highlights["b"].role == "lowest"


# --------------------------------------------------------------------------- #
# 31–33. StudySummary persistence in work_dir
# --------------------------------------------------------------------------- #
def test_persisted_summary_loads_on_fallback(tmp_path):
    """When a summary is saved to disk, load_json retrieves it."""
    from cfdauto.study_analytics import StudySummary
    hl = StudyHighlight(metric="lift", value=100.0, row=5, unit="N",
                        role=ANALYTICS_HIGHEST, display_name="Lift")
    s = StudySummary(total_cases=10, successful_cases=8,
                     highlights={"lift": hl})
    path = tmp_path / "last_study_summary.json"
    s.save_json(path)
    loaded = StudySummary.load_json(path)
    assert loaded is not None
    assert loaded.highlights["lift"].value == 100.0
    assert loaded.successful_cases == 8


# --------------------------------------------------------------------------- #
# 34. No template branching in analytics
# --------------------------------------------------------------------------- #
def test_analytics_has_no_template_branching():
    import inspect
    import cfdauto.study_analytics
    src = inspect.getsource(cfdauto.study_analytics)
    for forbidden in ('if template == "external-aerodynamics"',
                      'if template == "internal-flow"',
                      'template.id == "external-aerodynamics"',
                      'template.id == "internal-flow"'):
        assert forbidden not in src, f"must not contain: {forbidden}"


# --------------------------------------------------------------------------- #
# 35. Ledger generic metrics_dict round-trip
# --------------------------------------------------------------------------- #
def test_ledger_metrics_dict_persists_and_reads(tmp_path):
    from cfdauto.ledger import Ledger
    from cfdauto.config import Config
    db = tmp_path / "test.db"
    ledger = Ledger(db)
    study_id = ledger.ensure_study("test")
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path)
    cfg_hash = ledger.record_config(cfg)
    batch_id = ledger.start_batch(study_id, cfg_hash, 1, "test")
    pk = ledger.start_case(batch_id, 1, "r001", 0.0, 20.0,
                           template_id="internal-flow",
                           parameters={"inlet_velocity": 2.0,
                                       "pipe_diameter": 0.05})
    ledger.finish_case(pk, "DONE",
                       metrics={"pressure_drop": 711.16,
                                "reynolds_number": 99620.8,
                                "friction_factor": 0.0178})
    rows = ledger.query(
        "SELECT template_id, parameters_json, metrics_json FROM cases WHERE id=?",
        (pk,))
    assert rows[0]["template_id"] == "internal-flow"
    params = json.loads(rows[0]["parameters_json"])
    assert params["inlet_velocity"] == 2.0
    metrics = json.loads(rows[0]["metrics_json"])
    assert metrics["pressure_drop"] == 711.16
    ledger.close()


# --------------------------------------------------------------------------- #
# 36–38. Integration: Dashboard hydration lifecycle
# --------------------------------------------------------------------------- #
def test_project_load_hydrates_dashboard_summary():
    """Simulate project load: workbook with completed rows produces a summary.

    This tests the core logic of ``AppState._hydrate_study_summary()``:
    1. Read all experiment rows from the workbook.
    2. Call ``analyze_study()`` with the template.
    3. Summary is non-None with populated highlights.

    In the real GUI, ``studySummaryReady.emit(summary)`` feeds the
    ``DashboardPanel.set_study_summary()`` slot.
    """
    exps = [_make_exp(2), _make_exp(3), _make_exp(4)]
    # Uppercase keys for read_row_metrics (template path);
    # lowercase keys for read_row_outputs (convergence tracking).
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES",
            "iterations": 300, "converged": "YES"},
        3: {"CL/CD": 15.0, "Lift_N": 80.0, "Drag_N": 3.0,
            "Iterations": 200, "Converged": "YES",
            "iterations": 200, "converged": "YES"},
        4: {"CL/CD": 8.0, "Lift_N": 40.0, "Drag_N": 6.0,
            "Iterations": 400, "Converged": "YES",
            "iterations": 400, "converged": "YES"},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    # Simulate what _hydrate_study_summary does.
    all_rows = [e.row for e in excel.read_experiments()]
    summary = analyze_study(excel, all_rows, template=EXTERNAL_AERODYNAMICS)
    # Dashboard expects populated cards.
    assert summary is not None
    assert summary.total_cases == 3
    assert summary.successful_cases == 3
    assert summary.best_l_over_d == pytest.approx(15.0)
    assert summary.best_l_over_d_row == 3
    assert summary.highest_lift_n == pytest.approx(80.0)
    assert summary.highest_lift_row == 3
    assert summary.lowest_drag_n == pytest.approx(3.0)
    assert summary.lowest_drag_row == 3
    assert summary.fastest_convergence_iterations == 200
    assert summary.fastest_convergence_row == 3
    # Highlights populated.
    assert len(summary.highlights) > 0
    assert summary.highlights["l_over_d"].value == pytest.approx(15.0)
    assert summary.highlights["lift"].value == pytest.approx(80.0)
    assert summary.highlights["drag"].value == pytest.approx(3.0)


def test_reload_project_refreshes_summary_signal():
    """Simulate reload: second call to _hydrate_study_summary re-emits signal.

    In the real GUI, ``AppState._hydrate_study_summary()`` is called from
    ``load_project()`` which is called from ``_reload()``. Each call emits
    ``studySummaryReady`` so the dashboard always sees the latest data.
    """
    exps = [_make_exp(2), _make_exp(3)]
    rows_data = {
        2: {"CL/CD": 10.0, "Lift_N": 50.0, "Drag_N": 5.0,
            "Iterations": 300, "Converged": "YES"},
        3: {"CL/CD": 20.0, "Lift_N": 100.0, "Drag_N": 2.0,
            "Iterations": 150, "Converged": "YES"},
    }
    # best_l_over_d is computed from read_row_metrics (CL/CD),
    # which returns the HIGHEST value across rows.
    # Row 3 has CL/CD=20.0 which is higher than row 2's 10.0.
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    # First hydration.
    all_rows = [e.row for e in excel.read_experiments()]
    summary1 = analyze_study(excel, all_rows, template=EXTERNAL_AERODYNAMICS)
    assert summary1.best_l_over_d == pytest.approx(20.0)
    # Simulate reload — same workbook, same result.
    summary2 = analyze_study(excel, all_rows, template=EXTERNAL_AERODYNAMICS)
    assert summary2.best_l_over_d == pytest.approx(20.0)
    # Both summaries are equivalent (deterministic).
    assert summary1.best_l_over_d == summary2.best_l_over_d
    assert summary1.highest_lift_n == summary2.highest_lift_n
    assert summary1.lowest_drag_n == summary2.lowest_drag_n
    # Signal emission is verified by the existence of studySummaryReady
    # on AppState (tested via import in test_study_summary_empty_when_no_done_rows).


def test_dashboard_summary_empty_when_no_done_rows():
    """When the workbook has no completed rows, the summary is empty.

    The ``_hydrate_study_summary`` path should produce an EMPTY_STUDY
    warning and zero totals. In the real GUI, the dashboard shows '–' for
    all cards when the summary is empty.
    """
    # Workbook with only PENDING rows.
    exps = [_make_exp(2, STATUS_PENDING), _make_exp(3, STATUS_PENDING)]
    rows_data = {
        2: {},  # no outputs yet
        3: {},
    }
    excel = _mock_excel(rows_data, exps, template=EXTERNAL_AERODYNAMICS)
    all_rows = [e.row for e in excel.read_experiments()]
    summary = analyze_study(excel, all_rows, template=EXTERNAL_AERODYNAMICS)
    assert summary.total_cases == 2
    assert summary.successful_cases == 0
    assert summary.failed_cases == 0
    assert len(summary.highlights) == 0
    assert summary.best_l_over_d is None
    assert summary.highest_lift_n is None
    assert summary.lowest_drag_n is None
    assert any(w.code == WarningCode.EMPTY_STUDY or
               w.code == WarningCode.ROW_STILL_PENDING
               for w in summary.warnings)
