"""THE FLOOR — worker-runner abstraction in Agent Orchestrator's (AO) style.

Attribution / licence
---------------------
Adapted from Agent Orchestrator, Copyright 2026 Untrivial, licensed under the
Apache License 2.0. Modified, re-implemented port (no verbatim Go); the
machinery below derives from:

  * ``backend/internal/session_manager/manager.go`` — ``Manager.Spawn``,
    the single dispatch path: validate/preflight *before* any durable state
    exists (an unknown harness is rejected before CreateSession, so a failed
    spawn never leaves an orphan), insert the row (CDC fires
    ``session.created``), provision the workspace, launch the controller,
    then ``lifecycle.Manager.MarkSpawned`` writes the first activity fact.
    Spawn failures funnel to ``markSpawnFailedTerminated*`` — a failed run
    still ends terminated, with cleanup.
  * ``backend/pkg/agentruntime/process.go`` — one process group per agent,
    **reaped exactly once**; cancellation = graceful terminate, then kill
    after ``ShutdownGrace`` (5s) + 2s kill-wait. Here: cleanup callbacks run
    exactly once per run, however the run ends.
  * ``backend/internal/observe/reaper/reaper.go`` — a 5s probe loop that
    reports ``ProbeAlive / ProbeDead / ProbeFailed`` *facts* to the
    lifecycle manager. Load-bearing rule, kept verbatim in spirit:
    **a failed probe is NOT proof of death** — it is recorded as a fact and
    never, by itself, kills anything.
  * ``backend/internal/review/run_lifecycle.go`` — guarded run transitions
    plus launch / first-activity / idle / max-duration limits. Here:
    ``launch_timeout_s`` and ``max_duration_s`` on :class:`RunnerConfig`.
  * ``backend/internal/ports/*.go`` — hexagonal ports: the core depends on
    small interfaces; adapters are leaves. Here: :class:`WorkUnit`,
    :class:`EventSink` and :class:`Probe` are ``typing.Protocol`` ports;
    the floor's engine/tools are the adapters.

Floor fit: our "workers" are persona agents executing MCP tool calls inside
``FloorEngine.exec_*`` methods — there is no child process to spawn. The
runner therefore wraps a *work unit* (a callable) rather than a process:
preflight → lifecycle spawn → execute with heartbeat → collect result →
cleanup exactly once → terminate. The engine's job execution can sit behind
:meth:`WorkerRunner.run` without the economy, the confirmation gate or the
deterministic checks changing at all (see docs/AO_ORCHESTRATION_MAP.md §5).

Event bus: events are emitted through an injected sink with THE FLOOR's
existing signature — ``emit(type: str, payload: dict)`` — which is exactly
what ``FloorEngine._emit`` / ``economy.db.emit_event`` already provide.
Event payloads carry the AO-CDC fields (``seq`` comes from the bus itself;
here we attach ``work_order_id``, ``worker``, ``from``/``to`` on lifecycle
events) so the console consumes them like any other floor event.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Protocol, runtime_checkable

try:  # package import (normal engine use)
    from orchestrator.ao_lifecycle import (
        IllegalTransitionError,
        LifecycleEvent,
        WorkOrderLifecycle,
        WorkOrderState,
    )
except ImportError:  # standalone use: keep this module self-contained
    from ao_lifecycle import (  # type: ignore[no-redef]
        IllegalTransitionError,
        LifecycleEvent,
        WorkOrderLifecycle,
        WorkOrderState,
    )


# ---------------------------------------------------------------------------
# Ports (AO backend/internal/ports/*.go)
# ---------------------------------------------------------------------------

@runtime_checkable
class EventSink(Protocol):
    """THE FLOOR's event bus: FloorEngine._emit / economy.db.emit_event."""

    def __call__(self, type: str, payload: dict[str, Any]) -> Any: ...


@runtime_checkable
class WorkUnit(Protocol):
    """The adapter leaf: one unit of worker execution.

    ``preflight`` validates before any durable state exists (AO Spawn rule);
    ``execute`` does the work (for the floor: an ``exec_*`` family method);
    ``cleanup`` releases whatever the run held and must tolerate being the
    only method that runs after a failure.
    """

    def preflight(self) -> None: ...
    def execute(self) -> Any: ...
    def cleanup(self) -> None: ...


class CallableWorkUnit:
    """WorkUnit built from plain callables — the shape the engine already has
    (``executor(wo_id, winner)`` + verify + submit)."""

    def __init__(
        self,
        execute: Callable[[], Any],
        *,
        preflight: Optional[Callable[[], None]] = None,
        cleanup: Optional[Callable[[], None]] = None,
    ) -> None:
        self._execute = execute
        self._preflight = preflight
        self._cleanup = cleanup

    def preflight(self) -> None:
        if self._preflight is not None:
            self._preflight()

    def execute(self) -> Any:
        return self._execute()

    def cleanup(self) -> None:
        if self._cleanup is not None:
            self._cleanup()


class ProbeResult(str, Enum):
    """AO ports.Probe* facts (observe/reaper): three-valued, on purpose."""

    ALIVE = "alive"
    DEAD = "dead"
    FAILED = "failed"  # the probe itself failed — a fact, never a kill signal


@runtime_checkable
class Probe(Protocol):
    def probe(self) -> ProbeResult: ...


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class RunnerConfig:
    """Limits borrowed from AO's review run lifecycle + reaper cadence."""

    heartbeat_interval_s: float = 5.0   # AO reaper DefaultTickInterval = 5s
    launch_timeout_s: float = 30.0      # AO run LaunchTimeout analogue
    max_duration_s: float = 0.0         # 0 = unbounded (AO MaxDuration analogue)
    idle_after_s: float = 60.0          # WORKING ages to WAITING_INPUT past this


@dataclass
class RunResult:
    work_order_id: str
    worker: str
    status: str  # "completed" | "failed" | "cancelled"
    result: Any = None
    error: Optional[str] = None
    cleanup_ran: bool = False
    cleanup_error: Optional[str] = None
    probe_facts: list[str] = field(default_factory=list)
    transitions: list[str] = field(default_factory=list)


class WorkerRunner:
    """Runs one work unit behind the lifecycle machine, AO-style.

    Sequence (mirrors session_manager.Spawn + agentruntime.Process):
      1. ``preflight()`` — before the lifecycle is born; a failure here
         leaves NO durable state (AO rejects unknown harnesses pre-insert).
      2. Birth: QUEUED → SPAWNING → WORKING, each an event on the bus.
      3. ``execute()`` on a worker thread while a heartbeat thread reports
         activity facts (the runner is the observer; the lifecycle machine
         is the reducer — AO's observe → reduce split).
      4. Collect: success → WAITING_INPUT (work submitted, awaiting review —
         the *engine* drives REVIEWING/SETTLED from there); failure → FAILED.
      5. Cleanup runs exactly once, in all paths (reap-once).
      6. ``terminate()`` — idempotent (AO MarkTerminated).
    """

    def __init__(
        self,
        emit: EventSink,
        *,
        config: Optional[RunnerConfig] = None,
        probe: Optional[Probe] = None,
    ) -> None:
        self._emit = emit
        self.config = config or RunnerConfig()
        self._probe = probe

    # -- event plumbing --------------------------------------------------------

    def _forward(self, ev: LifecycleEvent) -> None:
        floor = ev.to_floor_event()
        self._emit(f"runner.{floor['type']}", floor["payload"])

    # -- the run -----------------------------------------------------------------

    def run(
        self,
        work_order_id: str | int,
        worker: str,
        unit: WorkUnit,
        *,
        cancel: Optional[threading.Event] = None,
    ) -> RunResult:
        cfg = self.config
        result = RunResult(work_order_id=str(work_order_id), worker=worker, status="failed")
        machine = WorkOrderLifecycle(work_order_id, on_event=self._forward)
        cleanup_once = threading.Lock()
        cleanup_done = False

        def cleanup() -> None:
            nonlocal cleanup_done
            with cleanup_once:
                if cleanup_done:
                    return
                cleanup_done = True
            try:
                unit.cleanup()
                result.cleanup_ran = True
            except Exception as exc:  # noqa: BLE001 — cleanup is best-effort (AO reap)
                result.cleanup_error = str(exc)[:300]

        # 1. Preflight BEFORE durable state (AO Spawn ordering rule).
        try:
            unit.preflight()
        except Exception as exc:  # noqa: BLE001
            result.error = f"preflight failed: {exc}"[:300]
            self._emit("runner.preflight_failed", {
                "work_order_id": result.work_order_id, "worker": worker,
                "error": result.error})
            return result

        # 2. Birth + spawn.
        machine.transition(WorkOrderState.QUEUED, reason="work order created")
        machine.transition(WorkOrderState.SPAWNING, reason="runner dispatch")
        machine.transition(WorkOrderState.WORKING, reason=f"{worker} executing")

        # 3. Execute with heartbeat (observer thread reports facts only).
        stop_hb = threading.Event()
        outcome: dict[str, Any] = {}

        def _execute() -> None:
            try:
                outcome["result"] = unit.execute()
            except Exception as exc:  # noqa: BLE001 — transcript must record failures
                outcome["error"] = exc

        def _heartbeat() -> None:
            while not stop_hb.wait(cfg.heartbeat_interval_s):
                machine.observe("heartbeat", time.time())
                self._emit("runner.heartbeat", {
                    "work_order_id": result.work_order_id, "worker": worker,
                    "state": machine.state.value if machine.state else None})
                if self._probe is not None:
                    fact = self._probe.probe()
                    machine.observe("probe", fact.value)
                    result.probe_facts.append(fact.value)
                    if fact is ProbeResult.FAILED:
                        # AO rule: a failed probe is a fact, NOT proof of
                        # death. Record it; never kill on it.
                        self._emit("runner.probe_failed", {
                            "work_order_id": result.work_order_id,
                            "worker": worker})

        exec_thread = threading.Thread(target=_execute, daemon=True)
        hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        started = time.monotonic()
        exec_thread.start()
        hb_thread.start()
        try:
            while exec_thread.is_alive():
                exec_thread.join(timeout=0.05)
                if cancel is not None and cancel.is_set():
                    break
                if cfg.max_duration_s and (time.monotonic() - started) > cfg.max_duration_s:
                    outcome.setdefault("error", TimeoutError(
                        f"run exceeded max_duration_s={cfg.max_duration_s}"))
                    break
        finally:
            stop_hb.set()
            hb_thread.join(timeout=1.0)

        # 4. Collect.
        try:
            if cancel is not None and cancel.is_set():
                machine.transition(WorkOrderState.CANCELLED, reason="cancelled by caller")
                result.status = "cancelled"
                result.error = "cancelled"
            elif "error" in outcome:
                machine.transition(WorkOrderState.FAILED,
                                   reason=f"execution failed: {outcome['error']}"[:200])
                result.error = str(outcome["error"])[:300]
            else:
                machine.transition(WorkOrderState.WAITING_INPUT,
                                   reason="work submitted; awaiting review")
                result.status = "completed"
                result.result = outcome.get("result")
        except IllegalTransitionError as exc:
            result.error = str(exc)[:300]

        # 5 + 6. Cleanup exactly once, then terminate (idempotent).
        cleanup()
        machine.terminate(reason=f"runner finished: {result.status}")
        result.transitions = [f"{r.from_state.value if r.from_state else '∅'}->{r.to_state.value}"
                              for r in machine.history]
        self._emit("runner.finished", {
            "work_order_id": result.work_order_id, "worker": worker,
            "status": result.status, "cleanup_ran": result.cleanup_ran,
            "error": result.error})
        return result


class RunnerPool:
    """Bounded-concurrency dispatch — AO runs many sessions in parallel and
    queues the rest (session_manager + durable queue). The floor's analogue
    is deliberately small: a thread pool capping simultaneous work orders."""

    def __init__(self, runner: WorkerRunner, *, max_concurrent: int = 4) -> None:
        self._runner = runner
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent,
                                        thread_name_prefix="floor-runner")

    def submit(self, work_order_id: str | int, worker: str, unit: WorkUnit):
        """Returns a Future[RunResult]."""
        return self._pool.submit(self._runner.run, work_order_id, worker, unit)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)
