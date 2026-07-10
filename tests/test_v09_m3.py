"""v0.9 M3 — SQLite ledger tests.

Covers: schema init, config-hash stability across identical configs,
batch + case + iteration lifecycle, config_diff surface, and the read-only
CLI dispatch."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import load_config                          # noqa: E402
from cfdauto.events import EventBus, Event                      # noqa: E402
from cfdauto.excel_manager import ExcelManager                  # noqa: E402
from cfdauto.ledger import Ledger, config_hash, config_snapshot # noqa: E402
from cfdauto.mocks import MockFluentController, MockWorkbenchController  # noqa: E402
from cfdauto.orchestrator import Orchestrator                   # noqa: E402
from tools.make_experiment_template import build_template       # noqa: E402


CFG = """
ansys: {{awp_root: "{awp}", runwb2: "{awp}/RunWB2.exe"}}
workbench: {{project_file: "{awp}/p.wbpj"}}
fluent:
  aoa_method: "geometry"
  wall_zones: ["wing"]
  reference: {{density: 1.225, area: 0.35, length: 0.4}}
excel: {{file: "{xlsx}"}}
runtime: {{work_dir: "{work}", mock: true, study_name: "{study}"}}
"""


def _cfg(tmp_path, study="unit-test", scale=1.0, shared_install=None):
    """Build a test config. ``shared_install`` lets two configs share their
    fake ANSYS/project/workbook paths so their physics-content hashes agree
    even though ``tmp_path`` differs (matches real single-machine usage)."""
    xlsx = tmp_path / "e.xlsx"
    build_template(xlsx)
    inst = shared_install if shared_install is not None else tmp_path
    awp = inst / "ansys"
    awp.mkdir(exist_ok=True, parents=True)
    (awp / "RunWB2.exe").write_text("stub")
    (awp / "p.wbpj").write_text("stub")
    if shared_install is not None:
        # Point Excel at the shared xlsx too so paths align
        shared_xlsx = inst / "e.xlsx"
        if not shared_xlsx.exists():
            build_template(shared_xlsx)
        xlsx = shared_xlsx
    cfgf = tmp_path / "c.yaml"
    cfgf.write_text(CFG.format(awp=awp.as_posix(), xlsx=xlsx.as_posix(),
                               work=(tmp_path / "runs").as_posix(),
                               study=study))
    return load_config(cfgf)


# --------------------------------------------------------------------- #
def test_config_hash_stable_across_identical_configs(tmp_path):
    inst = tmp_path / "shared"
    inst.mkdir()
    a = _cfg(tmp_path / "a", shared_install=inst)
    b = _cfg(tmp_path / "b", shared_install=inst)
    assert config_hash(a) == config_hash(b), \
        "Same effective config must produce the same hash"


def test_runtime_volatile_fields_excluded_from_hash(tmp_path):
    inst = tmp_path / "shared"
    inst.mkdir()
    a = _cfg(tmp_path / "a", shared_install=inst)
    b = _cfg(tmp_path / "b", shared_install=inst)
    a.runtime.mock = True
    b.runtime.mock = False
    a.runtime.work_dir = "runs_a"
    b.runtime.work_dir = "runs_b"
    assert config_hash(a) == config_hash(b), \
        "mock/work_dir must NOT influence the config hash"


def test_config_hash_changes_when_physics_changes(tmp_path):
    inst = tmp_path / "shared"
    inst.mkdir()
    a = _cfg(tmp_path / "a", shared_install=inst)
    b = _cfg(tmp_path / "b", shared_install=inst)
    b.fluent.reference.area = 0.5           # meaningful physics change
    assert config_hash(a) != config_hash(b)


def test_ledger_batch_and_case_lifecycle(tmp_path):
    cfg = _cfg(tmp_path)
    l = Ledger(cfg.work_dir() / "test.db")
    try:
        study_id = l.ensure_study("s1", "wb.xlsx")
        h = l.record_config(cfg)
        assert isinstance(h, str) and len(h) == 64

        batch_id = l.start_batch(study_id, h, total=3, slipstream_version="0.9")
        case_pk = l.start_case(batch_id, row=2, case_id="r002",
                               aoa_deg=4.0, velocity=20.0, extra={})
        for it in range(1, 6):
            l.record_iteration(case_pk, it, cl=0.01 * it, cd=0.001 * it,
                               residuals={"continuity": 1e-3 / it,
                                          "x_velocity": 1e-4,
                                          "y_velocity": 1e-4,
                                          "z_velocity": 1e-4,
                                          "k": 5e-4, "omega": 5e-4})
        l.finish_case(case_pk, "DONE",
                      result={"cl": 0.5, "cd": 0.02, "lift_n": 25.0,
                              "drag_n": 1.0, "iterations": 400,
                              "converged": True},
                      artifact_dir=str(tmp_path))
        l.finish_batch(batch_id, ok=1, failed=0, stopped=False)

        rows = l.query("SELECT cl, cd, iterations, converged, status "
                       "FROM cases WHERE id=?", (case_pk,))
        assert rows and rows[0]["status"] == "DONE"
        assert rows[0]["cl"] == 0.5 and rows[0]["converged"] == 1

        its = l.query("SELECT COUNT(*) AS n FROM iterations WHERE case_id=?",
                      (case_pk,))
        assert its[0]["n"] == 5
    finally:
        l.close()


def test_config_diff_pinpoints_changes(tmp_path):
    a = _cfg(tmp_path / "a")
    b = _cfg(tmp_path / "b")
    b.fluent.reference.area = 0.5
    b.workbench.aoa_scale = -1.0
    l = Ledger(tmp_path / "d.db")
    try:
        ha = l.record_config(a)
        hb = l.record_config(b)
        diff = l.config_diff(ha, hb)
        assert "fluent.reference.area" in diff
        assert diff["fluent.reference.area"] == (0.35, 0.5)
        assert diff["workbench.aoa_scale"] == (1.0, -1.0)
    finally:
        l.close()


def test_orchestrator_writes_batch_and_iterations_via_bus(tmp_path):
    """End-to-end: run one mock case, then assert the ledger captured
    the batch, the case, and per-iteration telemetry from the bus."""
    cfg = _cfg(tmp_path, study="e2e")
    excel = ExcelManager(cfg.excel)
    bus = EventBus()
    wb = MockWorkbenchController(cfg, bus=bus)
    fl = MockFluentController(cfg, bus=bus)
    orch = Orchestrator(cfg, excel, wb, fl, bus=bus)
    orch.run(max_cases=1)

    db = cfg.work_dir() / "slipstream.db"
    assert db.exists()
    l = Ledger(db)
    try:
        batches = l.query("SELECT id, ok_count, failed_count, "
                          "total_cases FROM batches ORDER BY id DESC LIMIT 1")
        assert batches and batches[0]["total_cases"] == 1
        assert batches[0]["ok_count"] == 1
        cases = l.query("SELECT id, cl, cd, status FROM cases "
                        "WHERE batch_id=? ORDER BY id", (batches[0]["id"],))
        assert cases and cases[0]["status"] == "DONE"
        assert cases[0]["cl"] is not None
        n_iter = l.query("SELECT COUNT(*) AS n FROM iterations "
                         "WHERE case_id=?", (cases[0]["id"],))[0]["n"]
        # Mock streams ~200 events per case; even a very short one > 20.
        assert n_iter > 20, f"Expected many iterations, got {n_iter}"
    finally:
        l.close()


def test_ledger_cli_query_refuses_writes(tmp_path):
    from cfdauto import ledger_cli
    cfg = _cfg(tmp_path)
    # Establish an empty DB so open() doesn't fail
    Ledger(cfg.work_dir() / "slipstream.db").close()
    captured: list[str] = []
    rc = ledger_cli.cmd_query(cfg, "DELETE FROM cases",
                              printer=captured.append)
    assert rc == 2
    assert any("Refusing" in ln for ln in captured)
