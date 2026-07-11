"""Sprint 1 — behavioral tests for cfdauto.state.RunState.

RunState is the crash-recovery backbone: the single-instance lock stops two
concurrent runs from corrupting one shared Workbench project, and the mesh
cache is what makes "kill the process, restart, resume" actually work
without silently reusing a stale or missing mesh. These tests target the
failure modes that matter in the field, not incidental code paths.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cfdauto.exceptions import FrameworkError    # noqa: E402
from cfdauto.models import Experiment            # noqa: E402
from cfdauto.state import RunState               # noqa: E402


def _work(tmp_path) -> Path:
    d = tmp_path / "runs"
    d.mkdir()
    return d


# --------------------------------------------------------------------- #
# Group: single-instance lock
#
# Regression Scenario: a user double-launches the tool (or a batch script
# retries) while a run against the same Workbench project is still
# active. Two processes updating one .wbpj concurrently is silent data
# corruption, not a clean error, if it isn't caught up front.
# Expected Behaviour: a second acquire while the owning process is alive
# raises FrameworkError; once the lock is released, acquiring again
# succeeds cleanly.
# Why this test exists: this is the only thing standing between "two
# runs at once" and a corrupted Workbench project.
# --------------------------------------------------------------------- #
def test_lock_blocks_a_second_run_while_the_owner_is_alive_then_releases(tmp_path):
    st = RunState(_work(tmp_path))
    st.acquire_lock()
    assert st._lock_path.read_text().strip() == str(os.getpid())

    # Our own process is (obviously) still alive, so a second attempt to
    # acquire must be treated exactly like a live concurrent run.
    with pytest.raises(FrameworkError):
        st.acquire_lock()

    st.release_lock()
    st.acquire_lock()          # must succeed now that the lock is free
    assert st._lock_path.exists()


# --------------------------------------------------------------------- #
# Group: stale lock reclaim after a crash
#
# Regression Scenario: a previous run was killed (crash, Ctrl+C, power
# loss) without reaching release_lock(), leaving cfdauto.lock behind
# with a PID that no longer exists. Without reclaim, every future run
# would refuse to start until the user manually deleted the file.
# Expected Behaviour: acquire_lock() detects the owning PID is dead,
# removes the stale lock itself, and proceeds.
# Why this test exists: directly protects the "never loses progress
# even after crashes" resume guarantee advertised in the README.
# --------------------------------------------------------------------- #
def test_acquire_lock_reclaims_a_stale_lock_from_a_dead_pid(tmp_path):
    work = _work(tmp_path)
    dead_pid = 999999999          # far outside any real OS PID range
    (work / "cfdauto.lock").write_text(str(dead_pid))

    st = RunState(work)
    st.acquire_lock()             # must not raise
    assert st._lock_path.read_text().strip() == str(os.getpid())


# --------------------------------------------------------------------- #
# Group: per-case artifact directory + result mirroring
#
# Regression Scenario: the Excel workbook is locked by the user (see
# ExcelManager.save()) at the exact moment a case finishes — the
# per-case result.json is the only copy of that result until the
# workbook can be saved.
# Expected Behaviour: case_dir() creates the folder on demand, and
# write_result_json() writes a JSON file readable back byte-for-byte.
# Why this test exists: this "never lost, even if Excel is locked"
# fallback path must work on its own, independent of ExcelManager.
# --------------------------------------------------------------------- #
def test_case_dir_and_result_json_round_trip(tmp_path):
    st = RunState(_work(tmp_path))
    exp = Experiment(row=5, aoa_deg=8.0, velocity=30.0)

    d = st.case_dir(exp)
    assert d.is_dir()
    assert d.name == exp.case_id

    payload = {"cl": 0.81, "cd": 0.034, "converged": True}
    out = st.write_result_json(exp, payload)
    assert json.loads(out.read_text()) == payload


# --------------------------------------------------------------------- #
# Group: mesh cache — the mechanism that skips Workbench re-meshing
#
# Regression Scenario A: mesh_cache.json is valid-ish but corrupted in a
# way that isn't simply "empty" (e.g. truncated mid-write by a crash, or
# hand-edited into a list). The empty-file case is already covered by
# test_v09_m1.py::test_mesh_cache_empty_file_is_harmless; this covers the
# other corruption shapes so a single bad cache file can't take down
# every future run.
# Regression Scenario B: a cached mesh's on-disk copy is deleted (user
# cleanup, disk issue) but the cache still references it — using the
# stale path would hand Fluent a mesh file that no longer exists.
# Expected Behaviour: (A) unreadable-but-non-empty cache content falls
# back to a fresh empty cache instead of raising. (B) a cache hit whose
# target file is gone is evicted and treated as a cache miss, and that
# eviction is persisted to disk.
# Why this test exists: mesh caching is a pure performance optimization
# — it must never be allowed to turn into a hard failure or hand out a
# wrong/missing mesh.
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_content", [
    "{not valid json at all",             # truncated/corrupted write
    "[1, 2, 3]",                          # valid JSON but not an object
])
def test_mesh_cache_recovers_from_corruption_other_than_empty(tmp_path, bad_content):
    work = _work(tmp_path)
    (work / "mesh_cache.json").write_text(bad_content)
    st = RunState(work)                    # must not raise during __init__
    assert st.cached_mesh("anything") is None


def test_mesh_cache_round_trips_and_self_heals_when_file_vanishes(tmp_path):
    work = _work(tmp_path)
    st = RunState(work)
    exp = Experiment(row=1, aoa_deg=4.0, velocity=20.0)
    source = work.parent / "FFF.msh"
    source.write_text("fake mesh contents")

    target = st.store_mesh(exp.geometry_key, source, exp)
    assert st.cached_mesh(exp.geometry_key) == target

    target.unlink()                        # simulate the copy vanishing
    assert st.cached_mesh(exp.geometry_key) is None
    # Re-reading the persisted cache file must reflect the eviction too.
    fresh = RunState(work)
    assert fresh.cached_mesh(exp.geometry_key) is None
