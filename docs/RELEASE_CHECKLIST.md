# Slipstream Release Checklist

Work through this list in order before tagging a release. It's a manual
checklist by design — automating the last few items (a real ANSYS run, a
human look at the packaged executable) is exactly the kind of brittle
automation Sprint 6 was told to avoid.

## Repository & code quality

- [ ] Clean repository — `git status` shows nothing unexpected staged or
      untracked; `config/config.yaml` / `experiments.xlsx` local edits are
      intentionally excluded per this project's established workflow.
- [ ] Run formatting (if/when a formatter is adopted — none is enforced
      yet; skip with a note in the release notes if so).
- [ ] Run linting (if/when a linter is adopted — none is enforced yet;
      skip with a note in the release notes if so).
- [ ] Run the complete test suite: `python -m pytest tests/ -q` — must
      show all tests passing, zero failures/errors.

## Manual GUI smoke test

- [ ] Launch the GUI from source (`python main.py gui`) with no existing
      project — confirm the first-run experience (Project Selector)
      appears instead of a bare empty dashboard.
- [ ] **Create project** — via the Project Selector, create a new project
      and confirm the standard folder layout + `project.json` appear on
      disk.
- [ ] **Open project** — reopen an existing project (including via
      **Recent projects**) and confirm it loads without error.
- [ ] **Dashboard loads** — status cards, progress bar, and the Study
      Summary panel all render (even with "no study yet" placeholders).
- [ ] **Mock CFD run** — toggle Mock mode, click **Run All**, confirm all
      rows complete DONE and the Study Summary panel populates with real
      numbers (not placeholders).
- [ ] **Real ANSYS validation (if available)** — with a real Workbench
      project + baseline case configured, run `python main.py doctor`
      clean, then a small real batch (`--max-cases 1`), and confirm a
      genuine Fluent solve completes.

## Packaged executable

- [ ] Build the executable: `powershell -ExecutionPolicy Bypass -File build\build.ps1`
      (see `build/README.md` for prerequisites).
- [ ] **Verify executable launches** — run `dist\Slipstream\Slipstream.exe`
      directly (not from source) and confirm the GUI opens and Mock mode
      still works end-to-end.
- [ ] **Verify version number** — the window title, status bar, and About
      dialog all show the expected version; right-click
      `Slipstream.exe` ▸ Properties ▸ Details shows the same version.

## Release

- [ ] Release notes prepared (what changed since the last tag — the
      `CHANGELOG.md`-style summary each sprint's commit already documents).
- [ ] Ready for Git tag — once every item above is checked, tag the
      release (e.g. `git tag v1.0.0-alpha.6`) and, if desired, attach the
      `release\Slipstream-v<version>-win64.zip` archive produced by
      `build\release.ps1` to the corresponding GitHub release.
