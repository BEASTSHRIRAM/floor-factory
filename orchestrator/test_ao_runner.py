"""Standalone proof for the AO port (orchestrator/ao_lifecycle.py +
orchestrator/ao_runner.py). Runs WITHOUT touching FloorEngine: fake work
orders go through the lifecycle via WorkerRunner against an in-memory event
sink shaped like THE FLOOR's bus.

Run:  python3 -m orchestrator.test_ao_runner     (from the repo root)
  or: python3 orchestrator/test_ao_runner.py

Adapted-pattern provenance: Agent Orchestrator (Copyright 2026 Untrivial,
Apache-2.0) — see the module headers of ao_lifecycle.py / ao_runner.py.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from orchestrator.ao_lifecycle import (  # noqa: E402
        IllegalTransitionError,
        WorkOrderLifecycle,
        WorkOrderState,
        derive_display_status,
    )
    from orchestrator.ao_runner import (  # noqa: E402
        CallableWorkUnit,
        ProbeResult,
        RunnerConfig,
        WorkerRunner,
    )
except ImportError:  # package __init__ pulls engine deps (httpx); load standalone
    from ao_lifecycle import (  # type: ignore[no-redef]  # noqa: E402
        IllegalTransitionError,
        WorkOrderLifecycle,
        WorkOrderState,
        derive_display_status,
    )
    from ao_runner import (  # type: ignore[no-redef]  # noqa: E402
        CallableWorkUnit,
        ProbeResult,
        RunnerConfig,
        WorkerRunner,
    )


class Bus:
    """In-memory stand-in for FloorEngine._emit / economy.db.emit_event."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, type: str, payload: dict[str, Any]) -> None:
        self.events.append((type, dict(payload)))

    def types(self) -> list[str]:
        return [t for t, _ in self.events]


class FlakyProbe:
    """First probe fails (a FACT, not death), then reports alive."""

    def __init__(self) -> None:
        self.calls = 0

    def probe(self) -> ProbeResult:
        self.calls += 1
        return ProbeResult.FAILED if self.calls == 1 else ProbeResult.ALIVE


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        raise AssertionError(f"{name}: {detail}")


def main() -> int:
    print("== 1. Lifecycle: legal path + AO event shape ==")
    seen: list[dict[str, Any]] = []
    m = WorkOrderLifecycle("WO-1", on_event=lambda ev: seen.append(ev.to_floor_event()))
    m.transition(WorkOrderState.QUEUED, reason="created")
    m.transition(WorkOrderState.SPAWNING, reason="dispatch")
    m.transition(WorkOrderState.WORKING, reason="executing")
    m.transition(WorkOrderState.BLOCKED, reason="write hit confirmation gate")
    m.transition(WorkOrderState.WORKING, reason="human approved")
    m.transition(WorkOrderState.WAITING_INPUT, reason="submitted")
    m.transition(WorkOrderState.REVIEWING, reason="checks running")
    m.transition(WorkOrderState.SETTLED, reason="accepted")
    m.terminate(reason="cycle closed")
    check("reached TERMINATED", m.is_terminated)
    check("event types AO-shaped",
          [e["type"] for e in seen][0] == "work_order_created"
          and seen[-1]["type"] == "work_order_terminated")
    check("seq monotonic (CDC dedup key)",
          [e["payload"]["to"] for e in seen] == [
              "queued", "spawning", "working", "blocked", "working",
              "waiting_input", "reviewing", "settled", "terminated"])
    check("terminate idempotent (AO MarkTerminated)", m.terminate() is None)

    print("== 2. Illegal transitions raise ==")
    m2 = WorkOrderLifecycle("WO-2")
    try:
        m2.transition(WorkOrderState.WORKING, reason="skip the queue")
        check("unborn -> WORKING rejected", False)
    except IllegalTransitionError:
        check("unborn -> WORKING rejected", True)
    m2.transition(WorkOrderState.QUEUED)
    try:
        m2.transition(WorkOrderState.SETTLED, reason="skip everything")
        check("QUEUED -> SETTLED rejected", False)
    except IllegalTransitionError:
        check("QUEUED -> SETTLED rejected", True)

    print("== 3. Sticky BLOCKED never ages out (AO IsSticky) ==")
    m3 = WorkOrderLifecycle("WO-3")
    for s in (WorkOrderState.QUEUED, WorkOrderState.SPAWNING,
              WorkOrderState.WORKING, WorkOrderState.BLOCKED):
        m3.transition(s)
    aged = m3.age(idle_after_s=0.0, now=time.time() + 10_000)
    check("BLOCKED survives ageing", aged is None and m3.state is WorkOrderState.BLOCKED)

    print("== 4. Derived display status (never stored) ==")
    check("blocked -> awaiting_confirmation",
          derive_display_status({"state": "blocked"}) == "awaiting_confirmation")
    check("settled+paid -> paid",
          derive_display_status({"state": "settled", "paid": True}) == "paid")
    check("terminated unpaid -> terminated",
          derive_display_status({"state": "terminated", "paid": False}) == "terminated")

    print("== 5. Runner: happy path ==")
    bus = Bus()
    runner = WorkerRunner(bus, config=RunnerConfig(heartbeat_interval_s=0.05))
    cleaned: list[bool] = []
    unit = CallableWorkUnit(lambda: {"tickets_closed": 3},
                            cleanup=lambda: cleaned.append(True))
    res = runner.run("WO-10", "Maya", unit)
    check("status completed", res.status == "completed", str(res.transitions))
    check("result collected", res.result == {"tickets_closed": 3})
    check("cleanup ran exactly once", res.cleanup_ran and cleaned == [True])
    check("lifecycle events on the bus",
          "runner.work_order_created" in bus.types()
          and "runner.work_order_terminated" in bus.types()
          and "runner.finished" in bus.types())
    check("transitions legal end-to-end",
          res.transitions[-1].endswith("->terminated"), " ".join(res.transitions))

    print("== 6. Runner: failure still cleans up + terminates (AO spawn-failure funnel) ==")
    bus2 = Bus()
    runner2 = WorkerRunner(bus2, config=RunnerConfig(heartbeat_interval_s=0.05))

    def boom() -> Any:
        raise RuntimeError("MCP server exploded")

    cleaned2: list[bool] = []
    res2 = runner2.run("WO-11", "Baron", CallableWorkUnit(
        boom, cleanup=lambda: cleaned2.append(True)))
    check("status failed", res2.status == "failed")
    check("error recorded", "MCP server exploded" in (res2.error or ""))
    check("cleanup ran on failure", res2.cleanup_ran and cleaned2 == [True])
    check("still terminated", res2.transitions[-1].endswith("->terminated"))

    print("== 7. Runner: preflight failure leaves NO durable state (AO Spawn rule) ==")
    bus3 = Bus()
    runner3 = WorkerRunner(bus3, config=RunnerConfig(heartbeat_interval_s=0.05))

    def bad_preflight() -> None:
        raise ValueError("unknown target server")

    res3 = runner3.run("WO-12", "Pixel", CallableWorkUnit(
        lambda: None, preflight=bad_preflight))
    check("status failed at preflight", res3.status == "failed")
    check("no lifecycle events emitted",
          not any(t.startswith("runner.work_order") for t in bus3.types()),
          str(bus3.types()))

    print("== 8. Probe: FAILED is a fact, never a kill (AO reaper rule) ==")
    bus4 = Bus()
    probe = FlakyProbe()
    runner4 = WorkerRunner(bus4, config=RunnerConfig(heartbeat_interval_s=0.02),
                           probe=probe)
    gate = threading.Event()

    def slow() -> str:
        gate.wait(timeout=2.0)
        return "done"

    import threading as _t
    _t.Timer(0.15, gate.set).start()
    res4 = runner4.run("WO-13", "Ravi", CallableWorkUnit(slow))
    check("run completed despite failed probe", res4.status == "completed")
    check("probe_failed recorded as event", "runner.probe_failed" in bus4.types())
    check("probe facts kept", ProbeResult.FAILED.value in res4.probe_facts,
          str(res4.probe_facts))

    print("\nALL AO-PORT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
