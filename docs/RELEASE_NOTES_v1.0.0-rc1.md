# Slipstream v1.0.0-rc1 — Release Notes

**Release candidate for v1.0.0.** This is the first build intended for
public GitHub release and portfolio demonstration. Full change history:
[`CHANGELOG.md`](../CHANGELOG.md). Full pre-release verification process:
[`docs/RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) and
[`docs/QA_GUIDE.md`](QA_GUIDE.md).

## Highlights

Slipstream automates ANSYS Workbench + Fluent parametric wing studies from
an Excel schedule, with a desktop GUI, crash-safe resume, mesh caching, a
SQLite provenance ledger, and — as of this release — post-batch analytics,
project management, standalone packaging, and a benchmark validation
framework. It runs entirely locally: no telemetry, no cloud dependency,
no account.

## Completed milestones this cycle (v0.9 → v1.0.0-rc1)

| Version | What shipped |
|---|---|
| v0.9 (M1–M3) | `doctor`, physics linter, `aoa_scale` fix, per-iteration telemetry, UTF-16 transcript support, license-lockout cascade detector, SQLite provenance ledger |
| v1.0.0-alpha.1 | Behavioral test hardening (config, Excel I/O, crash-recovery state, doctor) |
| v1.0.0-alpha.2 | Centralized, exception-type-driven error formatting across the CLI, GUI, and `doctor` |
| v1.0.0-alpha.3 | Study Analytics — a purely computational, read-only post-batch summary |
| v1.0.0-alpha.4 | Study Summary widget on the GUI Dashboard |
| v1.0.0-alpha.5 | Project & Study Management — project folders, metadata, recent projects, Project Selector |
| v1.0.0-alpha.6 | Packaging — PyInstaller one-folder Windows build, release scripts, centralized versioning |
| v1.0.0-alpha.7 | Benchmark validation framework — MAE/RMSE/max-error comparison tooling + deterministic plots |
| v1.0.0-rc1 | Documentation audit, version-consistency pass, release notes, changelog, QA guide, release metadata |

## New features since the alpha series began

- **Error formatting** (`cfdauto/error_formatting.py`) — every user-facing
  failure (CLI, GUI dialog, per-case log, `doctor`) now gets a title,
  possible reasons, a suggested next step, and — when available — a
  pointer to the relevant log/artifact, instead of a bare exception string.
- **Study Analytics** (`cfdauto/study_analytics.py` +
  `gui/widgets/study_summary_panel.py`) — total/successful/failed cases,
  retries, best L/D, highest lift, lowest drag, fastest convergence, and a
  fixed set of deterministic warnings, computed once per batch and shown
  live on the Dashboard.
- **Project & Study Management** (`cfdauto/project_manager.py` +
  `gui/project_selector_dialog.py`) — a standard project folder layout
  (`config/ data/ docs/ outputs/ runs/` + `project.json`), Open Recent /
  Open Existing / Create New, and a friendlier first-run experience that
  offers this dialog automatically instead of a bare empty dashboard.
- **Packaging** (`build/`) — a reproducible, one-folder PyInstaller build
  for Windows, with build/clean/release scripts and version metadata
  generated from `cfdauto.__version__` (never hand-duplicated).
- **Benchmark validation framework** (`tools/validation/`) — deterministic,
  standalone tooling to compare a Slipstream export against a trusted
  reference dataset (Mean Absolute Error, Root Mean Square Error, Maximum
  Absolute Error, plus comparison plots), and the engineering documentation
  template (`docs/validation/VALIDATION.md`) to record a real run against it.

## Testing summary

- **146 automated tests, all passing** (`python -m pytest tests/ -q`), up
  from 33 at the start of the alpha series.
- Coverage spans: config loading/validation, Excel read/write and
  crash-safe locking, resume/retry semantics, `doctor`'s environment
  checks, error formatting (every exception type + rendering contract),
  Study Analytics (tie-breaking, deterministic warnings, orchestrator
  wiring, lifecycle/reset behavior), Project Manager (creation, validation,
  recents), packaging configuration generation, first-run GUI behavior,
  and the validation comparison/plotting tools.
- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`) against the mock
  engine backend, so the full suite requires no ANSYS installation.
- CI runs the complete suite on Ubuntu and Windows, Python 3.11 and 3.12.

## Known limitations

- **No real ANSYS benchmark run recorded yet** — `docs/validation/VALIDATION.md`
  is a template with `PENDING` fields; `docs/validation/benchmark/`
  contains only placeholders. The NACA 0012 validation case itself (the
  actual benchmark run) remains outstanding for a final v1.0.0 tag.
- **No dedicated USAGE.md or CONTRIBUTING.md** — both are currently folded
  into `README.md`'s Installation/Configuration and Contributing sections.
- **Study Analytics is not ledger-backed** — the Dashboard's Study Summary
  widget shows the *most recent* batch only; browsing past studies/batches
  from the GUI (reading the SQLite ledger) is still planned
  (`docs/PRODUCT_BACKLOG.md` §4.3).
- **Packaging is Windows-only and unsigned** — no installer (MSI/NSIS), and
  the build/scripts in `build/` have not been exercised against a real
  PyInstaller run with a real ANSYS install in this cycle; see
  `build/README.md`'s "Known limitations."
- **`fluent_controller.py` / `orchestrator.py` still lack dedicated unit
  tests** — coverage there is indirect, via the mock-mode end-to-end
  pipeline tests only (tracked in `docs/PRODUCT_BACKLOG.md` §9.2).

## Future roadmap

Tracked in [`docs/CFD_PLATFORM_BLUEPRINT.md`](CFD_PLATFORM_BLUEPRINT.md)
and [`docs/PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md), explicitly out of
scope through v1.0: an interactive 3D field viewer (PyVista), a PDF/HTML
report generator, multi-turbulence-model support, an OpenFOAM backend,
ledger-backed historical analytics in the GUI, and a real NACA 0012
validation run to close out the item above.

## Acknowledgements

Built on [PySide6](https://doc.qt.io/qtforpython-6/),
[pyqtgraph](https://www.pyqtgraph.org/),
[ansys-fluent-core (PyFluent)](https://fluent.docs.pyansys.com/),
[openpyxl](https://openpyxl.readthedocs.io/),
[pandas](https://pandas.pydata.org/), [PyYAML](https://pyyaml.org/), and
[matplotlib](https://matplotlib.org/) (validation tooling only). Slipstream
is not affiliated with or endorsed by Ansys, Inc.; ANSYS, Fluent, and
Workbench are trademarks of Ansys, Inc.
