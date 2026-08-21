"""Event bus — the engine's observation layer (v0.8 keystone).

Every interesting moment in the pipeline is published as an :class:`Event` on
an :class:`EventBus`.  The engine never knows *who* is listening: the GUI
subscribes to drive progress bars and live plots, tests subscribe to assert
behaviour, and a future v0.9 worker process will serialize the same events to
JSON Lines.  Keeping this module free of any Qt import is what preserves the
engine/shell firewall.

Event vocabulary — additive-only within a major version
-------------------------------------------------------
Phase 8F extends the legacy aero-centric payloads with a generic contract.
Every event now carries ``template_id`` and ``case_id`` so consumers are
fully template-driven.  Legacy field names (``aoa``, ``velocity``, ``cl``,`n``cd``) are preserved for backward compatibility but are absent from
templates that do not declare them.

======================  ====================================================
type                    data payload (generic)
======================  ====================================================
batch.started           total:int, rows:list[int],
                        template_id:str

case.started            row, case_id, index, total,
                        template_id, parameters:{}, extra:{}
                        (legacy: aoa, velocity)

stage                   row, case_id, stage:str,
                        state:'start|done|cached|skip|failed',
                        template_id
                        stages: mesh · fluent_launch · read_case ·
                        replace_mesh · setup · initialize · solve · extract

mesh.ready              row, case_id, path:str, cache_hit:bool

solve.progress          row, case_id, it:int, max_it:int,
                        metrics:{...},  (generic — e.g. {cl: …, cd: …})
                        (legacy: cl, cd)

fluent.iteration        it, max_it, cl, cd, residuals:{…}
                        (solver-specific; generic consumers read
                         metrics_snapshot when present)

solve.converged         row, case_id, it:int
solve.maxiter           row, case_id, it:int

case.done               row, case_id,
                        result:{cl, cd, lift_n, drag_n, …},
                        metrics:{…}  (template-declared metric map)

case.failed             row, case_id, error:str

batch.finished          ok:int, failed:int, stopped:bool,
                        template_id
======================  ====================================================

Thread-safety: ``emit`` may be called from the engine worker thread while
subscribers were registered from the UI thread; the subscriber list is guarded
by a lock and callbacks are invoked synchronously on the *emitting* thread.
GUI subscribers must therefore re-post to the UI thread themselves (the Qt
bridge does this with a queued signal).
"""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

log = logging.getLogger("cfdauto.events")

Subscriber = Callable[["Event"], None]

# --------------------------------------------------------------------------- #
# Event schema version (Phase 8F revision) — additive-only.
# Every event payload carries this integer so consumers can validate
# compatibility.  Increment when new fields are added.
# --------------------------------------------------------------------------- #
EVENT_SCHEMA_VERSION = 2

# --------------------------------------------------------------------------- #
# Event type constants (Phase 8F) — canonical names replace string literals.
# Consuming code should import these rather than hardcoding strings.
# --------------------------------------------------------------------------- #
EVT_BATCH_STARTED = "batch.started"
EVT_BATCH_FINISHED = "batch.finished"
EVT_CASE_STARTED = "case.started"
EVT_CASE_DONE = "case.done"
EVT_CASE_FAILED = "case.failed"
EVT_STAGE = "stage"
EVT_MESH_READY = "mesh.ready"
EVT_SOLVE_PROGRESS = "solve.progress"
EVT_SOLVE_CONVERGED = "solve.converged"
EVT_SOLVE_MAXITER = "solve.maxiter"
EVT_FLUENT_ITERATION = "fluent.iteration"


# --------------------------------------------------------------------------- #
# RuntimeStage enum (Phase 8F revision) — replaces free-form stage strings.
# --------------------------------------------------------------------------- #
class RuntimeStage(enum.Enum):
    """Canonical runtime stages for pipeline lifecycle events.

    Serialization: ``.value`` (the string) is the wire format; ``.name``
    is the machine key.  Consumers should compare against enum members,
    not raw strings.
    """
    PREPARING = "preparing"
    MESHING = "meshing"
    SOLVING = "solving"
    POSTPROCESS = "postprocess"
    DONE = "done"
    FAILED = "failed"

    # Backward-compatible aliases for legacy stage strings.
    # These map the old wire values to the new enum members so that
    # events emitted by code that hasn't migrated yet still work.
    @classmethod
    def from_wire(cls, value: str) -> "RuntimeStage":
        """Parse a legacy or current stage string into a RuntimeStage."""
        _LEGACY_MAP = {
            "mesh": cls.MESHING,
            "fluent_launch": cls.PREPARING,
            "read_case": cls.PREPARING,
            "replace_mesh": cls.MESHING,
            "setup": cls.SOLVING,
            "initialize": cls.SOLVING,
            "solve": cls.SOLVING,
            "extract": cls.POSTPROCESS,
        }
        # Direct match on value first.
        for member in cls:
            if member.value == value:
                return member
        return _LEGACY_MAP.get(value, cls.PREPARING)



@dataclass
class Event:
    """A single pipeline occurrence."""

    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:  # compact, log-friendly
        return f"Event({self.type}, {self.data})"


class EventBus:
    """Minimal synchronous pub/sub. Cheap enough to always exist:
    an orchestrator constructed without subscribers pays ~nothing."""

    def __init__(self) -> None:
        self._subs: List[Subscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        """Register *fn*; returns an unsubscribe function."""
        with self._lock:
            self._subs.append(fn)

        def _unsub() -> None:
            with self._lock:
                if fn in self._subs:
                    self._subs.remove(fn)

        return _unsub

    def emit(self, type_: str, **data: Any) -> None:
        # Phase 8F revision R2: inject schema version into every payload.
        data.setdefault("event_version", EVENT_SCHEMA_VERSION)
        evt = Event(type_, data)
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(evt)
            except Exception:  # a bad subscriber must never break the run
                log.exception("Event subscriber raised for %s", type_)


# --------------------------------------------------------------------------- #
# MonitorMetric view model (Phase 8F revision R1+R4).
# --------------------------------------------------------------------------- #
# Lightweight dataclass consumed by the Monitor panel.  AppState builds
# these from SimulationTemplate metadata; the monitor never imports the
# template layer directly.
@dataclass(frozen=True)
class MonitorMetric:
    """Presentation metadata for one metric tile in the Monitor panel.

    Attributes
    ----------
    key:
        Machine key (``"cl"``, ``"pressure_drop"``) — used to look up
        values in ``metrics_snapshot`` event payloads.
    display_name:
        Human label shown above the value (``"CL"``, ``"Pressure Drop"``).
    unit:
        Display unit string (``"N"``, ``"Pa"``); empty for dimensionless.
    monitor_priority:
        Lower values appear first in the tile grid.  Bookkeeping tiles
        (iterations, residual) use negative priorities so they always
        appear at the top.
    """
    key: str
    display_name: str
    unit: str = ""
    monitor_priority: int = 100


class NullBus(EventBus):
    """Explicit do-nothing bus (semantic sugar for optional params)."""

    def emit(self, type_: str, **data: Any) -> None:  # noqa: D102
        pass
