"""Event bus — the engine's observation layer (v0.8 keystone).

Every interesting moment in the pipeline is published as an :class:`Event` on
an :class:`EventBus`.  The engine never knows *who* is listening: the GUI
subscribes to drive progress bars and live plots, tests subscribe to assert
behaviour, and a future v0.9 worker process will serialize the same events to
JSON Lines.  Keeping this module free of any Qt import is what preserves the
engine/shell firewall.

Event vocabulary (v0.8) — additive-only within a major version
---------------------------------------------------------------
======================  ====================================================
type                    data payload
======================  ====================================================
batch.started           total:int, rows:list[int]
case.started            row, case_id, index, total, aoa, velocity, extra:{}
stage                   row, case_id, stage:str, state:'start|done|cached|skip|failed'
                        stages: mesh · fluent_launch · read_case ·
                        replace_mesh · setup · initialize · solve · extract
mesh.ready              row, case_id, path:str, cache_hit:bool
solve.progress          row, case_id, it:int, max_it:int, cl:float, cd:float
solve.converged         row, case_id, it:int
solve.maxiter           row, case_id, it:int
case.done               row, case_id, result:{cl, cd, lift_n, drag_n, ...}
case.failed             row, case_id, error:str
batch.finished          ok:int, failed:int, stopped:bool
======================  ====================================================

Thread-safety: ``emit`` may be called from the engine worker thread while
subscribers were registered from the UI thread; the subscriber list is guarded
by a lock and callbacks are invoked synchronously on the *emitting* thread.
GUI subscribers must therefore re-post to the UI thread themselves (the Qt
bridge does this with a queued signal).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

log = logging.getLogger("cfdauto.events")

Subscriber = Callable[["Event"], None]


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
        evt = Event(type_, data)
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(evt)
            except Exception:  # a bad subscriber must never break the run
                log.exception("Event subscriber raised for %s", type_)


class NullBus(EventBus):
    """Explicit do-nothing bus (semantic sugar for optional params)."""

    def emit(self, type_: str, **data: Any) -> None:  # noqa: D102
        pass
