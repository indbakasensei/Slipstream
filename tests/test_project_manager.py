"""Sprint 5 — behavioral tests for cfdauto.project_manager.

Project management is desktop infrastructure sitting above the existing
config.yaml workflow: it must never corrupt or overwrite an existing
project, must tell the user *everything* wrong with an invalid one (not
just the first problem found), and must track recent projects without
ever touching a real user profile during a test run (every test below
passes an explicit store_path/SLIPSTREAM_DATA_DIR override).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.project_manager import (                     # noqa: E402
    ProjectError,
    ProjectMetadata,
    ProjectValidationResult,
    _SUBDIRS,
    add_recent_project,
    create_project,
    get_user_data_directory,
    load_recent_projects,
    open_project,
    validate_project_structure,
)


# --------------------------------------------------------------------- #
# Group: project creation
# --------------------------------------------------------------------- #
def test_create_project_builds_standard_layout_and_metadata(tmp_path):
    root = tmp_path / "Wing_v2"
    meta = create_project(root, name="Wing_v2", description="Flap sweep",
                          tags=["wing", "flap"])

    for sub in _SUBDIRS:
        assert (root / sub).is_dir()
    assert (root / "project.json").exists()

    assert meta.name == "Wing_v2"
    assert meta.description == "Flap sweep"
    assert meta.tags == ["wing", "flap"]
    assert meta.project_version == 1
    assert meta.created_with.startswith("Slipstream v")
    assert meta.created and meta.last_opened

    on_disk = json.loads((root / "project.json").read_text())
    assert on_disk["name"] == "Wing_v2"
    assert set(on_disk.keys()) == {"name", "description", "created",
                                   "last_opened", "project_version",
                                   "created_with", "tags", "template_id"}


def test_create_project_rejects_existing_nonempty_directory(tmp_path):
    root = tmp_path / "taken"
    root.mkdir()
    (root / "something.txt").write_text("pre-existing file")

    with pytest.raises(ProjectError, match="already exists"):
        create_project(root, name="Taken")


def test_create_project_adopts_existing_empty_directory(tmp_path):
    root = tmp_path / "empty_dir"
    root.mkdir()          # exists, but empty — must be adopted, not rejected
    meta = create_project(root, name="Adopted")
    assert meta.name == "Adopted"
    assert (root / "config").is_dir()


# --------------------------------------------------------------------- #
# Group: metadata defaults / empty / corrupt
# --------------------------------------------------------------------- #
def test_open_project_reads_metadata_and_bumps_last_opened(tmp_path):
    root = tmp_path / "proj"
    created = create_project(root, name="Proj")
    meta = open_project(root)
    assert meta.name == "Proj"
    assert meta.last_opened >= created.last_opened


def test_open_project_tolerates_empty_metadata_json(tmp_path):
    root = tmp_path / "bare"
    create_project(root, name="Bare")
    (root / "project.json").write_text("{}")     # empty-but-valid JSON

    meta = open_project(root)
    assert meta.name == "bare"          # falls back to the folder name
    assert meta.description == ""
    assert meta.tags == []


def test_open_project_rejects_corrupt_metadata_json(tmp_path):
    root = tmp_path / "corrupt"
    create_project(root, name="Corrupt")
    (root / "project.json").write_text("{not valid json")

    with pytest.raises(ProjectError, match="not a valid Slipstream project"):
        open_project(root)


# --------------------------------------------------------------------- #
# Group: ProjectValidationResult — must be an object, not a bare list
# --------------------------------------------------------------------- #
def test_validate_project_structure_returns_validation_result_object(tmp_path):
    root = tmp_path / "proj"
    create_project(root, name="Proj")
    result = validate_project_structure(root)
    assert isinstance(result, ProjectValidationResult)
    assert result.valid is True
    assert result.problems == []


def test_validate_project_structure_reports_every_missing_folder_at_once(tmp_path):
    root = tmp_path / "half_built"
    root.mkdir()
    (root / "config").mkdir()      # only one of five required subfolders
    (root / "project.json").write_text(json.dumps({"name": "x"}))

    result = validate_project_structure(root)
    assert result.valid is False
    missing = {p for p in result.problems if p.startswith("Missing required folder")}
    assert len(missing) == 4        # data/, docs/, outputs/, runs/ all flagged together


def test_open_project_raises_on_invalid_project(tmp_path):
    root = tmp_path / "not_a_project"
    root.mkdir()
    with pytest.raises(ProjectError):
        open_project(root)


# --------------------------------------------------------------------- #
# Group: recent projects
# --------------------------------------------------------------------- #
def test_load_recent_projects_is_empty_when_store_missing(tmp_path):
    store = tmp_path / "recents.json"
    assert load_recent_projects(store) == []


def test_load_recent_projects_recovers_from_corrupt_store(tmp_path):
    store = tmp_path / "recents.json"
    store.write_text("{not valid json at all")
    assert load_recent_projects(store) == []


def test_add_recent_project_prepends_most_recent_first(tmp_path):
    store = tmp_path / "recents.json"
    a, b = tmp_path / "a", tmp_path / "b"
    add_recent_project(a, store)
    recents = add_recent_project(b, store)
    assert recents[0] == str(b.resolve())
    assert recents[1] == str(a.resolve())


def test_add_recent_project_deduplicates_moving_entry_to_front(tmp_path):
    store = tmp_path / "recents.json"
    a, b = tmp_path / "a", tmp_path / "b"
    add_recent_project(a, store)
    add_recent_project(b, store)
    recents = add_recent_project(a, store)          # re-open 'a'
    assert recents == [str(a.resolve()), str(b.resolve())]
    assert len(recents) == 2                          # not 3 — no duplicate


def test_add_recent_project_respects_max_entries(tmp_path):
    store = tmp_path / "recents.json"
    for i in range(5):
        recents = add_recent_project(tmp_path / f"p{i}", store, max_entries=3)
    assert len(recents) == 3
    assert recents[0] == str((tmp_path / "p4").resolve())   # most recent kept


def test_create_open_open_again_yields_exactly_one_recent_entry(tmp_path):
    store = tmp_path / "recents.json"
    root = tmp_path / "cycle_proj"

    create_project(root, name="Cycle")
    recents = add_recent_project(root, store)
    assert len(recents) == 1

    open_project(root)
    recents = add_recent_project(root, store)
    assert len(recents) == 1                            # still exactly one

    open_project(root)
    recents = add_recent_project(root, store)
    assert len(recents) == 1
    assert recents == [str(root.resolve())]


# --------------------------------------------------------------------- #
# Group: user data directory helper
# --------------------------------------------------------------------- #
def test_get_user_data_directory_honors_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("SLIPSTREAM_DATA_DIR", str(tmp_path / "custom"))
    assert get_user_data_directory() == tmp_path / "custom"
