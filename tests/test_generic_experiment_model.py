"""Universal CFD Platform, Phase 4 — generic experiment model tests.

Experiment now stores generic ParameterValue objects (no airfoil fields);
CaseResult stores generic MetricValue objects. The legacy attributes
(aoa_deg/velocity/cl/cd/…) are compatibility accessors over those stores,
with one source of truth. These tests lock in: the generic containers, the
legacy accessors + setters, the generic accessors, byte-identical
serialization, and template-driven construction.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.experiment_definition import ExperimentDefinition   # noqa: E402
from cfdauto.models import (                                     # noqa: E402
    CaseResult,
    Experiment,
    MetricValue,
    ParameterValue,
)


# --------------------------------------------------------------------- #
# Group: generic value containers
# --------------------------------------------------------------------- #
def test_parameter_value_carries_id_value_source_status():
    pv = ParameterValue("aoa", 8.0)
    assert pv.parameter_id == "aoa" and pv.value == 8.0
    assert pv.source == "schedule" and pv.status == "set"


def test_metric_value_carries_id_value_unit_status():
    mv = MetricValue("lift_n", 120.5, "N")
    assert mv.metric_id == "lift_n" and mv.value == 120.5
    assert mv.unit == "N" and mv.status == "computed"


# --------------------------------------------------------------------- #
# Group: Experiment stores parameters generically
# --------------------------------------------------------------------- #
def test_experiment_stores_generic_parameters_not_airfoil_fields():
    e = Experiment(row=5, aoa_deg=8.0, velocity=30.0,
                   extra_wb_params={"Flap": 15.0})
    # Authoritative store is the generic dict.
    assert set(e.parameters) == {"aoa", "velocity", "Flap"}
    assert isinstance(e.parameters["aoa"], ParameterValue)
    assert e.parameters["aoa"].value == 8.0
    assert e.parameters["Flap"].source == "wbp"
    # No duplicate storage: legacy accessors read from the dict.
    assert "aoa_deg" not in vars(e)
    assert "velocity" not in vars(e)


def test_legacy_accessors_read_and_write_through_the_generic_store():
    e = Experiment(row=1, aoa_deg=4.0, velocity=20.0)
    assert e.aoa_deg == 4.0 and e.velocity == 20.0
    # Setter routes to the single source of truth.
    e.aoa_deg = 12.0
    assert e.parameters["aoa"].value == 12.0
    e.velocity = 25.0
    assert e.parameters["velocity"].value == 25.0
    assert e.extra_wb_params == {}


def test_generic_accessors():
    e = Experiment(row=1, aoa_deg=4.0, velocity=20.0, extra_wb_params={"P3": 2.0})
    assert e.parameter("aoa").value == 4.0
    assert e.parameter("missing") is None
    assert e.parameters_dict() == {"aoa": 4.0, "velocity": 20.0, "P3": 2.0}


def test_case_id_and_geometry_key_unchanged():
    e = Experiment(row=5, aoa_deg=8.0, velocity=30.0)
    assert e.case_id == "r005_aoa8_v30"
    assert e.geometry_key == "aoa=8.000000"
    e2 = Experiment(row=5, aoa_deg=8.0, velocity=30.0, extra_wb_params={"Flap": 15.0})
    assert e2.case_id == "r005_aoa8_v30_Flap15"
    assert e2.geometry_key == "aoa=8.000000|Flap=15.000000"


def test_experiment_validate_behavior_unchanged():
    Experiment(row=1, aoa_deg=4.0, velocity=20.0).validate()   # ok
    with pytest.raises(ValueError, match="velocity"):
        Experiment(row=1, aoa_deg=4.0, velocity=-1.0).validate()
    with pytest.raises(ValueError, match="AOA"):
        Experiment(row=1, aoa_deg=float("nan"), velocity=20.0).validate()


def test_experiment_json_matches_the_former_vars_dict():
    e = Experiment(row=2, aoa_deg=0.0, velocity=20.0, status="",
                   extra_wb_params={})
    assert e.to_json_dict() == {
        "row": 2, "aoa_deg": 0.0, "velocity": 20.0,
        "status": "", "extra_wb_params": {}}
    assert list(e.to_json_dict().keys()) == [
        "row", "aoa_deg", "velocity", "status", "extra_wb_params"]


# --------------------------------------------------------------------- #
# Group: CaseResult stores metrics generically
# --------------------------------------------------------------------- #
def test_case_result_stores_generic_metrics_not_airfoil_fields():
    r = CaseResult(cl=0.6, cd=0.05, lift_n=10.0, drag_n=1.0)
    assert set(r.metrics) == {"cl", "cd", "lift_n", "drag_n"}
    assert isinstance(r.metrics["cl"], MetricValue)
    assert r.metrics["lift_n"].unit == "N"
    # cl/cd/lift_n/drag_n are not stored as separate attributes.
    assert "cl" not in vars(r) and "cd" not in vars(r)


def test_case_result_legacy_accessors_and_tuple_assignment():
    r = CaseResult()
    assert r.cl is None and r.cd is None       # defaults present as None
    r.cl, r.cd = 0.8, 0.04                      # tuple set, as the mock does
    assert r.metrics["cl"].value == 0.8 and r.metrics["cd"].value == 0.04
    r.lift_n = 50.0
    assert r.metrics["lift_n"].value == 50.0


def test_case_result_generic_accessors():
    r = CaseResult(cl=0.6, cd=0.05)
    assert r.metric("cl").value == 0.6
    assert r.metric("nope") is None
    assert r.metrics_dict()["cl"] == 0.6


def test_case_result_derived_quantities_unchanged():
    r = CaseResult(cl=0.6, cd=0.05, lift_n=12.0, drag_n=1.0)
    assert r.cl_over_cd == pytest.approx(12.0)
    assert r.fl_over_fd == pytest.approx(12.0)
    assert CaseResult(cl=0.6, cd=0).cl_over_cd is None       # divide-by-zero guard


def test_case_result_json_keys_and_order_unchanged():
    from datetime import datetime
    r = CaseResult(cl=0.6, cd=0.05, lift_n=12.0, drag_n=1.0, iterations=200,
                   converged=True, started=datetime(2026, 1, 1, 10, 0, 0),
                   finished=datetime(2026, 1, 1, 10, 5, 0))
    d = r.to_json_dict()
    assert list(d.keys()) == [
        "cl", "cd", "lift_n", "drag_n", "iterations", "converged", "error",
        "started", "finished", "mesh_file", "artifact_dir",
        "cl_over_cd", "fl_over_fd", "duration_min"]
    assert d["cl"] == 0.6 and d["duration_min"] == 5.0
    assert d["started"] == "2026-01-01T10:00:00"


# --------------------------------------------------------------------- #
# Group: template-driven (generic) construction
# --------------------------------------------------------------------- #
def test_experiment_definition_builds_generic_parameter_values():
    ed = ExperimentDefinition.default()
    pvs = ed.build_parameter_values({"aoa": 5.0, "velocity": 25.0})
    assert set(pvs) == {"aoa", "velocity"}
    assert all(isinstance(v, ParameterValue) for v in pvs.values())
    assert pvs["aoa"].value == 5.0


def test_experiment_definition_builds_a_generic_experiment():
    ed = ExperimentDefinition.default()
    e = ed.build_experiment(row=3, values={"aoa": 5.0, "velocity": 25.0})
    # Behaves exactly like a legacy-constructed experiment.
    assert e.aoa_deg == 5.0 and e.velocity == 25.0
    assert e.case_id == "r003_aoa5_v25"
    e.validate()
