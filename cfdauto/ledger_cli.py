"""CLI helpers for the SQLite ledger.

Wired into ``main.py`` as subcommands::

    slipstream studies                 # list studies
    slipstream batches [--study NAME]  # list batches, optionally per study
    slipstream query "SELECT ..."      # arbitrary read-only SQL
    slipstream diff-config HASH_A HASH_B
    slipstream export-study NAME --out study.csv
"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, List

from .config import Config
from .ledger import Ledger

log = logging.getLogger("cfdauto.ledger.cli")

_READ_ONLY = re.compile(r"^\s*(SELECT|WITH|EXPLAIN|PRAGMA table_info)",
                        re.IGNORECASE)


def _open(cfg: Config) -> Ledger:
    return Ledger(cfg.work_dir() / "slipstream.db")


def cmd_studies(cfg: Config, printer=print) -> int:
    with _open_ctx(cfg) as l:
        rows = l.query(
            "SELECT s.id, s.name, s.workbook_path, s.created_at, "
            "COUNT(b.id) AS batches "
            "FROM studies s LEFT JOIN batches b ON b.study_id = s.id "
            "GROUP BY s.id ORDER BY s.created_at DESC")
    if not rows:
        printer("No studies recorded yet.")
        return 0
    _print_table(rows, printer)
    return 0


def cmd_batches(cfg: Config, study: str | None = None,
                printer=print) -> int:
    sql = ("SELECT b.id, s.name AS study, b.config_hash, b.started_at, "
           "b.finished_at, b.total_cases, b.ok_count, b.failed_count, "
           "b.stopped_early, b.slipstream_version "
           "FROM batches b JOIN studies s ON s.id = b.study_id")
    params: list[Any] = []
    if study:
        sql += " WHERE s.name = ?"
        params.append(study)
    sql += " ORDER BY b.started_at DESC LIMIT 50"
    with _open_ctx(cfg) as l:
        rows = l.query(sql, params)
    if not rows:
        printer("No batches found." + (f" (study={study!r})" if study else ""))
        return 0
    # short-hash config for readability
    for r in rows:
        r["config_hash"] = (r["config_hash"] or "")[:12]
    _print_table(rows, printer)
    return 0


def cmd_query(cfg: Config, sql: str, printer=print) -> int:
    if not _READ_ONLY.match(sql):
        printer("Refusing non-read query. Only SELECT/WITH/EXPLAIN/PRAGMA are "
                "allowed here.")
        return 2
    with _open_ctx(cfg) as l:
        rows = l.query(sql)
    if not rows:
        printer("(no rows)")
        return 0
    _print_table(rows, printer)
    return 0


def cmd_diff_config(cfg: Config, hash_a: str, hash_b: str,
                    printer=print) -> int:
    with _open_ctx(cfg) as l:
        try:
            diff = l.config_diff(hash_a, hash_b)
        except ValueError as exc:
            printer(str(exc))
            return 2
    if not diff:
        printer("Configs are identical.")
        return 0
    printer(f"{len(diff)} difference(s) between {hash_a[:12]} and {hash_b[:12]}:")
    keylen = max(len(k) for k in diff) + 2
    for k in sorted(diff):
        a, b = diff[k]
        printer(f"  {k.ljust(keylen)}  {_fmt(a)}  →  {_fmt(b)}")
    return 0


def cmd_export_study(cfg: Config, name: str, out: Path,
                     printer=print) -> int:
    sql = (
        "SELECT c.row_number, c.case_id, c.aoa_deg, c.velocity_m_s, "
        "c.status, c.cl, c.cd, c.lift_n, c.drag_n, c.iterations, "
        "c.converged, c.started_at, c.finished_at, "
        "c.artifact_dir, c.error, b.config_hash, b.started_at AS batch_started "
        "FROM cases c "
        "JOIN batches b ON b.id = c.batch_id "
        "JOIN studies s ON s.id = b.study_id "
        "WHERE s.name = ? ORDER BY b.started_at, c.row_number")
    with _open_ctx(cfg) as l:
        rows = l.query(sql, (name,))
    if not rows:
        printer(f"Study '{name}' has no cases yet.")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    printer(f"Wrote {len(rows)} rows to {out}")
    return 0


# --------------------------------------------------------------------------- #
def _fmt(v: Any) -> str:
    if isinstance(v, str) and len(v) > 40:
        return f'"{v[:37]}..."'
    return json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v


def _print_table(rows: List[dict], printer=print) -> None:
    cols = list(rows[0].keys())
    widths = {c: max(len(str(c)),
                     max(len(str(r.get(c, ""))) for r in rows))
              for c in cols}
    header = "  ".join(str(c).ljust(widths[c]) for c in cols)
    printer(header)
    printer("  ".join("-" * widths[c] for c in cols))
    for r in rows:
        printer("  ".join(str(r.get(c, "")).ljust(widths[c]) for c in cols))


class _open_ctx:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.l: Ledger | None = None

    def __enter__(self) -> Ledger:
        self.l = _open(self.cfg)
        return self.l

    def __exit__(self, *exc):
        if self.l is not None:
            self.l.close()
