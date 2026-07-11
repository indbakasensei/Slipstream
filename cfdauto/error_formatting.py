"""Centralized, human-readable error presentation.

This module owns *how an exception is explained to a user* — it never
changes what is raised, when, or why. Every raise site in the codebase is
untouched; this is a presentation layer that a handful of existing
except-blocks (CLI, GUI, orchestrator logging, doctor) opt into.

Dispatch is primarily **exception-type-driven**: most exception classes
(``MeshNotFoundError``, ``DivergedError``, ``NotConvergedError``,
``ResultExtractionError``, ``ExcelWriteError``, ``WorkbenchError``) map to one
fixed, specific explanation because the type alone already identifies the
scenario. Only the handful of exception types that legitimately cover several
distinguishable real-world scenarios (``ConfigError``, plain ``FluentError``,
plain ``FrameworkError``) additionally inspect the exception's own message —
matching the same situations already documented in README.md's
Troubleshooting section — to pick a more specific explanation.

This module must never raise. A failure anywhere inside ``format_error``
falls back to a generic-but-safe explanation rather than propagating.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .exceptions import (
    CaseError,
    CFDAutoError,
    ConfigError,
    DivergedError,
    ExcelWriteError,
    FluentError,
    FrameworkError,
    MeshNotFoundError,
    NotConvergedError,
    ResultExtractionError,
    WorkbenchError,
)


@dataclass(frozen=True)
class _ErrorProfile:
    title: str
    possible_reasons: List[str]
    suggested_action: str


@dataclass(frozen=True)
class FormattedError:
    """A ready-to-display explanation of one exception."""

    title: str
    summary: str
    possible_reasons: List[str] = field(default_factory=list)
    suggested_action: str = ""
    location: Optional[str] = None

    def render_text(self) -> str:
        """Multi-line block for the CLI, GUI dialogs, and log files."""
        lines = [self.title, self.summary]
        if self.possible_reasons:
            lines.append("")
            lines.append("Possible Reasons:")
            lines += [f"  - {r}" for r in self.possible_reasons]
        if self.suggested_action:
            lines.append("")
            lines.append("Suggested Next Step:")
            lines.append(f"  {self.suggested_action}")
        if self.location:
            lines.append("")
            lines.append("Need more information?")
            lines.append(f"  {self.location}")
        return "\n".join(lines)

    def render_compact(self) -> str:
        """Single-line form for tabular output (doctor's check rows)."""
        return f"{self.title}: {self.summary}"


# --------------------------------------------------------------------------- #
# Type-only profiles — the exception type alone fully identifies the scenario.
# --------------------------------------------------------------------------- #
def _const(profile: _ErrorProfile) -> Callable[[str], _ErrorProfile]:
    return lambda _msg: profile


_MESH_NOT_FOUND = _ErrorProfile(
    title="Mesh Not Found",
    possible_reasons=[
        "Workbench reported a successful update, but the expected .msh file "
        "was not produced.",
        "workbench.mesh_file_glob doesn't match this project's actual export "
        "filename.",
    ],
    suggested_action=(
        "Check wb_status.json and wb_update.wbjn in the case's artifact "
        "folder, and confirm workbench.mesh_file_glob against the project."
    ),
)

_DIVERGED = _ErrorProfile(
    title="Solver Diverged",
    possible_reasons=[
        "Boundary conditions, initialization, or mesh quality produced a "
        "non-finite (NaN/Inf) solution.",
        "The case is genuinely outside the solver's stable operating range "
        "(e.g. post-stall AOA, excessive Mach number).",
    ],
    suggested_action=(
        "Review the case's residuals/CL-CD history and case.log; consider a "
        "more conservative initialization, lower under-relaxation, or check "
        "the physics linter's findings for this row."
    ),
)

_NOT_CONVERGED = _ErrorProfile(
    title="Solver Did Not Converge",
    possible_reasons=[
        "solve.max_iterations was reached before CL/CD flattened within "
        "tolerance.",
        "The case may be oscillating rather than truly diverging.",
    ],
    suggested_action=(
        "Increase solve.max_iterations or solve.convergence_window, or set "
        "solve.accept_unconverged: true if a flagged result is acceptable."
    ),
)

_RESULT_EXTRACTION = _ErrorProfile(
    title="Result Extraction Error",
    possible_reasons=[
        "The configured report definitions could not be computed.",
        "A wall or inlet zone name in config.yaml doesn't match the "
        "baseline case.",
    ],
    suggested_action=(
        "Verify fluent.wall_zones and fluent.inlet_zone against "
        "`python main.py wb-info`."
    ),
)

_EXCEL_WRITE = _ErrorProfile(
    title="Excel Workbook Error",
    possible_reasons=[
        "The workbook is open in Excel (Windows file lock).",
        "The file lives on a syncing drive (OneDrive/Dropbox) that briefly "
        "locked it.",
    ],
    suggested_action=(
        "Close the workbook and rerun. The result was also written to "
        "result.json (and, if the workbook stayed locked, to "
        "recovery_results.csv), so nothing was lost."
    ),
)

_WORKBENCH = _ErrorProfile(
    title="Workbench Error",
    possible_reasons=[
        "The Workbench batch journal failed (bad parameter name, geometry "
        "update failure, or a locked/corrupted project file).",
    ],
    suggested_action=(
        "Check wb_status.json and wb_update.wbjn in the case's artifact "
        "folder, and confirm workbench.system_name / aoa_parameter with "
        "`python main.py wb-info`."
    ),
)

_CASE_GENERIC = _ErrorProfile(
    title="Case Error",
    possible_reasons=[
        "This experiment failed for a reason not covered by a more "
        "specific category.",
    ],
    suggested_action="Check the case's log file for the full detail.",
)

_APPLICATION_GENERIC = _ErrorProfile(
    title="Application Error",
    possible_reasons=["An internal Slipstream error occurred."],
    suggested_action="Check the log file for the full detail.",
)

_UNEXPECTED = _ErrorProfile(
    title="Unexpected Error",
    possible_reasons=[
        "This is likely an unhandled edge case rather than a known failure "
        "mode.",
    ],
    suggested_action=(
        "Check the full traceback in the log file; consider filing an "
        "issue if it repeats."
    ),
)


# --------------------------------------------------------------------------- #
# Message-refined profiles — only for exception types broad enough to cover
# several genuinely different real-world scenarios (mirrors README's own
# Troubleshooting section).
# --------------------------------------------------------------------------- #
def _config_profile(msg: str) -> _ErrorProfile:
    lower = msg.lower()
    if lower.startswith("unknown"):
        return _ErrorProfile(
            title="Configuration Error",
            possible_reasons=[
                "A key in config.yaml is misspelled or renamed.",
                "The config file was copied from a different or older "
                "Slipstream project.",
            ],
            suggested_action=(
                "Compare the offending key against the Configuration "
                "reference in README.md, or run `python main.py doctor`."
            ),
        )
    if "cannot locate ansys" in lower or "awp_root" in lower:
        return _ErrorProfile(
            title="Configuration Error",
            possible_reasons=[
                "ANSYS is not installed at any of the standard locations.",
                "ansys.awp_root is empty and the AWP_ROOT<version> "
                "environment variable is not set.",
            ],
            suggested_action=(
                "Set ansys.awp_root in config.yaml (or the AWP_ROOT<version> "
                "environment variable), then run `python main.py doctor`."
            ),
        )
    if "not found" in lower or "does not exist" in lower or "missing" in lower:
        return _ErrorProfile(
            title="Configuration Error",
            possible_reasons=[
                "A path in config.yaml (project file, baseline case, or "
                "schedule) was moved, renamed, or never created.",
            ],
            suggested_action=(
                "Verify the path in config.yaml, or regenerate the missing "
                "file."
            ),
        )
    if "validation failed" in lower:
        return _ErrorProfile(
            title="Configuration Error",
            possible_reasons=[
                "One or more solver/physics settings are internally "
                "inconsistent (see the specific field named above).",
            ],
            suggested_action=(
                "Fix the named field in config.yaml against the "
                "Configuration reference in README.md."
            ),
        )
    return _ErrorProfile(
        title="Configuration Error",
        possible_reasons=["config.yaml has an invalid or unexpected value."],
        suggested_action="Review the message above against config.yaml.",
    )


def _fluent_profile(msg: str) -> _ErrorProfile:
    lower = msg.lower()
    if ("rpc" in lower or "unavailable" in lower or "failed to launch" in lower
            or "connection refused" in lower):
        return _ErrorProfile(
            title="Fluent Solver Error",
            possible_reasons=[
                "ANSYS Student license tokens are stuck after a crashed "
                "session (the most common cause).",
                "ansys.version and fluent.product_version don't agree, so "
                "PyFluent looked up the wrong AWP_ROOT<version>.",
            ],
            suggested_action=(
                "Kill any orphaned Fluent/fl_mpi processes and wait 5-10 "
                "minutes for license tokens to release, then rerun with "
                "--retry-failed. Run `python main.py doctor` to check the "
                "version pairing."
            ),
        )
    return _ErrorProfile(
        title="Fluent Solver Error",
        possible_reasons=[
            "The Fluent session, boundary condition setup, or report "
            "definition configuration failed for this case.",
        ],
        suggested_action=(
            "Check the case's transcript.trn and case.log for the specific "
            "Fluent-side failure."
        ),
    )


def _framework_profile(msg: str) -> _ErrorProfile:
    lower = msg.lower()
    if "already owns" in lower:
        return _ErrorProfile(
            title="Environment Error",
            possible_reasons=[
                "Another Slipstream run is genuinely active against the "
                "same work directory.",
                "A previous run crashed without releasing its lock file.",
            ],
            suggested_action=(
                "Confirm no other run is active, then delete "
                "cfdauto.lock in the run's work directory if you're sure "
                "it's stale."
            ),
        )
    return _ErrorProfile(
        title="Environment Error",
        possible_reasons=[
            "A prerequisite the whole batch depends on (not one specific "
            "case) is missing or misconfigured.",
        ],
        suggested_action="Run `python main.py doctor` to pinpoint the problem.",
    )


_PROFILES: Dict[type, Callable[[str], _ErrorProfile]] = {
    MeshNotFoundError: _const(_MESH_NOT_FOUND),
    DivergedError: _const(_DIVERGED),
    NotConvergedError: _const(_NOT_CONVERGED),
    ResultExtractionError: _const(_RESULT_EXTRACTION),
    ExcelWriteError: _const(_EXCEL_WRITE),
    WorkbenchError: _const(_WORKBENCH),
    ConfigError: _config_profile,
    FluentError: _fluent_profile,
    FrameworkError: _framework_profile,
    CaseError: _const(_CASE_GENERIC),
    CFDAutoError: _const(_APPLICATION_GENERIC),
}


def format_error(exc: BaseException, *, log_path: Optional[Path] = None,
                  case_dir: Optional[Path] = None) -> FormattedError:
    """Build a :class:`FormattedError` for ``exc``. Never raises.

    ``case_dir`` (preferred) or ``log_path`` name where the caller should
    look for more detail; omitted entirely (not guessed) when neither is
    supplied.
    """
    try:
        summary = str(exc).strip() or exc.__class__.__name__
    except Exception:
        summary = getattr(exc, "__class__", type(exc)).__name__

    location: Optional[str] = None
    try:
        if case_dir is not None:
            location = str(Path(case_dir) / "case.log")
        elif log_path is not None:
            location = str(log_path)
    except Exception:
        location = None

    try:
        profile = _UNEXPECTED
        for cls in type(exc).__mro__:
            fn = _PROFILES.get(cls)
            if fn is not None:
                profile = fn(summary)
                break
    except Exception:
        profile = _UNEXPECTED

    return FormattedError(
        title=profile.title,
        summary=summary,
        possible_reasons=list(profile.possible_reasons),
        suggested_action=profile.suggested_action,
        location=location,
    )
