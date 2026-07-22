"""Sprint 7 — behavioral tests for tools/validation/plots.py.

Skipped automatically if matplotlib isn't installed (see
requirements-validation.txt), mirroring how PySide6-dependent GUI tests
are already gated in this project. The determinism test is the one that
matters most here: the same two input CSVs must always produce
byte-identical PNGs, or a "deterministic plots" claim in
docs/validation/VALIDATION.md would be untrue.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validation.plots import (                # noqa: E402
    _with_derived_l_over_d,
    generate_all_plots,
    plot_metric,
)

_REFERENCE = [
    {"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.25", "CD": "0.012"},
    {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.63", "CD": "0.018"},
    {"AOA_deg": "8", "Velocity_m_s": "20", "CL": "1.02", "CD": "0.031"},
]
_SLIPSTREAM = [
    {"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.24", "CD": "0.013"},
    {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.65", "CD": "0.017"},
    {"AOA_deg": "8", "Velocity_m_s": "20", "CL": "1.00", "CD": "0.033"},
]


def test_plot_metric_creates_a_png_file(tmp_path):
    out = plot_metric(_REFERENCE, _SLIPSTREAM, "CL", tmp_path / "cl.png")
    assert out.exists()
    assert out.stat().st_size > 0
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_generate_all_plots_creates_cl_cd_and_derived_ld(tmp_path):
    paths = generate_all_plots(_REFERENCE, _SLIPSTREAM, tmp_path / "plots")
    names = {p.name for p in paths}
    assert names == {"cl_comparison.png", "cd_comparison.png", "ld_comparison.png"}
    for p in paths:
        assert p.exists() and p.stat().st_size > 0


def test_l_over_d_is_derived_fresh_from_cl_and_cd():
    rows = _with_derived_l_over_d([{"AOA_deg": "0", "Velocity_m_s": "20",
                                   "CL": "0.6", "CD": "0.03"}])
    assert rows[0]["L/D"] == pytest.approx(20.0)


def test_l_over_d_omitted_when_cd_is_zero_no_crash():
    rows = _with_derived_l_over_d([{"AOA_deg": "0", "Velocity_m_s": "20",
                                   "CL": "0.6", "CD": "0"}])
    assert "L/D" not in rows[0]


def test_plots_are_deterministic_same_input_same_bytes(tmp_path):
    out1 = plot_metric(_REFERENCE, _SLIPSTREAM, "CL", tmp_path / "run1.png")
    out2 = plot_metric(_REFERENCE, _SLIPSTREAM, "CL", tmp_path / "run2.png")
    assert out1.read_bytes() == out2.read_bytes()
