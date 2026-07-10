#!/usr/bin/env python3
"""cfdauto command-line interface.

Usage
-----
Run the study (resumes automatically)::

    python main.py run --config config/config.yaml

Useful variants::

    python main.py run --dry-run              # validate config + schedule only
    python main.py run --max-cases 1          # smoke-test with a single case
    python main.py run --retry-failed         # re-queue FAILED rows
    python main.py run --mock                 # full pipeline, fake ANSYS
    python main.py wb-info                    # list WB systems & parameters
    python main.py init-template experiments.xlsx

Exit codes: 0 = all queued cases succeeded, 1 = at least one case failed,
2 = framework/config error (nothing was run or the batch aborted).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cfdauto.config import load_config
from cfdauto.exceptions import CFDAutoError, ConfigError, FrameworkError
from cfdauto.excel_manager import ExcelManager
from cfdauto.logging_setup import setup_logging
from cfdauto.orchestrator import (
    Orchestrator,
    build_controllers,
    summarize_schedule,
    write_summary_json,
)

log = logging.getLogger("cfdauto.main")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="config/config.yaml",
                   help="Path to the YAML configuration (default: %(default)s)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="DEBUG-level console output")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="cfdauto",
        description="Excel-driven ANSYS Workbench + Fluent AOA/velocity sweeps.")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Execute all pending experiments")
    _add_common(run)
    run.add_argument("--max-cases", type=int, default=0,
                     help="Run at most N cases (0 = all pending)")
    run.add_argument("--retry-failed", action="store_true",
                     help="Also re-queue rows whose Status is FAILED")
    run.add_argument("--dry-run", action="store_true",
                     help="Validate config + schedule and show the queue; run nothing")
    run.add_argument("--mock", action="store_true",
                     help="Use mock controllers (no ANSYS needed) — pipeline test")

    info = sub.add_parser("wb-info",
                          help="Inspect the Workbench project: systems & parameters "
                               "(use this once to find system_name / aoa_parameter)")
    _add_common(info)

    gui = sub.add_parser("gui", help="Launch the Slipstream desktop application")
    _add_common(gui)

    doc = sub.add_parser("doctor",
                         help="Diagnose the environment (paths, licences, "
                              "locks, workbook, physics linter)")
    _add_common(doc)

    # v0.9-M3: ledger commands
    st = sub.add_parser("studies", help="List studies recorded in the ledger")
    _add_common(st)

    bt = sub.add_parser("batches", help="List batches (optionally by study)")
    _add_common(bt)
    bt.add_argument("--study", help="filter by study name")

    q = sub.add_parser("query",
                       help="Read-only SQL against the ledger")
    _add_common(q)
    q.add_argument("sql", help="SELECT/WITH/EXPLAIN/PRAGMA query")

    dc = sub.add_parser("diff-config",
                        help="Show which config settings differ between two "
                             "batches (by hash)")
    _add_common(dc)
    dc.add_argument("hash_a", help="config hash (first 12 chars are enough)")
    dc.add_argument("hash_b")

    ex = sub.add_parser("export-study",
                        help="Export every case in a study to CSV")
    _add_common(ex)
    ex.add_argument("name", help="study name")
    ex.add_argument("--out", default="study_export.csv")

    tpl = sub.add_parser("init-template",
                         help="Create a fresh experiments.xlsx schedule template")
    tpl.add_argument("path", nargs="?", default="experiments.xlsx",
                     help="Output workbook path (default: %(default)s)")
    return ap


# --------------------------------------------------------------------------- #
def cmd_run(args) -> int:
    cfg = load_config(args.config)
    if args.mock:
        cfg.runtime.mock = True
    setup_logging(cfg.work_dir() / "logs", verbose=args.verbose)
    log.info("cfdauto starting — config: %s | AOA method: %s | mock: %s",
             args.config, cfg.fluent.aoa_method, cfg.runtime.mock)

    excel = ExcelManager(cfg.excel)
    from cfdauto import linter as _linter
    _findings = _linter.lint(cfg, excel.read_experiments())

    if args.dry_run:
        print(summarize_schedule(excel))
        queue = excel.pending(retry_failed=args.retry_failed,
                              rerun_stale_running=cfg.runtime.rerun_stale_running)
        print(f"Would run {len(queue)} case(s):")
        for e in queue[:25]:
            print(f"  row {e.row:>3}  AOA={e.aoa_deg:g} deg  V={e.velocity:g} m/s"
                  + (f"  extra={e.extra_wb_params}" if e.extra_wb_params else ""))
        if len(queue) > 25:
            print(f"  ... and {len(queue) - 25} more")
        print()
        _linter.report(_findings)
        # Real-run prerequisites are checked here too, so a dry run catches
        # missing baseline case / project file before an overnight launch.
        if not cfg.runtime.mock:
            checks = [("fluent.baseline_case", cfg.fluent.baseline_case_path)]
            if cfg.fluent.aoa_method == "geometry":       # WB only needed here
                checks += [("workbench.project_file", cfg.workbench.project_path),
                           ("ansys runwb2", cfg.ansys.resolve_runwb2)]
            problems = []
            for label, check in checks:
                try:
                    check()
                except ConfigError as exc:
                    problems.append(f"{label}: {exc}")
            if problems:
                print("\nBlocking problems for a real run:")
                for p in problems:
                    print("  -", p)
                return 2
        print("\nDry run OK.")
        return 0

    _linter.log_findings(_findings)
    wb, fluent = build_controllers(cfg)
    orch = Orchestrator(cfg, excel, wb, fluent)
    queued = len(excel.pending(retry_failed=args.retry_failed,
                               rerun_stale_running=cfg.runtime.rerun_stale_running))
    failures = orch.run(max_cases=args.max_cases, retry_failed=args.retry_failed)
    write_summary_json(cfg, failures, queued)
    return 1 if failures else 0


def cmd_wb_info(args) -> int:
    cfg = load_config(args.config)
    setup_logging(cfg.work_dir() / "logs", verbose=args.verbose)
    from cfdauto.workbench_controller import WorkbenchController
    out_dir = cfg.work_dir() / "wb_info"
    out_dir.mkdir(parents=True, exist_ok=True)
    info = WorkbenchController(cfg).inspect(out_dir)

    print("Systems:")
    for s in info.get("systems", []):
        print(f"  name={s.get('name')!r:16s} display={s.get('display_text')!r}"
              f"  components={s.get('components')}")
    print("\nParameters:")
    for p in info.get("parameters", []):
        print(f"  {p.get('name'):6s} {str(p.get('display_text')):30.30s} "
              f"= {p.get('value')}  ({p.get('usage')})")
    print("\nUse the system 'name' for workbench.system_name and the parameter "
          "'name' (or its display text) for workbench.aoa_parameter.")
    return 0


def cmd_doctor(args) -> int:
    from cfdauto.doctor import run_doctor
    return run_doctor(args.config)


def _ledger_cmd(name, args, **kwargs) -> int:
    """Dispatch to cfdauto.ledger_cli.cmd_* with the loaded config."""
    from cfdauto.config import load_config
    from pathlib import Path as _P
    from cfdauto import ledger_cli as _lc
    cfg = load_config(_P(args.config))
    fn = getattr(_lc, "cmd_" + name.replace("-", "_"))
    return fn(cfg, **kwargs)


def cmd_gui(args) -> int:
    """Launch the PySide6 desktop shell (imported lazily so the CLI keeps
    working on machines without the GUI extras installed)."""
    try:
        from gui.app import run_app
    except ImportError as exc:
        print("GUI dependencies missing. Install with:\n"
              "  pip install -r requirements-gui.txt\n"
              f"(import error: {exc})", file=sys.stderr)
        return 2
    return run_app(config_path=args.config)


def cmd_init_template(args) -> int:
    from tools.make_experiment_template import build_template
    path = Path(args.path)
    build_template(path)
    print(f"Template written: {path}")
    print("Fill in AOA_deg / Velocity_m_s (one experiment per row), leave "
          "Status empty, then:  python main.py run")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return cmd_run(args)
        if args.command == "wb-info":
            return cmd_wb_info(args)
        if args.command == "gui":
            return cmd_gui(args)
        if args.command == "doctor":
            return cmd_doctor(args)
        if args.command == "studies":
            return _ledger_cmd("studies", args)
        if args.command == "batches":
            return _ledger_cmd("batches", args, study=args.study)
        if args.command == "query":
            return _ledger_cmd("query", args, sql=args.sql)
        if args.command == "diff-config":
            return _ledger_cmd("diff-config", args,
                               hash_a=args.hash_a, hash_b=args.hash_b)
        if args.command == "export-study":
            from pathlib import Path as _P
            return _ledger_cmd("export-study", args,
                               name=args.name, out=_P(args.out))
        if args.command == "init-template":
            return cmd_init_template(args)
        return 2
    except (ConfigError, FrameworkError) as exc:
        print(f"\nCONFIG/FRAMEWORK ERROR: {exc}", file=sys.stderr)
        return 2
    except CFDAutoError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted — rerun the same command to resume where you "
              "left off (RUNNING rows are re-queued automatically).",
              file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
