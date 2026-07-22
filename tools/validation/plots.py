#!/usr/bin/env python3
"""Deterministic CL / CD / L-D comparison plots (reference vs. Slipstream)
generated from CSV input.

Requires matplotlib (see requirements-validation.txt) — this dependency is
deliberately isolated to this one module so ``tools.validation.compare``
(the metrics/report side) never needs it, and the rest of the app never
sees it at all. Uses the non-interactive "Agg" backend: no display, no
randomness, no timestamps embedded — the same input CSVs always produce
the same plot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from tools.validation.compare import read_csv_rows

_REFERENCE_COLOR = "#1f77b4"
_SLIPSTREAM_COLOR = "#d62728"


def _series(rows: Sequence[Dict[str, object]], x_key: str,
           y_key: str) -> List[Tuple[float, float]]:
    pts = []
    for row in rows:
        try:
            pts.append((float(row[x_key]), float(row[y_key])))
        except (KeyError, TypeError, ValueError):
            continue
    pts.sort(key=lambda p: p[0])
    return pts


def _with_derived_l_over_d(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    """Copy of ``rows`` with an "L/D" entry computed fresh from CL/CD —
    never read from a pre-existing "L/D" column, so a plotted value can
    never silently disagree with the CL/CD the same row also shows."""
    out = []
    for row in rows:
        row = dict(row)
        try:
            cl, cd = float(row["CL"]), float(row["CD"])
            if cd != 0:
                row["L/D"] = cl / cd
        except (KeyError, TypeError, ValueError):
            pass
        out.append(row)
    return out


def plot_metric(reference_rows: Sequence[Dict[str, object]],
                slipstream_rows: Sequence[Dict[str, object]],
                metric: str, out_path: Path, x_key: str = "AOA_deg") -> Path:
    """Render one reference-vs-Slipstream comparison plot to ``out_path``."""
    import matplotlib
    matplotlib.use("Agg")     # headless, deterministic — no display backend
    import matplotlib.pyplot as plt

    ref_pts = _series(reference_rows, x_key, metric)
    sim_pts = _series(slipstream_rows, x_key, metric)

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    if ref_pts:
        ax.plot(*zip(*ref_pts), marker="o", label="Reference", color=_REFERENCE_COLOR)
    if sim_pts:
        ax.plot(*zip(*sim_pts), marker="s", label="Slipstream", color=_SLIPSTREAM_COLOR)
    ax.set_xlabel(x_key)
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} vs {x_key}: Reference vs Slipstream")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)
    return out_path


def generate_all_plots(reference_rows: Sequence[Dict[str, object]],
                       slipstream_rows: Sequence[Dict[str, object]],
                       out_dir: Path) -> List[Path]:
    """Generate the three standard comparison plots: CL, CD, L/D."""
    out_dir = Path(out_dir)
    ref_ld = _with_derived_l_over_d(reference_rows)
    sim_ld = _with_derived_l_over_d(slipstream_rows)
    return [
        plot_metric(reference_rows, slipstream_rows, "CL", out_dir / "cl_comparison.png"),
        plot_metric(reference_rows, slipstream_rows, "CD", out_dir / "cd_comparison.png"),
        plot_metric(ref_ld, sim_ld, "L/D", out_dir / "ld_comparison.png"),
    ]


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m tools.validation.plots",
        description="Generate CL/CD/L-D comparison plots from two CSVs.")
    ap.add_argument("reference", help="Path to the reference dataset CSV")
    ap.add_argument("slipstream", help="Path to the Slipstream-exported results CSV")
    ap.add_argument("--out-dir", default="docs/validation/benchmark/plots",
                    help="Directory for generated PNGs (default: %(default)s)")
    args = ap.parse_args(argv)

    ref_rows = read_csv_rows(Path(args.reference))
    sim_rows = read_csv_rows(Path(args.slipstream))
    for p in generate_all_plots(ref_rows, sim_rows, Path(args.out_dir)):
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main())
