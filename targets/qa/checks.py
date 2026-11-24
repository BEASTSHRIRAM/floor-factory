"""Deterministic Reviewer checks for the QA triage department.

Mirrors orchestrator/engine.py's verify() for TicketDesk: each check
re-reads live QADesk state THROUGH THE TOOL LAYER (never the DB) and
returns findings — one per acceptance criterion — as
{"criterion": str, "passed": bool, "detail": str}.

The `call` argument is any callable with the engine's shape:
    call(tool_name: str, args: dict) -> dict
e.g. Floor.call bound to server "qa", or a DirectToolClient.call_tool
partial. All money/review decisions downstream key off these findings;
nothing here is an LLM judgement.

The flaky rule (single source of truth, also stated in jobs.json):
a test is FLAKY iff, across all recorded runs, it has >= 3 failures AND
at least one pass in a run AFTER its first failing run (it recovered at
least once — intermittent, not a hard regression). A test that starts
failing and never passes again is a regression, not flaky, however many
times it fails.
"""
from __future__ import annotations

from typing import Any, Callable

CallFn = Callable[[str, dict], dict]

FLAKY_MIN_FAILURES = 3


def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": passed, "detail": detail}


def is_flaky(history: list[dict]) -> bool:
    """history: [{run_id, outcome}] for one test, any order."""
    ordered = sorted(history, key=lambda h: h["run_id"])
    fails = [h for h in ordered if h["outcome"] == "fail"]
    if len(fails) < FLAKY_MIN_FAILURES:
        return False
    first_fail_run = fails[0]["run_id"]
    return any(h["outcome"] == "pass" and h["run_id"] > first_fail_run
               for h in ordered)


def expected_flaky_tests(call: CallFn) -> set[str]:
    """Derive the exact flaky set from recorded history, via tools only."""
    failures = call("read_list_failures", {})["failures"]
    tests = sorted({f["test_name"] for f in failures})
    flaky = set()
    for test_name in tests:
        first = next(f for f in failures if f["test_name"] == test_name)
        detail = call("read_get_failure_detail", {"failure_id": first["id"]})
        if is_flaky(detail["test_history"]):
            flaky.add(test_name)
    return flaky


def expected_verdict(new_failure_count: int) -> str:
    return "regression" if new_failure_count > 0 else "no_regression"


# ---------------------------------------------------------------------------
# Job checks — one per job template in jobs.json
# ---------------------------------------------------------------------------

def check_cluster_failures(call: CallFn, criterion: str, run_id: int) -> list[dict]:
    """Every failure in the run has a cluster assignment, and each
    assigned cluster's signature equals the failure's own signature."""
    failures = call("read_list_failures", {"run_id": run_id})["failures"]
    unassigned = [f["id"] for f in failures if f.get("cluster_id") is None]
    mismatched = []
    for f in failures:
        if f.get("cluster_id") is None:
            continue
        detail = call("read_get_failure_detail", {"failure_id": f["id"]})
        cluster = detail.get("cluster") or {}
        if cluster.get("signature") != f["signature"]:
            mismatched.append(f["id"])
    passed = bool(failures) and not unassigned and not mismatched
    return [_finding(criterion, passed,
                     f"{len(failures)} failure(s) in run {run_id}; "
                     f"unassigned: {unassigned}; signature-mismatched: {mismatched}")]


def check_quarantine_flaky(call: CallFn, criterion: str) -> list[dict]:
    """The quarantined set is EXACTLY the derived flaky set — no missing
    flaky test, no extra quarantined test. Quarantine state is read back
    per test via get_failure_detail (test_quarantined)."""
    failures = call("read_list_failures", {})["failures"]
    tests = sorted({f["test_name"] for f in failures})
    quarantined = set()
    for test_name in tests:
        first = next(f for f in failures if f["test_name"] == test_name)
        detail = call("read_get_failure_detail", {"failure_id": first["id"]})
        if detail.get("test_quarantined"):
            quarantined.add(test_name)
    expected = expected_flaky_tests(call)
    passed = quarantined == expected
    return [_finding(criterion, passed,
                     f"quarantined: {sorted(quarantined)}; "
                     f"expected exactly: {sorted(expected)}")]


def check_regression_verdict(call: CallFn, criterion: str, run_id: int) -> list[dict]:
    """A verdict is recorded for the run AND it is the only verdict
    consistent with the run's new-failure count."""
    runs = call("read_list_runs", {})["runs"]
    run = next((r for r in runs if r["id"] == run_id), None)
    if run is None:
        return [_finding(criterion, False, f"run {run_id} not found")]
    want = expected_verdict(run["new_failure_count"])
    got = run.get("regression_verdict")
    passed = got == want
    return [_finding(criterion, passed,
                     f"run {run_id} new_failure_count={run['new_failure_count']}; "
                     f"expected verdict {want!r}, recorded: {got!r}")]


CHECKS = {
    "cluster_failures": check_cluster_failures,
    "quarantine_flaky": check_quarantine_flaky,
    "regression_verdict": check_regression_verdict,
}
