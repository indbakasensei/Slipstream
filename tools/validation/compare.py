#!/usr/bin/env python3
"""Compare Slipstream's simulated results against a trusted reference
dataset (e.g. published benchmark polar data).

Pure, stdlib-only (csv, json, math) — no pandas/numpy, no ``cfdauto``
import, and never wired into the runtime engine (CLI, GUI, or
Orchestrator). This is validation tooling, run by hand or from a release
job; see docs/validation/VALIDATION.md for the full workflow.

Usage::

    python -m tools.validation.compare reference.csv slipstream.csv \\
        --out-dir docs/validation/benchmark --plots

Both CSVs are expected to have at least ``AOA_deg`` and ``Velocity_m_s``
columns (the same join key used by the app's Excel schedule) plus one
column per metric being compared (default: ``CL``, ``CD``, ``L/D``).
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_JOIN_KEYS = ("AOA_deg", "Velocity_m_s")


# --------------------------------------------------------------------------- #
# CSV I/O
# --------------------------------------------------------------------------- #
def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    """Read a CSV file into a list of string-valued dict rows."""
    with open(path, "r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _row_key(row: Dict[str, object]) -> Optional[Tuple[float, float]]:
    try:
        return tuple(round(float(row[k]), 6) for k in _JOIN_KEYS)  # type: ignore[return-value]
    except (KeyError, TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
@dataclass
class MetricComparison:
    """Error statistics for one metric column across all matched rows."""

    metric: str
    n: int
    mae: Optional[float]                  # Mean Absolute Error
    rmse: Optional[float]                 # Root Mean Square Error
    max_abs_error: Optional[float]
    max_abs_error_at: Optional[str]       # which (AOA, V) pair had the worst error


@dataclass
class ComparisonSummary:
    reference_path: str
    slipstream_path: str
    matched_rows: int
    unmatched_reference_rows: int
    metrics: List[MetricComparison] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #
def compare_datasets(reference_rows: Sequence[Dict[str, object]],
                     slipstream_rows: Sequence[Dict[str, object]],
                     metrics: Sequence[str] = ("CL", "CD", "L/D"),
                     *, reference_path: str = "",
                     slipstream_path: str = "") -> ComparisonSummary:
    """Join on (AOA_deg, Velocity_m_s) and compute MAE/RMSE/max-abs-error
    per metric. Never raises: a row that can't be matched, or a metric
    that can't be parsed as a number, is simply excluded from that
    metric's statistics — ``n`` always reflects exactly how many values
    were actually compared, never a guess.
    """
    sim_index: Dict[Tuple[float, float], Dict[str, object]] = {}
    for row in slipstream_rows:
        key = _row_key(row)
        if key is not None:
            sim_index[key] = row

    matched = 0
    unmatched = 0
    per_metric_errors: Dict[str, List[Tuple[Tuple[float, float], float]]] = {
        m: [] for m in metrics}

    for ref in reference_rows:
        key = _row_key(ref)
        if key is None:
            continue
        sim = sim_index.get(key)
        if sim is None:
            unmatched += 1
            continue
        matched += 1
        for metric in metrics:
            try:
                ref_v = float(ref[metric])
                sim_v = float(sim[metric])
            except (KeyError, TypeError, ValueError):
                continue
            per_metric_errors[metric].append((key, sim_v - ref_v))

    metric_results: List[MetricComparison] = []
    for metric in metrics:
        errors = per_metric_errors[metric]
        if not errors:
            metric_results.append(MetricComparison(
                metric=metric, n=0, mae=None, rmse=None,
                max_abs_error=None, max_abs_error_at=None))
            continue
        abs_errors = [abs(e) for _, e in errors]
        mae = sum(abs_errors) / len(abs_errors)
        rmse = math.sqrt(sum(e * e for _, e in errors) / len(errors))
        worst_key, worst_err = max(errors, key=lambda ke: abs(ke[1]))
        metric_results.append(MetricComparison(
            metric=metric, n=len(errors), mae=mae, rmse=rmse,
            max_abs_error=abs(worst_err),
            max_abs_error_at=f"AOA={worst_key[0]}, V={worst_key[1]}"))

    return ComparisonSummary(
        reference_path=reference_path, slipstream_path=slipstream_path,
        matched_rows=matched, unmatched_reference_rows=unmatched,
        metrics=metric_results)


# --------------------------------------------------------------------------- #
# Report writers
# --------------------------------------------------------------------------- #
def write_json_summary(summary: ComparisonSummary, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_dict(), indent=2), encoding="utf-8")
    return path


def write_csv_table(summary: ComparisonSummary, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "n", "mae", "rmse", "max_abs_error", "max_abs_error_at"])
        for m in summary.metrics:
            writer.writerow([
                m.metric, m.n,
                "" if m.mae is None else f"{m.mae:.6g}",
                "" if m.rmse is None else f"{m.rmse:.6g}",
                "" if m.max_abs_error is None else f"{m.max_abs_error:.6g}",
                m.max_abs_error_at or "",
            ])
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m tools.validation.compare",
        description="Compare a Slipstream benchmark export against a reference dataset.")
    ap.add_argument("reference", help="Path to the reference dataset CSV")
    ap.add_argument("slipstream", help="Path to the Slipstream-exported results CSV")
    ap.add_argument("--metrics", default="CL,CD,L/D",
                    help="Comma-separated metric columns to compare (default: %(default)s)")
    ap.add_argument("--out-dir", default="docs/validation/benchmark",
                    help="Directory for comparison_summary.json / comparison_table.csv "
                         "(default: %(default)s)")
    ap.add_argument("--plots", action="store_true",
                    help="Also generate CL/CD/L-D comparison plots (requires matplotlib; "
                         "see requirements-validation.txt)")
    ap.add_argument("--plots-dir", default="docs/validation/benchmark/plots",
                    help="Directory for generated plots (default: %(default)s)")
    args = ap.parse_args(argv)

    ref_rows = read_csv_rows(Path(args.reference))
    sim_rows = read_csv_rows(Path(args.slipstream))
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]

    summary = compare_datasets(ref_rows, sim_rows, metrics=metrics,
                               reference_path=str(args.reference),
                               slipstream_path=str(args.slipstream))

    json_path = write_json_summary(summary, Path(args.out_dir) / "comparison_summary.json")
    csv_path = write_csv_table(summary, Path(args.out_dir) / "comparison_table.csv")
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")
    for m in summary.metrics:
        if m.n:
            print(f"  {m.metric}: n={m.n} MAE={m.mae:.6g} RMSE={m.rmse:.6g} "
                  f"max_abs_error={m.max_abs_error:.6g} (at {m.max_abs_error_at})")
        else:
            print(f"  {m.metric}: no comparable data")

    if args.plots:
        from tools.validation.plots import generate_all_plots
        paths = generate_all_plots(ref_rows, sim_rows, Path(args.plots_dir))
        for p in paths:
            print(f"Wrote {p}")

    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
