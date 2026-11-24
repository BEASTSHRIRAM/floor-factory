"""THE FLOOR — work-order / worker lifecycle state machine, adapted from
Agent Orchestrator (AO).

Attribution / licence
---------------------
Adapted from Agent Orchestrator, Copyright 2026 Untrivial, licensed under the
Apache License 2.0. This file is a *modified, re-implemented* port: no Go code
is copied verbatim; the state vocabulary, transition discipline and guardrail
rules below derive from these AO sources (paths relative to the AO repo):

  * ``backend/internal/domain/activity.go``
        ActivityState {active, idle, waiting_input, blocked, exited};
        ``IsSticky()`` (waiting_input/blocked are never demoted by time) and
        ``NeedsInput()`` (both mean "paused on the user").
  * ``backend/internal/lifecycle/manager.go``
        ``lifecycle.Manager`` — the *canonical write path*: nobody writes
        lifecycle facts except through ``MarkSpawned`` /
        ``ApplyRuntimeObservation`` / ``ApplyActivitySignal`` /
        ``MarkTerminated``. ``MarkTerminated`` is idempotent and funnels every
        terminal path through one cleanup hook (container reap).
  * ``backend/internal/domain/review.go`` + ``backend/internal/review/run_lifecycle.go``
        ReviewRunStatus {queued, launching, running, cancelling, completed,
        failed, cancelled, superseded} with guarded transitions
        (``transitionRun`` only moves a run from an explicit ``from`` set).
  * ``backend/internal/domain/session.go`` / ``backend/internal/domain/doc.go``
        Durable facts only: ``activity_state`` + ``is_terminated`` are stored;
        display status is *derived at read time*, never stored.

Floor adaptation (names documented in docs/AO_ORCHESTRATION_MAP.md)
-------------------------------------------------------------------
AO sessions are long-lived coding agents; FLOOR work orders are short jobs
(post → bid → award → execute → review → appeal → payroll). The machine below
keeps AO's two-layer shape:

  * :class:`WorkerActivity` — AO's ActivityState, verbatim semantics, for a
    floor *worker* (persona agent) across a shift.
  * :class:`WorkOrderState` — a work order's lifecycle, blending AO's session
    lifecycle (spawned → active → exited/terminated) with the review-run
    lifecycle (queued → launching → running → completed/failed/cancelled).

One floor-specific state exists: ``BLOCKED`` on a work order means "paused on
the confirmation gate" — exactly AO's ``blocked`` semantics (stopped on a
pending *decision*; automated senders must not inject input). It is sticky:
the passage of time never demotes it.

This module is self-contained (stdlib only) and writes nothing to the DB.
Every transition produces an event dict shaped like AO's CDC event
(``backend/internal/cdc/event.go``: monotonic ``seq``, ``type``, entity id,
raw ``payload``, ``createdAt``) and can be flattened to THE FLOOR's existing
event-bus shape via :meth:`LifecycleEvent.to_floor_event` for
``economy.db.emit_event(conn, type, payload)``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Worker activity — AO backend/internal/domain/activity.go, semantics verbatim
# ---------------------------------------------------------------------------

class WorkerActivity(str, Enum):
    """How busy a floor worker is, reported by the runner — never inferred."""

    ACTIVE = "active"                # executing tool calls right now
    IDLE = "idle"                    # alive, no work in hand
    WAITING_INPUT = "waiting_input"  # at an empty prompt: awaiting next job
    BLOCKED = "blocked"              # stopped on a pending human decision
    EXITED = "exited"                # terminated (fired / shift over)

    @property
    def is_sticky(self) -> bool:
        """AO ``IsSticky``: must NOT be aged/demoted by the passage of time."""
        return self in (WorkerActivity.WAITING_INPUT, WorkerActivity.BLOCKED)

    @property
    def needs_input(self) -> bool:
        """AO ``NeedsInput``: the human is the unblocker."""
        return self in (WorkerActivity.WAITING_INPUT, WorkerActivity.BLOCKED)


# ---------------------------------------------------------------------------
# Work-order lifecycle
# ---------------------------------------------------------------------------

class WorkOrderState(str, Enum):
    """Lifecycle of one floor work order.

    AO provenance per state is noted inline; the transition table below is
    the floor analogue of AO's guarded ``transitionRun`` + lifecycle.Manager
    write path.
    """

    QUEUED = "queued"            # AO ReviewRunQueued / session row created, pre-launch
    SPAWNING = "spawning"        # AO ReviewRunLaunching / session_manager.Spawn in flight
    WORKING = "working"          # AO ActivityActive — winner is executing tools
    BLOCKED = "blocked"          # AO ActivityBlocked — paused on the confirmation gate
    WAITING_INPUT = "waiting_input"  # AO ActivityWaitingInput — submitted, awaiting review slot
    REVIEWING = "reviewing"      # AO ReviewRunRunning — deterministic checks + reviewer
    REMEDIATING = "remediating"  # AO "addressing comments" — appeal rework in progress
    SETTLED = "settled"          # AO ReviewRunCompleted — accepted (payroll settles it)
    FAILED = "failed"            # AO ReviewRunFailed — rejected, appeal denied / unrecoverable
    CANCELLED = "cancelled"      # AO ReviewRunCancelled / Cancelling collapsed (no async cancel here)
    TERMINATED = "terminated"    # AO ActivityExited + is_terminated — cleanup done, absorbing


#: States after which only TERMINATED is reachable (AO: settled runs are
#: final; termination is a separate, idempotent act — MarkTerminated).
FINAL_STATES = frozenset(
    {WorkOrderState.SETTLED, WorkOrderState.FAILED, WorkOrderState.CANCELLED}
)

#: Legal transitions. Mirrors AO's discipline: every move names its allowed
#: ``from`` set explicitly (cf. run_lifecycle.transitionRun's ``from`` slice).
TRANSITIONS: dict[WorkOrderState, frozenset[WorkOrderState]] = {
    WorkOrderState.QUEUED: frozenset(
        {WorkOrderState.SPAWNING, WorkOrderState.CANCELLED, WorkOrderState.TERMINATED}
    ),
    WorkOrderState.SPAWNING: frozenset(
        {WorkOrderState.WORKING, WorkOrderState.FAILED, WorkOrderState.TERMINATED}
    ),
    WorkOrderState.WORKING: frozenset(
        {
            WorkOrderState.BLOCKED,          # a write hit the confirmation gate
            WorkOrderState.WAITING_INPUT,    # work submitted, awaiting review
            WorkOrderState.FAILED,
            WorkOrderState.CANCELLED,
            WorkOrderState.TERMINATED,
        }
    ),
    # BLOCKED is sticky (AO): only a decision (approve → WORKING, deny →
    # FAILED/CANCELLED) or termination leaves it — never a timeout.
    WorkOrderState.BLOCKED: frozenset(
        {WorkOrderState.WORKING, WorkOrderState.FAILED,
         WorkOrderState.CANCELLED, WorkOrderState.TERMINATED}
    ),
    WorkOrderState.WAITING_INPUT: frozenset(
        {WorkOrderState.REVIEWING, WorkOrderState.CANCELLED, WorkOrderState.TERMINATED}
    ),
    WorkOrderState.REVIEWING: frozenset(
        {
            WorkOrderState.SETTLED,       # accepted
            WorkOrderState.REMEDIATING,   # rejected → appeal filed → rework
            WorkOrderState.FAILED,        # rejected, no appeal / appeal denied
            WorkOrderState.TERMINATED,
        }
    ),
    WorkOrderState.REMEDIATING: frozenset(
        {WorkOrderState.WORKING, WorkOrderState.FAILED, WorkOrderState.TERMINATED}
    ),
    WorkOrderState.SETTLED: frozenset({WorkOrderState.TERMINATED}),
    WorkOrderState.FAILED: frozenset({WorkOrderState.TERMINATED}),
    WorkOrderState.CANCELLED: frozenset({WorkOrderState.TERMINATED}),
    WorkOrderState.TERMINATED: frozenset(),  # absorbing — AO is_terminated
}


class IllegalTransitionError(RuntimeError):
    """Raised on any transition outside TRANSITIONS (AO: guarded transitions
    refuse rather than silently no-op)."""


@dataclass(frozen=True)
class LifecycleEvent:
    """One state change, AO-CDC-shaped (backend/internal/cdc/event.go).

    ``seq`` is monotonic per machine (consumers dedup by it, as AO clients
    dedup by change_log seq). ``payload`` is kept as a plain dict — the
    discriminated decode lives at the transport edge, exactly as in AO.
    """

    seq: int
    type: str  # "work_order_created" | "work_order_updated" | "work_order_terminated"
    entity_id: str
    payload: dict[str, Any]
    created_at: float  # epoch seconds (AO: time.Time; epoch keeps stdlib-only)

    def to_floor_event(self) -> dict[str, Any]:
        """Flatten to THE FLOOR's event-bus shape for
        ``economy.db.emit_event(conn, type, payload)``."""
        return {"type": self.type, "payload": dict(self.payload)}


@dataclass
class TransitionRecord:
    from_state: Optional[WorkOrderState]
    to_state: WorkOrderState
    reason: str
    at: float


class WorkOrderLifecycle:
    """The canonical write path for one work order's lifecycle facts.

    AO rule (lifecycle.Manager): *nobody else writes lifecycle facts.* The
    engine should hold one machine per work order and move it only via
    :meth:`transition` / :meth:`terminate`; observers (runner heartbeats,
    probes) *report* facts through :meth:`observe` and never set state
    directly.
    """

    def __init__(
        self,
        work_order_id: str | int,
        *,
        on_event: Optional[Callable[[LifecycleEvent], None]] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.work_order_id = str(work_order_id)
        self._state: Optional[WorkOrderState] = None
        self._seq = 0
        self._on_event = on_event
        self._clock = clock
        self.history: list[TransitionRecord] = []
        self.last_activity_at: float = clock()
        #: Durable facts only (AO session.go): everything display-shaped is
        #: derived from these, never stored alongside them.
        self.facts: dict[str, Any] = {}

    # -- reads ---------------------------------------------------------------

    @property
    def state(self) -> Optional[WorkOrderState]:
        return self._state

    @property
    def is_terminated(self) -> bool:
        """AO's durable ``is_terminated`` fact."""
        return self._state is WorkOrderState.TERMINATED

    @property
    def is_final(self) -> bool:
        return self._state in FINAL_STATES

    def can_transition(self, to: WorkOrderState) -> bool:
        if self._state is None:
            return to is WorkOrderState.QUEUED
        return to in TRANSITIONS[self._state]

    # -- writes (the canonical path) ------------------------------------------

    def _emit(self, type_: str, payload: dict[str, Any]) -> LifecycleEvent:
        self._seq += 1
        ev = LifecycleEvent(
            seq=self._seq,
            type=type_,
            entity_id=self.work_order_id,
            payload=payload,
            created_at=self._clock(),
        )
        if self._on_event is not None:
            self._on_event(ev)
        return ev

    def transition(self, to: WorkOrderState, *, reason: str = "") -> LifecycleEvent:
        """Move the machine, or raise IllegalTransitionError.

        The first transition must be to QUEUED (AO: the session row exists —
        and a ``session.created`` CDC event fires — *before* anything is
        launched physically).
        """
        if not self.can_transition(to):
            raise IllegalTransitionError(
                f"work order {self.work_order_id}: "
                f"{self._state.value if self._state else '<unborn>'} -> {to.value} "
                "is not a legal transition"
            )
        prev = self._state
        now = self._clock()
        self._state = to
        self.last_activity_at = now
        self.history.append(TransitionRecord(prev, to, reason, now))
        type_ = (
            "work_order_created" if prev is None
            else "work_order_terminated" if to is WorkOrderState.TERMINATED
            else "work_order_updated"
        )
        return self._emit(type_, {
            "work_order_id": self.work_order_id,
            "from": prev.value if prev else None,
            "to": to.value,
            "reason": reason,
        })

    def terminate(self, *, reason: str = "") -> Optional[LifecycleEvent]:
        """AO ``MarkTerminated``: idempotent. Calling it on an already
        terminated machine is a no-op returning None — every terminal path
        (settle, fail, cancel, kill) may funnel through here safely."""
        if self.is_terminated:
            return None
        return self.transition(WorkOrderState.TERMINATED, reason=reason or "terminated")

    # -- observer reports (facts in, never state writes) ----------------------

    def observe(self, fact: str, value: Any) -> None:
        """Record a durable fact reported by an observer (runner heartbeat,
        probe result). Facts never move the machine by themselves — AO's
        reaper reports ProbeAlive/ProbeDead/ProbeFailed and only the
        lifecycle manager reduces them; a *failed* probe is a fact, never
        proof of death."""
        self.facts[fact] = value
        if fact == "heartbeat":
            self.last_activity_at = self._clock()

    def age(self, *, idle_after_s: float, now: Optional[float] = None) -> Optional[WorkOrderState]:
        """Time-based demotion, AO-style: only WORKING may age toward
        WAITING_INPUT when silent past ``idle_after_s``. Sticky states
        (BLOCKED) are never demoted by the passage of time (AO IsSticky).
        Returns the new state if a demotion happened, else None."""
        now = self._clock() if now is None else now
        if self._state is WorkOrderState.WORKING and (now - self.last_activity_at) >= idle_after_s:
            self.transition(WorkOrderState.WAITING_INPUT, reason="aged: no activity")
            return self._state
        return None


def derive_display_status(facts: dict[str, Any]) -> str:
    """Derived-at-read-time display status — AO's core rule (AGENTS.md:
    "Do not store derived/display session status").

    ``facts`` keys (all durable): ``state`` (WorkOrderState value),
    ``appeal`` (None | "filed" | "upheld" | "denied"), ``paid`` (bool).
    Precedence mirrors AO's service-layer derivation: terminated first,
    then blocked-on-decision, then appeal, then settled facts.
    """
    state = facts.get("state")
    if state == WorkOrderState.TERMINATED.value:
        return "paid" if facts.get("paid") else "terminated"
    if state == WorkOrderState.BLOCKED.value:
        return "awaiting_confirmation"
    if state == WorkOrderState.REVIEWING.value and facts.get("appeal") == "filed":
        return "appeal_blind_review"
    if state == WorkOrderState.REMEDIATING.value:
        return "remediating"
    if state == WorkOrderState.SETTLED.value:
        return "paid" if facts.get("paid") else "accepted"
    if state == WorkOrderState.FAILED.value:
        return "rejected"
    if state == WorkOrderState.WORKING.value:
        return "working"
    if state == WorkOrderState.SPAWNING.value:
        return "spawning"
    if state in (WorkOrderState.QUEUED.value, WorkOrderState.WAITING_INPUT.value):
        return "queued"
    if state == WorkOrderState.CANCELLED.value:
        return "cancelled"
    return "unknown"
