"""v0.9 M1 hardening tests: aoa_scale, linter rules, cache guard, doctor."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto import linter                              # noqa: E402
from cfdauto.config import load_config                  # noqa: E402
from cfdauto.excel_manager import ExcelManager          # noqa: E402
from cfdauto.state import RunState                      # noqa: E402
from cfdauto.workbench_controller import WorkbenchController  # noqa: E402
from tools.make_experiment_template import build_template      # noqa: E402

CFG = """
ansys: {{awp_root: "{awp}", runwb2: "{awp}/RunWB2.exe"}}
workbench: {{aoa_scale: {scale}, project_file: "{awp}/p.wbpj"}}
fluent:
  aoa_method: "geometry"
  wall_zones: ["wing"]
  reference: {{density: 1.225, area: {area}, length: {length}}}
excel:
  file: "{xlsx}"
runtime: {{work_dir: "{work}", mock: true}}
"""


def _cfg(tmp_path, scale=1.0, area=1.0, length=1.0):
    xlsx = tmp_path / "e.xlsx"
    build_template(xlsx)
    awp = tmp_path / "ansys"                      # fake install for path checks
    awp.mkdir(exist_ok=True)
    (awp / "RunWB2.exe").write_text("stub")
    (awp / "p.wbpj").write_text("stub")
    cfgf = tmp_path / "c.yaml"
    cfgf.write_text(CFG.format(scale=scale, area=area, length=length,
                               awp=awp.as_posix(), xlsx=xlsx.as_posix(),
                               work=(tmp_path / "runs").as_posix()))
    return load_config(cfgf)


def test_aoa_scale_applied_to_wb_parameter(tmp_path):
    cfg = _cfg(tmp_path, scale=-1.0)
    wb = WorkbenchController(cfg)
    exps = ExcelManager(cfg.excel).read_experiments()
    exp = next(e for e in exps if e.aoa_deg == 8.0)
    params = wb._parameter_expressions(exp)
    assert params[cfg.workbench.aoa_parameter] == "-8.0 [degree]"


def test_aoa_scale_default_is_identity(tmp_path):
    cfg = _cfg(tmp_path)
    wb = WorkbenchController(cfg)
    exp = ExcelManager(cfg.excel).read_experiments()[0]
    assert cfg.workbench.aoa_scale == 1.0
    assert wb._parameter_expressions(exp)[
        cfg.workbench.aoa_parameter] == f"{exp.aoa_deg} [degree]"


def test_linter_flags_post_stall_and_mach(tmp_path):
    cfg = _cfg(tmp_path, area=0.35, length=0.4)
    mgr = ExcelManager(cfg.excel)
    exps = mgr.read_experiments()
    # Push two rows out of bounds
    exps[0].aoa_deg = 18.0
    exps[1].velocity = 150.0
    codes = {f.code for f in linter.lint(cfg, exps)}
    assert "rans-post-stall" in codes
    assert "mach-limit" in codes
    assert "default-reference" not in codes      # real area/length given


def test_linter_quiet_on_sane_schedule(tmp_path):
    cfg = _cfg(tmp_path, area=0.35, length=0.4)
    exps = ExcelManager(cfg.excel).read_experiments()   # template: ±12, 20-30
    codes = {f.code for f in linter.lint(cfg, exps)}
    assert "rans-post-stall" not in codes
    assert "mach-limit" not in codes


def test_linter_row_compaction():
    assert linter._compact([2, 3, 4, 7, 9, 10]) == "2-4, 7, 9-10"


def test_mesh_cache_empty_file_is_harmless(tmp_path):
    work = tmp_path / "runs"
    work.mkdir()
    (work / "mesh_cache.json").write_text("")           # the crash case
    st = RunState(work)
    assert st.cached_mesh("anything") is None


def test_doctor_runs_clean_on_mock_project(tmp_path, capsys):
    cfg_path = None
    xlsx = tmp_path / "e.xlsx"
    build_template(xlsx)
    cfg_path = tmp_path / "c.yaml"
    awp = tmp_path / "ansys"; awp.mkdir(exist_ok=True)
    (awp / "RunWB2.exe").write_text("stub")
    (awp / "p.wbpj").write_text("stub")
    cfg_path.write_text(CFG.format(scale=1.0, area=0.35, length=0.4,
                                   awp=awp.as_posix(), xlsx=xlsx.as_posix(),
                                   work=(tmp_path / "runs").as_posix()))
    from cfdauto.doctor import run_doctor
    rc = run_doctor(str(cfg_path))
    out = capsys.readouterr().out
    assert rc == 0
    assert "[FAIL]" not in out
    assert "mock mode" in out
