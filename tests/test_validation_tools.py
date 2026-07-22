"""Sprint 7 — behavioral tests for tools/validation (compare.py + plots.py).

These are standalone validation utilities, never wired into the runtime
app — no cfdauto import here proves that isolation. All datasets are
small, synthetic, and hand-verifiable so the metric arithmetic can be
checked exactly, not just "doesn't crash." Plot tests are skipped if
matplotlib isn't installed, mirroring how this project already gates
PySide6-dependent tests.
"""

from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.validation.compare import (                    # noqa: E402
    ComparisonSummary,
    compare_datasets,
    main as compare_main,
    read_csv_rows,
    write_csv_table,
    write_json_summary,
)


def _write_csv(path: Path, rows: list[dict]) -> Path:
    fieldnames = list(rows[0].keys()) if rows else ["AOA_deg", "Velocity_m_s", "CL", "CD"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return path


# --------------------------------------------------------------------- #
# Group: CSV parsing
# --------------------------------------------------------------------- #
def test_read_csv_rows_parses_header_and_rows(tmp_path):
    path = _write_csv(tmp_path / "ref.csv", [
        {"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.25", "CD": "0.012"},
        {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.63", "CD": "0.018"},
    ])
    rows = read_csv_rows(path)
    assert len(rows) == 2
    assert rows[0]["CL"] == "0.25"


# --------------------------------------------------------------------- #
# Group: metric calculations — exact, hand-verifiable arithmetic
# --------------------------------------------------------------------- #
def test_perfect_match_gives_zero_error_for_every_metric():
    rows = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.25", "CD": "0.012"},
           {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.63", "CD": "0.018"}]
    summary = compare_datasets(rows, rows, metrics=("CL", "CD"))
    assert summary.matched_rows == 2
    assert summary.unmatched_reference_rows == 0
    for m in summary.metrics:
        assert m.n == 2
        assert m.mae == 0.0
        assert m.rmse == 0.0
        assert m.max_abs_error == 0.0


def test_small_deviation_metrics_match_hand_computed_values():
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"},
                {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "2.0"}]
    simulated = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.1"},   # error +0.1
                {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "1.9"}]   # error -0.1
    summary = compare_datasets(reference, simulated, metrics=("CL",))
    m = summary.metrics[0]
    assert m.n == 2
    assert m.mae == pytest.approx(0.1)
    assert m.rmse == pytest.approx(math.sqrt((0.1 ** 2 + 0.1 ** 2) / 2))
    assert m.max_abs_error == pytest.approx(0.1)


def test_large_deviation_is_reflected_in_max_abs_error_and_its_location():
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"},
                {"AOA_deg": "8", "Velocity_m_s": "20", "CL": "1.0"}]
    simulated = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.01"},   # tiny error
                {"AOA_deg": "8", "Velocity_m_s": "20", "CL": "3.0"}]    # huge error
    summary = compare_datasets(reference, simulated, metrics=("CL",))
    m = summary.metrics[0]
    assert m.max_abs_error == pytest.approx(2.0)
    assert "AOA=8.0" in m.max_abs_error_at


# --------------------------------------------------------------------- #
# Group: missing values / unmatched rows / empty datasets
# --------------------------------------------------------------------- #
def test_missing_reference_metric_column_is_skipped_not_crashed():
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20"}]        # no CL at all
    simulated = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.5"}]
    summary = compare_datasets(reference, simulated, metrics=("CL",))
    assert summary.matched_rows == 1                # rows matched by AOA/V
    assert summary.metrics[0].n == 0                 # but no CL to compare
    assert summary.metrics[0].mae is None


def test_unmatched_reference_row_is_counted_not_silently_dropped():
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"},
                {"AOA_deg": "99", "Velocity_m_s": "20", "CL": "1.0"}]   # no sim match
    simulated = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"}]
    summary = compare_datasets(reference, simulated, metrics=("CL",))
    assert summary.matched_rows == 1
    assert summary.unmatched_reference_rows == 1


def test_empty_reference_dataset_returns_empty_summary_without_crashing():
    summary = compare_datasets([], [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"}])
    assert summary.matched_rows == 0
    assert summary.unmatched_reference_rows == 0
    assert all(m.n == 0 for m in summary.metrics)


def test_empty_simulated_dataset_marks_every_reference_row_unmatched():
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"},
                {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "1.0"}]
    summary = compare_datasets(reference, [])
    assert summary.matched_rows == 0
    assert summary.unmatched_reference_rows == 2


# --------------------------------------------------------------------- #
# Group: report generation
# --------------------------------------------------------------------- #
def test_write_json_summary_round_trips_exactly(tmp_path):
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0"}]
    summary = compare_datasets(reference, reference, metrics=("CL",))
    out = write_json_summary(summary, tmp_path / "comparison_summary.json")
    loaded = json.loads(out.read_text())
    assert loaded["matched_rows"] == 1
    assert loaded["metrics"][0]["metric"] == "CL"
    assert loaded["metrics"][0]["mae"] == 0.0


def test_write_csv_table_has_expected_header_and_one_row_per_metric(tmp_path):
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20", "CL": "1.0", "CD": "0.1"}]
    summary = compare_datasets(reference, reference, metrics=("CL", "CD"))
    out = write_csv_table(summary, tmp_path / "comparison_table.csv")
    rows = list(csv.reader(out.read_text().splitlines()))
    assert rows[0] == ["metric", "n", "mae", "rmse", "max_abs_error", "max_abs_error_at"]
    assert len(rows) == 3            # header + CL + CD
    assert rows[1][0] == "CL"
    assert rows[2][0] == "CD"


def test_missing_metric_renders_as_blank_csv_cells_not_the_word_none(tmp_path):
    reference = [{"AOA_deg": "0", "Velocity_m_s": "20"}]   # no CL column at all
    summary = compare_datasets(reference, reference, metrics=("CL",))
    out = write_csv_table(summary, tmp_path / "comparison_table.csv")
    rows = list(csv.reader(out.read_text().splitlines()))
    assert rows[1] == ["CL", "0", "", "", "", ""]


# --------------------------------------------------------------------- #
# Group: CLI end-to-end
# --------------------------------------------------------------------- #
def test_compare_main_writes_both_reports(tmp_path, capsys):
    ref = _write_csv(tmp_path / "reference.csv", [
        {"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.25", "CD": "0.012"},
        {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.63", "CD": "0.018"},
    ])
    sim = _write_csv(tmp_path / "slipstream.csv", [
        {"AOA_deg": "0", "Velocity_m_s": "20", "CL": "0.24", "CD": "0.013"},
        {"AOA_deg": "4", "Velocity_m_s": "20", "CL": "0.65", "CD": "0.017"},
    ])
    out_dir = tmp_path / "out"
    rc = compare_main([str(ref), str(sim), "--metrics", "CL,CD", "--out-dir", str(out_dir)])
    assert rc == 0
    assert (out_dir / "comparison_summary.json").exists()
    assert (out_dir / "comparison_table.csv").exists()
    out = capsys.readouterr().out
    assert "CL" in out and "CD" in out
