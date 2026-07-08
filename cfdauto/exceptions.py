"""Exception hierarchy.

The orchestrator's error policy hangs off these types:

* :class:`CaseError` and subclasses — *this case* failed; mark the row FAILED,
  clean up, move on to the next row (optionally retry first).
* :class:`FrameworkError` — configuration / environment is broken; retrying
  other rows would fail identically, so abort the whole run with a clear
  message.
"""

from __future__ import annotations


class CFDAutoError(Exception):
    """Base class for everything raised intentionally by this framework."""


# --------------------------------------------------------------------------- #
# Fatal: stop the run
# --------------------------------------------------------------------------- #
class FrameworkError(CFDAutoError):
    """Bad config, missing executables, unreadable Excel schedule, ..."""


class ConfigError(FrameworkError):
    pass


# --------------------------------------------------------------------------- #
# Per-case: mark FAILED and continue
# --------------------------------------------------------------------------- #
class CaseError(CFDAutoError):
    """A single experiment failed but the run can continue."""


class WorkbenchError(CaseError):
    """Geometry update / meshing failed inside Workbench batch."""


class MeshNotFoundError(WorkbenchError):
    """Workbench reported success but no fresh Fluent mesh file was found."""


class FluentError(CaseError):
    """Fluent launch, setup or solve failed."""


class DivergedError(FluentError):
    """Solver produced NaN/Inf or Fluent aborted the calculation."""


class NotConvergedError(FluentError):
    """Hit max_iterations without meeting the convergence criteria.

    Whether this is treated as a failure or as an accepted (flagged) result is
    a config decision — see ``solve.accept_unconverged``.
    """


class ResultExtractionError(FluentError):
    """Report definitions could not be computed or parsed."""


class ExcelWriteError(CFDAutoError):
    """Workbook could not be saved (usually: file open in Excel).

    Never fatal — results are always mirrored to per-case JSON files, so the
    orchestrator logs this loudly and keeps going.
    """
