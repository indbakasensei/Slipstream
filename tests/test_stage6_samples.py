"""Stage 6 (T7) — regression contract for the sample-data builders.

The T7 visual samples (_screens/stage6_samples.py) are a Stage 6 deliverable:
every screenshot is rendered from one of these workbooks, so a builder that
writes a broken file (or a save bug such as calling ``ws.save`` on a
Worksheet) silently corrupts the captures. These tests lock in each sample's
*shape* by loading it through the real GUI dataset path (``AppState.
load_project`` — the exact path the capture harness uses), covering the two
bugs found during the Stage 6 T10 loop in one place:

1. ``Experiment.case_id`` raises KeyError for Internal Flow projects (no
   legacy aoa/velocity slots) — exercised by ``build_internal``, whose
   workbook would previously crash ``AppState.load_project``.
2. ``ws.save`` vs ``wb.save`` — a Worksheet has no ``save``; a builder that
   uses the wrong receiver writes nothing and the loaded dataset comes back
   empty.

Pure sample-data tests: no engine, no window, no screenshot is produced.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "_screens"))          # for stage6_samples

import stage6_samples                                    # noqa: E402
from gui.state import AppState                           # noqa: E402


def _dataset(name: str, tmp_path: Path) -> AppState:
    """Build sample ``name`` and load it through the real GUI project path."""
    cfg = stage6_samples.build(name, tmp_path)
    st = AppState()
    st.load_project(str(cfg))
    return st


# --------------------------------------------------------------------- #
# Row counts — every sample must load and produce its advertised size
# --------------------------------------------------------------------- #
@pytest.mark.parametrize("name,rows", [
    ("small-aero", 8),
    ("medium-aero", 24),
    ("large-queue", 64),
    ("mixed-status", 15),
    ("internal-flow", 8),
])
def test_sample_loads_with_expected_row_count(name, rows, tmp_path):
    st = _dataset(name, tmp_path)
    assert len(st.df) == rows
    # Every sample must carry the standard output columns so the Queue,
    # Charts, and Dashboard panels all render.
    for col in ("Status", "CL", "CD", "L/D", "Lift_N", "Drag_N"):
        assert col in st.df.columns


def test_medium_aero_carries_wbp_flap_angle(tmp_path):
    st = _dataset("medium-aero", tmp_path)
    assert "FlapAngle" in st.df.columns
    assert st.wbp_names == ["FlapAngle"]
    assert st.df["FlapAngle"].notna().all()


def test_mixed_status_distribution(tmp_path):
    st = _dataset("mixed-status", tmp_path)
    dist = st.df["Status"].value_counts().to_dict()
    assert dist == {"DONE": 10, "PENDING": 3, "FAILED": 1, "SKIP": 1}


def test_small_large_all_done(tmp_path):
    for name, rows in (("small-aero", 8), ("large-queue", 64)):
        st = _dataset(name, tmp_path)
        assert st.df["Status"].eq("DONE").all()
        assert len(st.df) == rows


def test_internal_flow_sample_resolves_template_and_ids(tmp_path):
    """The internal-flow sample is the regression for the KeyError 'aoa'
    crash: it must load through the GUI path, use the metadata template, and
    form case ids without the legacy aoa/velocity slots."""
    st = _dataset("internal-flow", tmp_path)
    assert st.context.template.id == "internal-flow"
    assert len(st.df) == 8
    assert "Inlet Velocity" in st.df.columns
    assert "AOA" not in st.df.columns
    assert all(st.df["CaseID"].str.startswith("r"))
    assert st.df["Status"].eq("DONE").all()
