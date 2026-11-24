#!/usr/bin/env python3
"""End-to-end verification for the QA triage workplace (targets/qa).

Requires the QADesk app running:  uvicorn app:app --port 8103

Phases:
  1. Exercise EVERY tool (reads + writes) in direct mode, using the
     tool_specs mapping from department.json — the same direct-mode tool
     layer shape the orchestrator uses (FLOOR_MCP_MODE=direct).
  2. Reset, then run all three jobs from jobs.json end-to-end with a
     deterministic worker (post -> execute tools -> Reviewer checks via
     checks.py). All checks must pass.
  3. MCP over stdio: spawn mcp_server.py with the official mcp client,
     list tools (expect the 7 allowlisted), call two reads.

Exit code 0 iff every assertion passes. Prints one line per assertion.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checks as CHECKS  # noqa: E402

BASE_URL = os.environ.get("QA_URL", "http://localhost:8103").rstrip("/")
MANIFEST = json.loads((HERE / "department.json").read_text())
JOBS = json.loads((HERE / "jobs.json").read_text())
TOOL_SPECS = MANIFEST["tool_specs"]
PATH_PARAMS = ("failure_id", "run_id")

RESULTS: list[tuple[str, bool, str]] = []


def expect(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}  {detail}")


# ---------------------------------------------------------------------------
# Direct-mode tool client (mirrors mcp_manager/orchestrator direct fallback)
# ---------------------------------------------------------------------------

def call_tool(tool_name: str, args: dict | None = None) -> dict:
    args = dict(args or {})
    spec = TOOL_SPECS[tool_name]
    path = spec["path"]
    remaining = dict(args)
    for key in list(remaining):
        token = "{" + key + "}"
        if token in path:
            path = path.replace(token, str(remaining.pop(key)))
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        if spec["method"] == "GET":
            resp = client.get(path, params=remaining or None)
        else:
            resp = client.request(spec["method"], path, json=remaining)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        return {"error": detail, "status_code": resp.status_code}
    return resp.json()


def call(tool_name: str, args: dict | None = None) -> dict:
    return call_tool(tool_name, args)


def admin_reset() -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        resp = client.post("/admin/reset")
        resp.raise_for_status()
        return resp.json()


def latest_run_id() -> int:
    runs = call("read_list_runs", {})["runs"]
    return max(r["id"] for r in runs)


# ---------------------------------------------------------------------------
# Phase 1 — exercise every tool
# ---------------------------------------------------------------------------

def phase1() -> None:
    print("\n== Phase 1: exercise every tool (direct mode) ==")
    out = admin_reset()
    expect("reset reseeds dataset", out == {"reset": True, "runs": 6, "failures": 25},
           str(out))

    runs = call("read_list_runs", {})
    expect("read_list_runs: 6 runs", runs.get("count") == 6, f"count={runs.get('count')}")
    run6 = next(r for r in runs["runs"] if r["id"] == latest_run_id())
    expect("read_list_runs: overnight run failure_count=6, new_failure_count=1",
           run6["failure_count"] == 6 and run6["new_failure_count"] == 1,
           f"failure_count={run6['failure_count']} new={run6['new_failure_count']}")

    all_f = call("read_list_failures", {})
    expect("read_list_failures: 25 failures", all_f.get("count") == 25,
           f"count={all_f.get('count')}")
    f6 = call("read_list_failures", {"run_id": run6["id"]})
    expect("read_list_failures(run 6): 6 failures", f6.get("count") == 6,
           f"count={f6.get('count')}")
    new_in_6 = [f for f in f6["failures"] if f["is_new_signature"]]
    expect("exactly 1 new-signature failure in run 6 (search ranking)",
           len(new_in_6) == 1 and "test_search_ranking_order" in new_in_6[0]["test_name"],
           f"new={[f['test_name'] for f in new_in_6]}")

    detail = call("read_get_failure_detail", {"failure_id": f6["failures"][0]["id"]})
    expect("read_get_failure_detail: history of 6 runs + signature stats",
           len(detail.get("test_history", [])) == 6
           and detail["signature_stats"]["total_failures"] >= 1,
           f"history={len(detail.get('test_history', []))}")

    clustered = call("write_cluster_failures", {"run_id": run6["id"], "author": "verify"})
    expect("write_cluster_failures(run 6): 6 assigned into 5 clusters",
           clustered.get("assigned") == 6 and len(clustered.get("clusters", [])) == 5,
           f"assigned={clustered.get('assigned')} clusters={len(clustered.get('clusters', []))}")
    again = call("write_cluster_failures", {"run_id": run6["id"], "author": "verify"})
    expect("write_cluster_failures is idempotent (0 newly assigned)",
           again.get("assigned") == 0, f"assigned={again.get('assigned')}")

    flaky = sorted(CHECKS.expected_flaky_tests(call))
    expect("derived flaky set is exactly the 3 planted flaky tests",
           len(flaky) == 3 and all(
               any(k in t for k in ("test_pay_now_button", "test_webhook_delivery",
                                    "test_apply_discount_banner")) for t in flaky),
           f"flaky={flaky}")
    q = call("write_quarantine_test", {"test_name": flaky[0], "author": "verify",
                                       "reason": "intermittent — see history"})
    expect("write_quarantine_test: quarantines with failure rows moved",
           q.get("already") is False and q.get("failures_quarantined", 0) >= 1,
           f"moved={q.get('failures_quarantined')}")
    q2 = call("write_quarantine_test", {"test_name": flaky[0], "author": "verify"})
    expect("write_quarantine_test is idempotent", q2.get("already") is True, "")

    bad = call("write_set_regression_verdict",
               {"run_id": run6["id"], "verdict": "maybe", "author": "verify"})
    expect("write_set_regression_verdict rejects invalid verdict (422)",
           bad.get("status_code") == 422, f"status={bad.get('status_code')}")
    v = call("write_set_regression_verdict",
             {"run_id": run6["id"], "verdict": "regression", "author": "verify",
              "note": "1 new signature in overnight run"})
    expect("write_set_regression_verdict records verdict + note",
           v.get("regression_verdict") == "regression", f"verdict={v.get('regression_verdict')}")

    n = call("write_add_triage_note",
             {"target_type": "failure", "target_id": str(f6["failures"][0]["id"]),
              "author": "verify", "text": "First failure of the overnight run."})
    expect("write_add_triage_note attaches to a failure", "note" in n,
           f"note_id={n.get('note', {}).get('id')}")
    bad_note = call("write_add_triage_note",
                    {"target_type": "failure", "target_id": "99999",
                     "author": "verify", "text": "ghost"})
    expect("write_add_triage_note 404s on unknown failure",
           bad_note.get("status_code") == 404, f"status={bad_note.get('status_code')}")


# ---------------------------------------------------------------------------
# Phase 2 — run the jobs pack end-to-end
# ---------------------------------------------------------------------------

def worker_cluster(run_id: int) -> None:
    call("read_list_failures", {"run_id": run_id})
    out = call("write_cluster_failures", {"run_id": run_id, "author": "worker"})
    for c in out["clusters"]:
        call("write_add_triage_note", {
            "target_type": "cluster", "target_id": str(c["id"]), "author": "worker",
            "text": f"Cluster of {c['count']} failure(s) sharing signature: {c['signature']}"})


def worker_quarantine() -> None:
    for test_name in sorted(CHECKS.expected_flaky_tests(call)):
        call("write_quarantine_test", {
            "test_name": test_name, "author": "worker",
            "reason": "Flaky per recorded history: >=3 failures with a pass "
                      "after the first failure."})
        call("write_add_triage_note", {
            "target_type": "test", "target_id": test_name, "author": "worker",
            "text": "Quarantined as flaky; removed from the regression signal."})


def worker_verdict(run_id: int) -> None:
    failures = call("read_list_failures", {"run_id": run_id})["failures"]
    new_count = sum(1 for f in failures if f["is_new_signature"])
    verdict = CHECKS.expected_verdict(new_count)
    call("write_set_regression_verdict", {
        "run_id": run_id, "verdict": verdict, "author": "worker",
        "note": f"{new_count} failure(s) with a brand-new signature in this run."})


def phase2() -> None:
    print("\n== Phase 2: jobs pack end-to-end (direct mode) ==")
    admin_reset()
    run_id = latest_run_id()
    templates = {t["key"]: t for t in JOBS["templates"]}

    t = templates["cluster_failures"]
    worker_cluster(run_id)
    findings = CHECKS.check_cluster_failures(call, t["acceptance_criteria"][0], run_id)
    expect(f"JOB cluster_failures (₡{t['budget_credits']}): check passes",
           all(f["passed"] for f in findings), findings[0]["detail"])

    t = templates["quarantine_flaky"]
    worker_quarantine()
    findings = CHECKS.check_quarantine_flaky(call, t["acceptance_criteria"][0])
    expect(f"JOB quarantine_flaky (₡{t['budget_credits']}): check passes",
           all(f["passed"] for f in findings), findings[0]["detail"])

    t = templates["regression_verdict"]
    worker_verdict(run_id)
    findings = CHECKS.check_regression_verdict(call, t["acceptance_criteria"][0], run_id)
    expect(f"JOB regression_verdict (₡{t['budget_credits']}): check passes",
           all(f["passed"] for f in findings), findings[0]["detail"])

    # Negative control: tamper — quarantine a regression test; the exact-set
    # check must now FAIL, proving the check is not a rubber stamp.
    call("write_quarantine_test", {
        "test_name": "tests/checkout/test_cart.py::test_cart_total_recalc",
        "author": "verify", "reason": "negative control — must break the check"})
    findings = CHECKS.check_quarantine_flaky(call, t["acceptance_criteria"][0])
    expect("NEGATIVE CONTROL: extra quarantine makes the check fail",
           not all(f["passed"] for f in findings), findings[0]["detail"])
    admin_reset()


# ---------------------------------------------------------------------------
# Phase 3 — MCP over stdio
# ---------------------------------------------------------------------------

async def _stdio_probe() -> tuple[list[str], dict, dict]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["QA_URL"] = BASE_URL
    params = StdioServerParameters(
        command=sys.executable, args=[str(HERE / "mcp_server.py")], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            r1 = await session.call_tool("read_list_runs", {})
            r2 = await session.call_tool(
                "read_list_failures", {"run_id": latest_run_id()})
            def parse(r):
                return json.loads(r.content[0].text)
            return names, parse(r1), parse(r2)


def phase3() -> None:
    print("\n== Phase 3: MCP over stdio ==")
    names, runs, failures = asyncio.run(_stdio_probe())
    expect("stdio list_tools: exactly the 7 allowlisted tools",
           sorted(names) == sorted(TOOL_SPECS), f"tools={sorted(names)}")
    expect("stdio read_list_runs works", runs.get("count") == 6,
           f"count={runs.get('count')}")
    expect("stdio read_list_failures(run 6) works", failures.get("count") == 6,
           f"count={failures.get('count')}")
    expect("no delete/admin tools exposed via MCP",
           not any("delete" in n or "reset" in n or "admin" in n for n in names), "")


def main() -> int:
    try:
        with httpx.Client(timeout=5.0, trust_env=False) as client:
            client.get(BASE_URL + "/health").raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"QADesk not reachable at {BASE_URL}: {exc}")
        print("Start it first:  uvicorn app:app --port 8103")
        return 2
    phase1()
    phase2()
    phase3()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n== SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} assertions passed ==")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
