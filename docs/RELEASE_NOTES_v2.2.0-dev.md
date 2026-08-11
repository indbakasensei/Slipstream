# Slipstream v2.2.0-dev — Development Release Notes

**Development milestone — not a production release.** This documents the
Neo v2.2 UI milestone and the platform/template work that landed before it.
Full change history: [`CHANGELOG.md`](../CHANGELOG.md). The last *shipped*
release remains [`v1.0.0-rc1`](RELEASE_NOTES_v1.0.0-rc1.md); the current
development version is `2.2.0-dev` (`cfdauto.__version__`).

## Status

- **Neo v2.2 UI: feature-complete** (Stages 1–6).
- **Platform Phase 8: partial** — the remaining airfoil-shaped identity/write
  paths (`case_id` / `geometry_key` / `validate`, `ColumnMap` output columns,
  ledger schema, orchestrator event payloads, linter dispatch, analytics
  architecture) are scheduled future work and are **not** part of this
  release. See [`docs/PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md).
- **397 automated tests, all passing** (`python -m pytest tests/ -q`).

## Highlights

Slipstream automates ANSYS Workbench + Fluent parametric wing studies from
an Excel schedule. With Neo v2.2, the desktop shell is a modern,
information-first engineering interface — while the architecture, execution,
runtime, `AppState`, controllers, signals/slots, and workflows stay **frozen**
and unchanged behind it. The design language is defined once in
[`docs/UI_DESIGN_SYSTEM.md`](UI_DESIGN_SYSTEM.md) and implemented in
`gui/theme.py`; every public widget attribute the app and tests depend on is
preserved.

## Neo v2.2 UI — completed milestones (Stages 1–6)

| Stage | What shipped |
|---|---|
| 1 | Neo desktop shell & design system — tokens, palette, typography, shared card/chip components; Dashboard, Monitor, and Sidebar navigation redesigned |
| 2 | Queue redesign (persistent, colour-coded schedule table with run controls) and Charts redesign (interactive presets plus custom X/Y/colour, hover, PNG export) |
| 3 | Parameters redesign (metadata-driven form generated from the active template), Images workspace (thumbnail browser + zoom/pan viewer), and Console panel |
| 4 | Polish, WorkspaceHeader chrome, and empty states |
| 5 | Adaptive Workspace — user-initiated Queue collapse and Focus Mode (hides the sidebar, Queue, and docks so the current page fills the window; exact layout restoration on exit) |
| 6 | Responsive workspace hardening — dock sizing, flow-layout wrapping, and a stress matrix verified offscreen across desktop/narrow/short window sizes (16 verified screenshots) |

## Platform / template work that landed before this release

- **Template-driven architecture** — `cfdauto/platform/` pure-metadata models
  (`ParameterDefinition`, `MetricDefinition`, `SimulationTemplate`,
  `TemplateRegistry`, `StudyDefinition`) and the External Aerodynamics
  template.
- **Project template selection** — a `runtime.template` config field resolved
  through the registry; new projects pick a template and restore it on load.
- **Internal Flow template + execution strategy** — a second, domain-different
  reference template with an executable (analytical) Internal Flow workflow
  through the same strategy framework.
- **Generic experiment/model improvements** — `ParameterValue`/`MetricValue`
  containers; `Experiment`/`CaseResult` store generically with the
  airfoil-named fields kept as compatibility accessors (byte-identical
  serialization verified).
- **Template-driven StudyIO / UI behavior** — `StudyIO` maps template metadata
  to/from the spreadsheet; the GUI's parameters, queue, charts, and validation
  render from template metadata.

## Testing summary

- **397 automated tests, all passing** (`python -m pytest tests/ -q`).
- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen`) against the mock
  engine backend, so the full suite requires no ANSYS installation. This
  includes the end-to-end GUI smoke test (project load, Run All through the
  EngineWorker thread, live event handling in every panel, dataset refresh,
  chart population, mock contour images, resume semantics) plus behavioral
  tests for the Sidebar and CollapsibleSection contracts.

## Known limitations

- **Platform Phase 8 remains partial** — the aero-shaped identity/write paths
  listed under *Status* above are still airfoil-specific; generalizing them is
  future work, not part of this release.
- **v1.0.0-rc1 limitations still apply** — the NACA 0012 validation benchmark
  run is still outstanding; packaging remains Windows-only and unsigned; Study
  Analytics is not yet ledger-backed; `fluent_controller.py` / `orchestrator.py`
  still lack dedicated unit tests. See
  [`RELEASE_NOTES_v1.0.0-rc1.md`](RELEASE_NOTES_v1.0.0-rc1.md).

## Future roadmap

Tracked in [`docs/PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md) and
[`docs/PLATFORM_ARCHITECTURE.md`](PLATFORM_ARCHITECTURE.md): completing
platform **Phase 8** (generalizing the remaining identity/write paths), an
interactive 3D field viewer (PyVista), a PDF/HTML report generator,
multi-turbulence-model support, an OpenFOAM backend, ledger-backed historical
analytics in the GUI, and a real NACA 0012 validation run.

## Acknowledgements

Built on [PySide6](https://doc.qt.io/qtforpython-6/),
[pyqtgraph](https://www.pyqtgraph.org/),
[ansys-fluent-core (PyFluent)](https://fluent.docs.pyansys.com/),
[openpyxl](https://openpyxl.readthedocs.io/),
[pandas](https://pandas.pydata.org/), [PyYAML](https://pyyaml.org/), and
[matplotlib](https://matplotlib.org/) (validation tooling only). Slipstream
is not affiliated with or endorsed by Ansys, Inc.; ANSYS, Fluent, and
Workbench are trademarks of Ansys, Inc.
