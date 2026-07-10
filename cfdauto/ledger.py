"""SQLite ledger — durable provenance store for every batch, case, and iteration.

Excel stays as the human-facing schedule and result table. The DB adds what
Excel can never provide:

* **config provenance** — every run stores a hash of the effective config
  plus a JSON snapshot, so ``slipstream diff-config a b`` shows exactly what
  changed between two batches. Every debugging session this week could have
  ended in ten seconds with this table.
* **per-iteration telemetry** — the ``fluent.iteration`` events from the
  M2 tap now get written to disk; you can plot the CL history of any past
  case without re-running Fluent.
* **cross-study querying** — group cases into named studies, query "best
  L/D across all wing_v2 runs at V=20 with |AOA|<8". Impossible in Excel.

The DB is written **in addition to** the workbook — nothing about Tejas's
existing workflow changes. If the DB is missing/broken, the batch still
succeeds and Excel remains authoritative.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

log = logging.getLogger("cfdauto.db")

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configs (
    hash TEXT PRIMARY KEY,        -- sha256 of the JSON snapshot
    snapshot_json TEXT NOT NULL,
    first_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS studies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    workbook_path TEXT,
    created_at TEXT NOT NULL,
    notes TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_studies_name ON studies(name);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    study_id INTEGER NOT NULL REFERENCES studies(id),
    config_hash TEXT NOT NULL REFERENCES configs(hash),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_cases INTEGER NOT NULL,
    ok_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    stopped_early INTEGER DEFAULT 0,
    slipstream_version TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    row_number INTEGER NOT NULL,
    case_id TEXT NOT NULL,
    aoa_deg REAL NOT NULL,
    velocity_m_s REAL NOT NULL,
    extra_params_json TEXT DEFAULT '{}',
    status TEXT NOT NULL,             -- DONE / FAILED / RUNNING
    started_at TEXT,
    finished_at TEXT,
    cl REAL, cd REAL, lift_n REAL, drag_n REAL,
    iterations INTEGER, converged INTEGER,
    error TEXT,
    artifact_dir TEXT
);
CREATE INDEX IF NOT EXISTS idx_cases_batch ON cases(batch_id);
CREATE INDEX IF NOT EXISTS idx_cases_case_id ON cases(case_id);

CREATE TABLE IF NOT EXISTS iterations (
    case_id INTEGER NOT NULL REFERENCES cases(id),
    iter INTEGER NOT NULL,
    cl REAL, cd REAL,
    continuity REAL, x_velocity REAL, y_velocity REAL, z_velocity REAL,
    k REAL, omega REAL,
    PRIMARY KEY (case_id, iter)
);
"""


# --------------------------------------------------------------------------- #
# JSON helpers for config hashing
# --------------------------------------------------------------------------- #
def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses/Paths to a stable JSON-compatible form."""
    if is_dataclass(obj):
        return {k: _to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(x) for x in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


def config_snapshot(cfg: Any) -> Dict[str, Any]:
    """Deterministic JSON-friendly snapshot of the effective config.

    Runtime-only knobs (work_dir, mock, retries_per_case) are excluded from
    the hash so re-running the same schedule with `mock: true` for testing
    still matches the production config's hash.
    """
    d = _to_dict(cfg)
    if isinstance(d, dict) and "runtime" in d:
        rt = dict(d["runtime"])
        for volatile in ("work_dir", "mock", "retries_per_case",
                          "stop_on_failure"):
            rt.pop(volatile, None)
        d["runtime"] = rt
    return d


def config_hash(cfg: Any) -> str:
    """Stable SHA-256 of the effective config (first 12 hex chars for logs)."""
    snap = config_snapshot(cfg)
    canonical = json.dumps(snap, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #
class Ledger:
    """Thread-safe SQLite handle. One instance per batch is fine (cheap)."""

    def __init__(self, db_path: Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # check_same_thread=False + our own mutex lets the tap and orchestrator
        # both write from different threads (rare, but the tap streams events).
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                     isolation_level=None, timeout=15.0)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    @contextmanager
    def _tx(self):
        with self._lock:
            try:
                self._conn.execute("BEGIN")
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            cur = self._conn.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cur.fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO schema_version(version, applied_at) VALUES (?,?)",
                    (SCHEMA_VERSION, datetime.now().isoformat(timespec="seconds")))
            elif row[0] < SCHEMA_VERSION:
                # Future migrations go here — v1 has no upgrade path yet.
                log.warning("DB schema is at v%d, code expects v%d.",
                            row[0], SCHEMA_VERSION)

    # ------------------------------------------------------------------ #
    # Study / batch lifecycle
    # ------------------------------------------------------------------ #
    def ensure_study(self, name: str, workbook_path: str = "",
                     notes: str = "") -> int:
        """Get-or-create a study by name."""
        with self._tx() as c:
            row = c.execute("SELECT id FROM studies WHERE name=?",
                            (name,)).fetchone()
            if row:
                return row[0]
            cur = c.execute(
                "INSERT INTO studies(name, workbook_path, created_at, notes) "
                "VALUES (?,?,?,?)",
                (name, workbook_path,
                 datetime.now().isoformat(timespec="seconds"), notes))
            return cur.lastrowid

    def record_config(self, cfg: Any) -> str:
        """Store (or match) the config snapshot; returns its hash."""
        h = config_hash(cfg)
        snap = json.dumps(config_snapshot(cfg), sort_keys=True,
                          ensure_ascii=False, indent=2)
        with self._tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO configs(hash, snapshot_json, first_seen_at) "
                "VALUES (?,?,?)",
                (h, snap, datetime.now().isoformat(timespec="seconds")))
        return h

    def start_batch(self, study_id: int, config_hash_: str, total: int,
                    slipstream_version: str) -> int:
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO batches(study_id, config_hash, started_at, "
                "total_cases, slipstream_version) VALUES (?,?,?,?,?)",
                (study_id, config_hash_,
                 datetime.now().isoformat(timespec="seconds"),
                 total, slipstream_version))
            return cur.lastrowid

    def finish_batch(self, batch_id: int, ok: int, failed: int,
                     stopped: bool) -> None:
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET finished_at=?, ok_count=?, failed_count=?, "
                "stopped_early=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"),
                 ok, failed, 1 if stopped else 0, batch_id))

    # ------------------------------------------------------------------ #
    # Case + iteration writes
    # ------------------------------------------------------------------ #
    def start_case(self, batch_id: int, row: int, case_id: str,
                   aoa_deg: float, velocity: float,
                   extra: Optional[Dict[str, Any]] = None) -> int:
        with self._tx() as c:
            cur = c.execute(
                "INSERT INTO cases(batch_id, row_number, case_id, aoa_deg, "
                "velocity_m_s, extra_params_json, status, started_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (batch_id, row, case_id, aoa_deg, velocity,
                 json.dumps(extra or {}), "RUNNING",
                 datetime.now().isoformat(timespec="seconds")))
            return cur.lastrowid

    def finish_case(self, case_pk: int, status: str,
                    result: Optional[Dict[str, Any]] = None,
                    error: Optional[str] = None,
                    artifact_dir: Optional[str] = None) -> None:
        r = result or {}
        with self._tx() as c:
            c.execute(
                "UPDATE cases SET status=?, finished_at=?, cl=?, cd=?, "
                "lift_n=?, drag_n=?, iterations=?, converged=?, error=?, "
                "artifact_dir=? WHERE id=?",
                (status,
                 datetime.now().isoformat(timespec="seconds"),
                 r.get("cl"), r.get("cd"),
                 r.get("lift_n"), r.get("drag_n"),
                 r.get("iterations"),
                 1 if r.get("converged") else 0 if "converged" in r else None,
                 error, artifact_dir, case_pk))

    def record_iteration(self, case_pk: int, it: int, cl: float, cd: float,
                         residuals: Optional[Dict[str, float]] = None) -> None:
        """Called from the telemetry tap for every fluent.iteration event."""
        r = residuals or {}
        with self._tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO iterations("
                "case_id, iter, cl, cd, continuity, x_velocity, y_velocity, "
                "z_velocity, k, omega) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (case_pk, it, cl, cd,
                 r.get("continuity"), r.get("x_velocity"),
                 r.get("y_velocity"), r.get("z_velocity"),
                 r.get("k"), r.get("omega")))

    # ------------------------------------------------------------------ #
    # Read paths (used by CLI `query` and future analytics panel)
    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(sql, list(params))
            cols = [d[0] for d in cur.description] if cur.description else []
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def config_diff(self, hash_a: str, hash_b: str) -> Dict[str, Any]:
        """Return {key: (a_value, b_value)} for every path where the two
        configs differ. Nested dicts are flattened dotted-style."""
        rows = self.query(
            "SELECT hash, snapshot_json FROM configs WHERE hash IN (?, ?)",
            (hash_a, hash_b))
        if len(rows) < 2:
            missing = [h for h in (hash_a, hash_b)
                       if h not in {r["hash"] for r in rows}]
            raise ValueError(f"Config hash(es) not found in ledger: {missing}")
        snaps = {r["hash"]: json.loads(r["snapshot_json"]) for r in rows}
        return _dict_diff(snaps[hash_a], snaps[hash_b])


def _dict_diff(a: Any, b: Any, prefix: str = "") -> Dict[str, Any]:
    """Recursive flat diff of two nested JSON structures."""
    diffs: Dict[str, Any] = {}
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            key = f"{prefix}.{k}" if prefix else k
            if k not in a:
                diffs[key] = ("<missing>", b[k])
            elif k not in b:
                diffs[key] = (a[k], "<missing>")
            else:
                diffs.update(_dict_diff(a[k], b[k], key))
    elif a != b:
        diffs[prefix] = (a, b)
    return diffs
