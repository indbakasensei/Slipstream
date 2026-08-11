# Slipstream Release Metadata

Machine-checkable facts about this release, kept separate from the prose
in `docs/RELEASE_NOTES_v1.0.0-rc1.md`. Update this file's **Version** and
**Release name** fields for every future release; the rest changes rarely.

## Current development release

| Field | Value |
|---|---|
| Release name | Slipstream v2.2.0-dev (Neo v2.2 UI milestone) |
| Version | `v2.2.0-dev` (`cfdauto.__version__` — the single authoritative version source; see `cfdauto/__init__.py`) |
| Status | **Development — unreleased.** The Neo v2.2 UI milestone is feature-complete (Stages 1–6); platform **Phase 8 remains partial** and is future work. Not a production release. |
| Repository URL | `<GITHUB_REPOSITORY_URL>` — placeholder; fill in with the public repository URL before publishing this release |
| License | Apache License 2.0 (see [`LICENSE`](../LICENSE)) |

## Previous tagged release (v1.0.0-rc1)

The last shipped tagged release. Kept for history; the current development
work builds on top of it.

| Field | Value |
|---|---|
| Release name | Slipstream v1.0.0 Release Candidate 1 |
| Version | `v1.0.0-rc1` (`cfdauto.__version__` — the single authoritative version source; see `cfdauto/__init__.py`) |
| Repository URL | `<GITHUB_REPOSITORY_URL>` — placeholder; fill in with the public repository URL before publishing this release |
| License | Apache License 2.0 (see [`LICENSE`](../LICENSE)) |

## Supported Python versions

- 3.11
- 3.12

(Matches the CI matrix in `.github/workflows/tests.yml`.)

## Supported ANSYS versions

- Tested: ANSYS Student 2026 R1 (v261 / Fluent 26.1.0)
- Expected to work: other recent commercial ANSYS Workbench + Fluent
  installations, provided `ansys.version` and `fluent.product_version` are
  set to match (see `README.md`'s Troubleshooting section) — PyFluent's
  version-tolerant adapters (`cfdauto/fluent_controller.py`) absorb most
  API drift across Fluent 24/25/26.1, but only the Student 2026 R1 path
  above has been exercised end-to-end in this cycle.
- Not required at all for Mock mode, the GUI, packaging, or the automated
  test suite.

## Operating systems

| OS | Engine (CLI) | GUI | Packaging | ANSYS |
|---|---|---|---|---|
| Windows 10/11 | ✅ | ✅ | ✅ (only supported packaging target) | ✅ primary/tested |
| Linux | ✅ | ✅ | — | supported by PyFluent; not commonly installed in this project's testing |
| macOS | ✅ | ✅ | — | not available on Apple silicon |

CI (`.github/workflows/tests.yml`) runs the full automated suite on both
Ubuntu and Windows.

## Primary dependencies

| Package | Role | Required for |
|---|---|---|
| `pandas` | Data handling | Core engine (always) |
| `openpyxl` | Excel read/write | Core engine (always) |
| `PyYAML` | Config parsing | Core engine (always) |
| `ansys-fluent-core` (PyFluent) | Fluent solver control | Real (non-mock) runs only |
| `PySide6-Essentials` | Desktop GUI (Qt, LGPLv3) | GUI only |
| `pyqtgraph` | Live/interactive plotting | GUI only |
| `pyinstaller` | Standalone executable build | Packaging only (`build/`) |
| `matplotlib` | Benchmark comparison plots | Validation tooling only (`tools/validation/`) |

See `requirements.txt`, `requirements-gui.txt`, `requirements-build.txt`,
and `requirements-validation.txt` for exact version pins.
