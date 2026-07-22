# Slipstream Validation Tooling

Standalone utilities for comparing a Slipstream benchmark run against a
trusted reference dataset. **Never wired into the runtime app** — not
imported by `main.py`, `cfdauto/`, or `gui/`; run these by hand (or from a
release job) against exported CSVs. See
[`docs/validation/VALIDATION.md`](../../docs/validation/VALIDATION.md) for
the full engineering validation write-up and workflow.

## Prerequisites

`tools/validation/compare.py` is stdlib-only — nothing to install.

`tools/validation/plots.py` needs matplotlib:

```bash
pip install -r requirements-validation.txt
```

## Input format

Both the reference CSV and the Slipstream CSV need at minimum:

```
AOA_deg, Velocity_m_s, CL, CD
```

Rows are joined on `(AOA_deg, Velocity_m_s)`. A Slipstream CSV in this
shape is exactly what `python main.py export-study <name> --out results.csv`
already produces.

## Usage

```bash
# Metrics only -> comparison_summary.json + comparison_table.csv
python -m tools.validation.compare reference.csv slipstream.csv \
    --out-dir docs/validation/benchmark

# Metrics + the three standard comparison plots
python -m tools.validation.compare reference.csv slipstream.csv \
    --out-dir docs/validation/benchmark --plots

# Plots only (re-run without recomputing metrics)
python -m tools.validation.plots reference.csv slipstream.csv \
    --out-dir docs/validation/benchmark/plots
```

## Outputs

- `comparison_summary.json` — full detail: matched/unmatched row counts,
  and per-metric Mean Absolute Error (MAE), Root Mean Square Error (RMSE),
  and Maximum Absolute Error (with which (AOA, V) pair produced it).
- `comparison_table.csv` — the same per-metric statistics as a flat table.
- `cl_comparison.png`, `cd_comparison.png`, `ld_comparison.png` — reference
  vs. Slipstream line plots (L/D is always derived fresh from CL/CD, never
  read from a possibly-stale pre-existing column).

All three are deterministic: the same two input CSVs always produce the
same numbers and the same plotted data.
