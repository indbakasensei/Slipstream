"""Sprint 1 — behavioral tests for cfdauto.doctor.

`doctor` exists specifically because "it works on my machine" failures in
this framework are expensive: a batch can burn through licence tokens or
30 minutes of Workbench time before a bad path/version pairing is
discovered. These tests cover the checks that are pure logic (no real
ANSYS/Fluent install needed), plus one end-to-end proof that a
deliberately broken config actually surfaces as a FAIL in the printed
report — not just that a clean mock project passes (already covered by
test_v09_m1.py::test_doctor_runs_clean_on_mock_project).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import Config                         # noqa: E402
from cfdauto.doctor import (                                # noqa: E402
    FAIL, PASS, WARN,
    _awp_env_check, _lock_check, _mesh_cache_check, _version_consistency,
    run_doctor,
)
from tools.make_experiment_template import build_template   # noqa: E402


# --------------------------------------------------------------------- #
# Group: ansys.version <-> fluent.product_version pairing
#
# Regression Scenario: config.yaml's ansys.version ("261") and
# fluent.product_version ("25.2.0") drift out of sync after a partial
# ANSYS upgrade — PyFluent then looks up the wrong AWP_ROOT<ver>
# environment variable and fails to launch, with an error message that
# gives no hint the two settings even needed to match.
# Expected Behaviour: matching versions -> PASS; a real mismatch -> FAIL;
# an unset product_version -> WARN (PyFluent will guess).
# Why this test exists: this exact mismatch is called out in the
# module's own docstring as a real, previously-hit failure mode.
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("version,product_version,expected", [
    ("261", "26.1.0", PASS),
    ("261", "25.2.0", FAIL),
    ("261", "", WARN),
])
def test_version_consistency_check(version, product_version, expected):
    cfg = Config()
    cfg.ansys.version = version
    cfg.fluent.product_version = product_version
    status, _ = _version_consistency(cfg)
    assert status == expected


# --------------------------------------------------------------------- #
# Group: AWP_ROOT<version> environment variable resolution
#
# Regression Scenario: PyFluent resolves the ANSYS install location via
# the AWP_ROOT<version> environment variable, falling back to
# ansys.awp_root only if that's unset. A user who sets one but not the
# other gets a confusing "works in this shell, not that one" experience.
# Expected Behaviour: env var present & valid -> PASS; present but
# pointing nowhere -> WARN; absent with no config fallback -> FAIL;
# absent with a config fallback present -> WARN.
# Why this test exists: pins down the exact fallback precedence so a
# future edit to this check can't silently invert it.
# --------------------------------------------------------------------- #
def test_awp_env_check_precedence(tmp_path, monkeypatch):
    real_dir = tmp_path / "ansys"
    real_dir.mkdir()
    cfg = Config()
    cfg.ansys.version = "261"

    monkeypatch.setenv("AWP_ROOT261", str(real_dir))
    assert _awp_env_check(cfg)[0] == PASS

    monkeypatch.setenv("AWP_ROOT261", str(tmp_path / "does_not_exist"))
    assert _awp_env_check(cfg)[0] == WARN

    monkeypatch.delenv("AWP_ROOT261", raising=False)
    cfg.ansys.awp_root = ""
    assert _awp_env_check(cfg)[0] == FAIL

    cfg.ansys.awp_root = str(real_dir)
    assert _awp_env_check(cfg)[0] == WARN


# --------------------------------------------------------------------- #
# Group: run lock + mesh cache health, as seen from disk
#
# Regression Scenario: `doctor` is meant to be safe to run *while* a
# batch is in progress, and to explain a stale lock left by a crash
# rather than just reporting a mysterious FAIL.
# Expected Behaviour: no lock file -> PASS; a lock from a live PID (the
# test process itself) -> FAIL; a lock from a dead PID -> WARN
# (reclaimable). A mesh cache with some evicted mesh files still reports
# an accurate live/total count instead of crashing.
# Why this test exists: these are the two on-disk artifacts most likely
# to be in a "weird" state right after a crash — doctor's job is to
# explain that state, not just fail opaquely.
# --------------------------------------------------------------------- #
def test_lock_check_reports_live_dead_and_absent_locks(tmp_path):
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path / "runs")

    assert _lock_check(cfg)[0] == PASS       # no lock yet

    lock = cfg.work_dir() / "cfdauto.lock"
    lock.write_text(str(os.getpid()))
    assert _lock_check(cfg)[0] == FAIL       # our own process is alive

    lock.write_text("999999999")             # guaranteed-dead PID
    assert _lock_check(cfg)[0] == WARN


def test_mesh_cache_check_reports_live_entry_count(tmp_path):
    cfg = Config()
    cfg.runtime.work_dir = str(tmp_path / "runs")
    work = cfg.work_dir()

    assert _mesh_cache_check(cfg)[0] == PASS         # no cache file yet

    present = work / "present.msh"
    present.write_text("mesh")
    cache = {"aoa=0.000000": str(present), "aoa=4.000000": str(work / "gone.msh")}
    (work / "mesh_cache.json").write_text(json.dumps(cache))
    status, detail = _mesh_cache_check(cfg)
    assert status == PASS
    assert "2 entries" in detail and "1 mesh files present" in detail


# --------------------------------------------------------------------- #
# Group: run_doctor end-to-end — a broken config must show up as FAIL
#
# Regression Scenario: doctor is only useful if it actually catches a
# real misconfiguration, not just prints a clean report for a healthy
# mock project. Silently passing a broken config would defeat the
# entire purpose of the command.
# Expected Behaviour: given a config with a deliberate ansys.version /
# fluent.product_version mismatch, the printed report marks the "ansys
# version pairing" row FAIL and the function returns exit code 1.
# Why this test exists: proves doctor's failure path end-to-end, not
# just its happy path.
# --------------------------------------------------------------------- #
def test_run_doctor_flags_a_deliberately_broken_config(tmp_path, capsys):
    xlsx = tmp_path / "e.xlsx"
    build_template(xlsx)
    awp = tmp_path / "ansys"
    awp.mkdir()
    runwb2 = awp / "RunWB2.exe"
    runwb2.write_text("stub")
    wbpj = tmp_path / "p.wbpj"
    wbpj.write_text("stub")
    cfg_path = tmp_path / "c.yaml"
    cfg_path.write_text(f"""
ansys: {{version: "261", awp_root: "{awp.as_posix()}", runwb2: "{runwb2.as_posix()}"}}
workbench: {{project_file: "{wbpj.as_posix()}"}}
fluent:
  aoa_method: "geometry"
  wall_zones: ["wing"]
  product_version: "25.2.0"
  reference: {{density: 1.225, area: 0.35, length: 0.4}}
excel: {{file: "{xlsx.as_posix()}"}}
runtime: {{work_dir: "{(tmp_path / 'runs').as_posix()}", mock: false}}
""")
    rc = run_doctor(str(cfg_path))
    out = capsys.readouterr().out
    version_line = next(l for l in out.splitlines() if "ansys version pairing" in l)
    assert "[FAIL]" in version_line
    assert rc == 1
