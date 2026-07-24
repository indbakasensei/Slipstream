"""Capability 3 — project template selection & persistence.

A project now remembers which SimulationTemplate it was created for, and the
whole runtime (study definition, workbook schema, execution strategy) plus the
UI resolve *that* template rather than assuming External Aerodynamics. These
tests cover the config field, the resolver seams, template-aware workbook
generation + reading, execution-strategy selection, project-metadata
persistence, and backward compatibility with pre-Capability-3 projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import load_config                          # noqa: E402
from cfdauto.events import EventBus                             # noqa: E402
from cfdauto.excel_manager import ExcelManager                  # noqa: E402
from cfdauto.experiment_definition import ExperimentDefinition  # noqa: E402
from cfdauto.orchestrator import Orchestrator, build_controllers  # noqa: E402
from cfdauto.platform import DEFAULT_TEMPLATE_ID                # noqa: E402
from cfdauto.project_manager import (create_project,           # noqa: E402
                                     open_project)
from cfdauto.project_scaffold import scaffold_project           # noqa: E402
from cfdauto.simulation_context import SimulationContext        # noqa: E402
from cfdauto.study_io import StudyIO                            # noqa: E402


# --------------------------------------------------------------------- #
# Config field + resolver seams
# --------------------------------------------------------------------- #
def _write_config(tmp_path, template=None):
    from tools.make_experiment_template import build_template
    xlsx = tmp_path / "e.xlsx"
    ed = (ExperimentDefinition.from_context(
              SimulationContext.for_template_id(template))
          if template else None)
    build_template(xlsx, exp_def=ed)
    doc = {"excel": {"file": xlsx.as_posix()},
           "runtime": {"work_dir": (tmp_path / "runs").as_posix(), "mock": True}}
    if template is not None:
        doc["runtime"]["template"] = template
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(yaml.safe_dump(doc))
    return load_config(cfg_file)


def test_config_template_id_defaults_when_unset(tmp_path):
    cfg = _write_config(tmp_path)                       # no runtime.template
    assert cfg.runtime.template == ""
    assert cfg.template_id() == DEFAULT_TEMPLATE_ID


def test_config_template_id_honours_project_choice(tmp_path):
    cfg = _write_config(tmp_path, template="internal-flow")
    assert cfg.template_id() == "internal-flow"


def test_simulation_context_for_config_resolves_project_template(tmp_path):
    cfg = _write_config(tmp_path, template="internal-flow")
    ctx = SimulationContext.for_config(cfg)
    assert ctx.template.id == "internal-flow"
    assert ctx.template.name == "Internal Flow"


def test_for_template_id_unknown_is_actionable():
    with pytest.raises(LookupError, match="external-aerodynamics"):
        SimulationContext.for_template_id("no-such-template")


def test_experiment_definition_and_study_io_follow_the_config(tmp_path):
    cfg = _write_config(tmp_path, template="internal-flow")
    ed = ExperimentDefinition.for_config(cfg)
    assert [p.name for p in ed.study.ordered()][:1] == ["inlet_velocity"]
    io = StudyIO.for_config(cfg)
    assert "InletVelocity_m_s" in io.input_column_headers()


# --------------------------------------------------------------------- #
# Template-aware workbook generation + reading
# --------------------------------------------------------------------- #
def test_scaffold_generates_config_and_readable_workbook(tmp_path):
    root = tmp_path / "MyPipeStudy"
    root.mkdir()
    cfg_path = scaffold_project(root, "internal-flow")
    assert cfg_path == root / "config" / "config.yaml"
    assert (root / "data" / "experiments.xlsx").exists()

    cfg = load_config(cfg_path)
    assert cfg.template_id() == "internal-flow"

    # The project-template-aware manager reads the internal-flow workbook —
    # right columns, 8 example rows — with no External Aero assumption.
    excel = ExcelManager.for_config(cfg)
    exps = excel.read_experiments()
    assert len(exps) == 8
    assert exps[0].parameter("inlet_velocity") is not None


def test_scaffold_default_template_is_external_aero(tmp_path):
    root = tmp_path / "WingStudy"
    root.mkdir()
    cfg_path = scaffold_project(root, "")               # empty → default
    cfg = load_config(cfg_path)
    assert cfg.template_id() == DEFAULT_TEMPLATE_ID
    exps = ExcelManager.for_config(cfg).read_experiments()
    assert exps[0].parameter("aoa") is not None


# --------------------------------------------------------------------- #
# Execution-strategy selection is per project
# --------------------------------------------------------------------- #
def test_orchestrator_selects_strategy_from_project_template(tmp_path):
    cfg = _write_config(tmp_path, template="internal-flow")
    excel = ExcelManager.for_config(cfg)
    wb, fl = build_controllers(cfg)
    orch = Orchestrator(cfg, excel, wb, fl, bus=EventBus())
    assert orch._template.id == "internal-flow"
    assert orch._strategy.strategy_id == "internal-flow"


def test_orchestrator_external_aero_strategy_unchanged(tmp_path):
    cfg = _write_config(tmp_path)                       # default template
    excel = ExcelManager.for_config(cfg)
    wb, fl = build_controllers(cfg)
    orch = Orchestrator(cfg, excel, wb, fl, bus=EventBus())
    assert orch._strategy.strategy_id == "external-aerodynamics"


# --------------------------------------------------------------------- #
# Project-metadata persistence + backward compatibility
# --------------------------------------------------------------------- #
def test_project_metadata_persists_template(tmp_path):
    root = tmp_path / "proj"
    meta = create_project(root, "Pipe", template_id="internal-flow")
    assert meta.template_id == "internal-flow"
    on_disk = json.loads((root / "project.json").read_text())
    assert on_disk["template_id"] == "internal-flow"
    # Reopening preserves the recorded template.
    assert open_project(root).template_id == "internal-flow"


def test_old_project_without_template_id_loads_as_default(tmp_path):
    # A pre-Capability-3 project.json (no template_id) is still valid; the
    # field reads back empty → the runtime resolves the default.
    root = tmp_path / "legacy"
    create_project(root, "Legacy")
    data = json.loads((root / "project.json").read_text())
    del data["template_id"]
    (root / "project.json").write_text(json.dumps(data))
    assert open_project(root).template_id == ""


def test_old_config_without_template_loads_unchanged(tmp_path):
    # A config.yaml written before Capability 3 (no runtime.template) loads
    # fine and resolves to the default template.
    cfg = _write_config(tmp_path)
    assert cfg.template_id() == DEFAULT_TEMPLATE_ID
