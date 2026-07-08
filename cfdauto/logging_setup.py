"""Logging: readable console output + a complete rotating debug file.

Rules of thumb applied here:

* Console shows INFO and above — the operator's narrative of the run.
* ``logs/cfdauto.log`` captures DEBUG — every journal path, every Fluent call,
  every retry — because when case 47 of 120 fails overnight, the log file is
  the only witness.
* Each case additionally gets its own log file inside its artifact directory
  so a single failed case can be zipped up and inspected in isolation.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_CONSOLE_FMT = "%(asctime)s  %(levelname)-7s %(message)s"
_FILE_FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATE_FMT = "%H:%M:%S"


def setup_logging(log_dir: str | Path, verbose: bool = False) -> Path:
    """Configure the root logger once per process. Returns the log file path."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logfile = log_path / "cfdauto.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, _DATE_FMT))
    root.addHandler(console)

    file_h = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(logging.Formatter(_FILE_FMT))
    root.addHandler(file_h)

    # Third-party chatter stays out of the console.
    for noisy in ("grpc", "urllib3", "matplotlib", "ansys"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return logfile


def add_case_file_handler(case_dir: Path) -> logging.Handler:
    """Mirror everything into ``<case_dir>/case.log`` while a case runs."""
    handler = logging.FileHandler(case_dir / "case.log", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(_FILE_FMT))
    logging.getLogger().addHandler(handler)
    return handler


def remove_handler(handler: logging.Handler) -> None:
    logging.getLogger().removeHandler(handler)
    try:
        handler.close()
    except Exception:  # pragma: no cover - best effort
        pass


class CaseLogger(logging.LoggerAdapter):
    """Prefixes every message with the case id: ``[r05_aoa8_v30] message``."""

    def process(self, msg, kwargs):
        return f"[{self.extra['case_id']}] {msg}", kwargs


def case_logger(name: str, case_id: str) -> CaseLogger:
    return CaseLogger(logging.getLogger(name), {"case_id": case_id})
