"""Sprint 1 — behavioral tests for cfdauto.config.

Config loading is the very first thing every entry point (CLI, GUI, doctor)
does. A silent misconfiguration here doesn't fail loudly at start-up — it
surfaces two hours later as a cryptic Workbench/Fluent crash deep in a batch.
These tests protect the "fail fast, fail clearly" contract of load_config().
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.config import load_config                  # noqa: E402
from cfdauto.exceptions import ConfigError               # noqa: E402


def _write_cfg(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(body)
    return p


# --------------------------------------------------------------------- #
# Group: happy path
#
# Regression Scenario: a config with no explicit sections at all (a brand
# new user just runs the tool against the shipped default config.yaml).
# Expected Behaviour: every section falls back to its dataclass defaults,
# and the file loads without raising.
# Why this test exists: guards against a future required-field addition
# silently breaking "config.yaml as documented" for every existing user.
# --------------------------------------------------------------------- #
def test_defaults_load_without_any_sections(tmp_path):
    cfg = load_config(_write_cfg(tmp_path, "excel: {file: nonexistent.xlsx}\n"))
    assert cfg.fluent.dimension == 3
    assert cfg.solve.max_iterations == 1500
    assert cfg.runtime.retries_per_case == 1


# --------------------------------------------------------------------- #
# Group: loud rejection of unknown keys
#
# Regression Scenario: a user (or a copy-pasted config from another
# project) has a typo'd or stale key, e.g. "flunt:" instead of "fluent:",
# or "wal_zones:" instead of "wall_zones:". Silently ignoring it means the
# run proceeds with defaults the user never intended, and the mistake is
# only discovered after burning through an overnight batch.
# Expected Behaviour: load_config raises ConfigError naming the bad key.
# Why this test exists: this is the framework's main defense against typo
# configs — a single parametrized test proves the same defensive mechanism
# fires at every level (top-level section, section field) instead of
# writing a near-identical test per section.
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("body", [
    "flunt: {dimension: 3}\n",                      # unknown top-level section
    "fluent: {wal_zones: [wing]}\n",                 # unknown key within a section
    "fluent: not_a_mapping\n",                       # section is not a mapping at all
])
def test_unknown_or_malformed_config_is_rejected_loudly(tmp_path, body):
    with pytest.raises(ConfigError):
        load_config(_write_cfg(tmp_path, body))


def test_missing_config_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does_not_exist.yaml")


# --------------------------------------------------------------------- #
# Group: physics/solver sanity checks (validate_static)
#
# Regression Scenario: a hand-edited config.yaml has an internally
# inconsistent solver setting (e.g. convergence_window of 2 samples, which
# makes the flatness check meaningless, or a wall_zones list emptied out
# by accident) — nothing here is a YAML syntax error, so the plain loader
# would accept it and the mistake would only show up as garbage CL/CD
# results after a full solve.
# Expected Behaviour: load_config raises ConfigError whose message names
# the specific offending field, for every field validate_static() checks.
# Why this test exists: validate_static() is the framework's only
# pre-flight physics/solver sanity net; a table-driven test proves each
# rule still fires without one bespoke test function per rule.
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("body,expected_fragment", [
    ("fluent: {aoa_method: sideways}\n", "aoa_method"),
    ("fluent: {dimension: 4}\n", "dimension"),
    ("solve: {max_iterations: 0}\n", "max_iterations"),
    ("solve: {convergence_window: 2}\n", "convergence_window"),
    ("fluent: {wall_zones: []}\n", "wall_zones"),
    ("workbench: {aoa_expression: 'no placeholder here'}\n", "aoa_expression"),
])
def test_validate_static_catches_inconsistent_physics_settings(
        tmp_path, body, expected_fragment):
    with pytest.raises(ConfigError, match=expected_fragment):
        load_config(_write_cfg(tmp_path, body))


# --------------------------------------------------------------------- #
# Group: path-resolution failures point at the real problem
#
# Regression Scenario: config.yaml references a Workbench project, a
# baseline case, or an ANSYS install that has since moved, been deleted,
# or was never set. Without this, the failure only appears deep inside
# WorkbenchController/FluentController with a much less actionable
# traceback.
# Expected Behaviour: each resolver raises ConfigError naming the
# specific missing path, before any Workbench/Fluent process is launched.
# Why this test exists: this is the exact error path `doctor` and the
# orchestrator both rely on to give users an actionable message instead
# of an ANSYS stack trace.
# --------------------------------------------------------------------- #
def test_path_resolvers_reject_missing_files_by_name(tmp_path):
    cfg = load_config(_write_cfg(tmp_path, "excel: {file: nonexistent.xlsx}\n"))
    with pytest.raises(ConfigError, match="Cannot locate ANSYS"):
        cfg.ansys.resolve_awp_root()
    with pytest.raises(ConfigError, match="project_file"):
        cfg.workbench.project_path()
    with pytest.raises(ConfigError, match="baseline_case"):
        cfg.fluent.baseline_case_path()
    with pytest.raises(ConfigError, match="Experiment schedule not found"):
        cfg.excel.path()


def test_path_resolvers_succeed_once_the_files_exist(tmp_path):
    awp = tmp_path / "ansys"
    awp.mkdir()
    (awp / "Framework" / "bin" / "Win64").mkdir(parents=True)
    (awp / "Framework" / "bin" / "Win64" / "RunWB2.exe").write_text("stub")
    wbpj = tmp_path / "p.wbpj"
    wbpj.write_text("stub")
    cfg = load_config(_write_cfg(tmp_path, f"""
ansys: {{awp_root: "{awp.as_posix()}"}}
workbench: {{project_file: "{wbpj.as_posix()}"}}
excel: {{file: nonexistent.xlsx}}
"""))
    assert cfg.ansys.resolve_awp_root() == awp
    assert cfg.ansys.resolve_runwb2().name == "RunWB2.exe"
    assert cfg.workbench.project_path() == wbpj
