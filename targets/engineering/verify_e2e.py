#!/usr/bin/env python3
"""End-to-end verification for the Engineering department workplace.

Mirrors how THE FLOOR exercises TicketDesk:
  * a DirectClient implementing the FLOOR_MCP_MODE=direct contract — the
    identical tool mapping (name -> method/path/effect) executed over
    plain httpx, exactly like mcp_manager's / orchestrator.tools' direct
    fallback;
  * one real MCP-over-stdio pass (spawn mcp_server.py, list tools, one
    call) — the primary transport the factory uses;
  * the `work_issue` job template run end-to-end in direct mode and
    graded by checks.check_work_issue (deterministic Reviewer checks);
  * the `triage_unlabelled` job run end-to-end and graded by
    checks.check_triage;
  * the reviewer gates: unclaimed PR open rejected, double-claim
    rejected, red-CI PR cannot be approved, author cannot approve their
    own PR, green PR approves (and is still NOT merged — no such tool).

Requires the Engineering app running:  uvicorn app:app --port 8106
Run:  python3 verify_e2e.py     (resets the service first via /admin/reset)
Exit code 0 = every assertion passed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

import checks  # noqa: E402

BASE_URL = os.environ.get("ENGINEERING_URL", "http://localhost:8106").rstrip("/")

TOOL_SPECS = {
    "read_list_issues": {"method": "GET", "path": "/issues", "effect": "read"},
    "read_get_issue": {"method": "GET", "path": "/issues/{issue_id}", "effect": "read"},
    "read_get_pr": {"method": "GET", "path": "/prs/{pr_id}", "effect": "read"},
    "read_get_ci_status": {"method": "GET", "path": "/prs/{pr_id}/ci", "effect": "read"},
    "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
    "write_claim_issue": {"method": "POST", "path": "/issues/{issue_id}/claim", "effect": "write"},
    "write_triage_issue": {"method": "POST", "path": "/issues/{issue_id}/triage", "effect": "write"},
    "write_open_pr": {"method": "POST", "path": "/prs", "effect": "write"},
    "write_request_changes": {"method": "POST", "path": "/prs/{pr_id}/request-changes", "effect": "write"},
    "write_approve_pr": {"method": "POST", "path": "/prs/{pr_id}/approve", "effect": "write"},
    "write_add_eng_note": {"method": "POST", "path": "/issues/{issue_id}/note", "effect": "write"},
}

_PATH_PARAMS = ("issue_id", "pr_id")
FAILURES = []


class DirectClient:
    """FLOOR_MCP_MODE=direct equivalent for this department (same contract
    as mcp_manager.ToolClient's direct fallback)."""

    def call_tool(self, tool_name: str, args: dict | None = None) -> dict:
        args = dict(args or {})
        spec = TOOL_SPECS[tool_name]
        path = spec["path"]
        params, body = {}, {}
        for key, value in args.items():
            if key in _PATH_PARAMS and "{" + key + "}" in path:
                path = path.replace("{" + key + "}", str(value))
            elif spec["method"] == "GET":
                if value is not None:
                    params[key] = value
            else:
                body[key] = value
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as c:
            resp = (c.get(path, params=params) if spec["method"] == "GET"
                    else c.post(path, json=body))
        try:
            data = resp.json()
        except ValueError:
            data = {"error": resp.text}
        if resp.status_code >= 400:
            return {"error": data, "status_code": resp.status_code}
        return data


def expect(label: str, cond: bool, detail: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILURES.append(label)


def show(label: str, obj) -> None:
    print(f"  {label}: {json.dumps(obj, default=str)[:400]}")


def main() -> int:
    client = DirectClient()
    call = client.call_tool

    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as c:
        r = c.post("/admin/reset")
    expect("reset to seeded state", r.status_code == 200, r.text[:120])

    # ---- read tools -------------------------------------------------------
    stats = call("read_stats_summary")
    show("stats after reset", stats)
    expect("12 seeded issues", stats.get("total_issues") == 12)
    expect("4 unlabelled issues seeded", stats.get("unlabelled") == 4)
    expect("seeded PR states open/changes_requested/approved",
           stats.get("prs_by_status") == {"open": 1, "changes_requested": 1, "approved": 1},
           str(stats.get("prs_by_status")))
    expect("seeded CI rows: 2 pass / 1 fail",
           stats.get("ci_results") == {"pass": 2, "fail": 1}, str(stats.get("ci_results")))

    unlabelled = call("read_list_issues", {"unlabelled": True})
    expect("read_list_issues(unlabelled=true) -> 4", unlabelled.get("count") == 4,
           f"ids {[i['id'] for i in unlabelled.get('issues', [])]}")
    issue1 = call("read_get_issue", {"issue_id": 1})
    expect("read_get_issue(1) carries acceptance keywords + files",
           issue1.get("acceptance_keywords") == ["session", "refresh", "token"]
           and issue1.get("files") == ["auth/session.py", "auth/tokens.py"])
    pr2_ci = call("read_get_ci_status", {"pr_id": 2})
    expect("seeded PR 2 CI is fail (summary missed 'sunset')",
           pr2_ci.get("status") == "fail", pr2_ci.get("detail", ""))
    pr1 = call("read_get_pr", {"pr_id": 1})
    expect("seeded PR 1 open with green CI",
           pr1.get("status") == "open" and pr1.get("ci", {}).get("status") == "pass")

    # ---- gates before the job ----------------------------------------------
    early = call("write_open_pr", {"issue_id": 1, "author": "maya", "title": "Too soon",
                                   "change_summary": "session refresh token fix",
                                   "files_touched": ["auth/session.py", "auth/tokens.py"]})
    expect("open_pr before claim is rejected", "error" in early, str(early)[:160])

    # ---- JOB work_issue, end-to-end in direct mode (worker: maya) ----------
    claimed = call("write_claim_issue", {"issue_id": 1, "assignee": "maya"})
    expect("write_claim_issue(1, maya)", claimed.get("assignee") == "maya"
           and claimed.get("status") == "claimed")
    stolen = call("write_claim_issue", {"issue_id": 1, "assignee": "ravi"})
    expect("second claim by another agent is rejected", "error" in stolen)

    bad_pr = call("write_open_pr", {
        "issue_id": 1, "author": "maya", "title": "Fix login thing",
        "change_summary": "Fixed the login thing.",
        "files_touched": ["auth/session.py"]})
    expect("sloppy PR opens (record created)", "id" in bad_pr, f"PR id {bad_pr.get('id')}")
    bad_ci = call("read_get_ci_status", {"pr_id": bad_pr["id"]})
    expect("sloppy PR CI is fail (deterministic rule)", bad_ci.get("status") == "fail",
           bad_ci.get("detail", ""))

    good_pr = call("write_open_pr", {
        "issue_id": 1, "author": "maya", "title": "Refresh expired sessions",
        "change_summary": "Session refresh on token expiry: when the access token "
                          "expires, the session layer now uses the refresh token to "
                          "issue a new token without forcing re-login.",
        "files_touched": ["auth/session.py", "auth/tokens.py", "tests/test_session.py"]})
    expect("proper PR opens", "id" in good_pr, f"PR id {good_pr.get('id')}")
    good_ci = call("read_get_ci_status", {"pr_id": good_pr["id"]})
    expect("proper PR CI is pass", good_ci.get("status") == "pass", good_ci.get("detail", ""))

    findings = checks.check_work_issue(call, issue_id=1, worker="maya")
    for f in findings:
        print(f"  check: {f['criterion']} -> {'PASS' if f['passed'] else 'FAIL'} ({f['detail']})")
    expect("JOB work_issue: deterministic Reviewer checks ALL PASS",
           checks.all_passed(findings))

    # ---- reviewer-side gates -------------------------------------------------
    red_approve = call("write_approve_pr", {"pr_id": bad_pr["id"], "reviewer": "iris",
                                            "note": "trying"})
    expect("approve of red-CI PR is rejected", "error" in red_approve, str(red_approve)[:160])
    self_approve = call("write_approve_pr", {"pr_id": good_pr["id"], "reviewer": "maya",
                                             "note": "self"})
    expect("author approving own PR is rejected", "error" in self_approve)
    approved = call("write_approve_pr", {"pr_id": good_pr["id"], "reviewer": "iris",
                                         "note": "CI green, acceptance addressed."})
    expect("reviewer approves green PR", approved.get("status") == "approved")
    expect("approved PR is NOT merged (no merge state exists)",
           approved.get("status") == "approved" and "merged" not in json.dumps(approved))

    rc = call("write_request_changes", {"pr_id": 1, "reviewer": "iris",
                                        "note": "Add a note on cache TTL interaction, then re-verify."})
    expect("write_request_changes on seeded PR 1", rc.get("status") == "changes_requested")

    note = call("write_add_eng_note", {"issue_id": 1, "author": "maya",
                                       "text": "PR opened and approved; merge is with a human now.",
                                       "pr_id": good_pr["id"]})
    expect("write_add_eng_note", note.get("note", {}).get("text", "").startswith("PR opened"))

    # ---- JOB triage_unlabelled, end-to-end -----------------------------------
    triage_plan = {
        6: (["bug", "mobile"], "P1"),        # crash for every viewer
        7: (["feature", "ui"], "P4"),        # dark mode request
        8: (["bug", "billing"], "P1"),       # money mismatch
        9: (["bug", "api"], "P2"),           # 500 on a core endpoint
    }
    for issue_id, (labels, priority) in triage_plan.items():
        out = call("write_triage_issue", {"issue_id": issue_id, "labels": labels,
                                          "priority": priority})
        expect(f"write_triage_issue({issue_id})", out.get("priority") == priority
               and out.get("labels") == labels)
    tfindings = checks.check_triage(call)
    for f in tfindings:
        print(f"  check: {f['criterion']} -> {'PASS' if f['passed'] else 'FAIL'} ({f['detail']})")
    expect("JOB triage_unlabelled: deterministic Reviewer check PASSES",
           checks.all_passed(tfindings))

    # ---- MCP over stdio (the factory's primary transport) ---------------------
    asyncio.run(_stdio_pass())
    return 1 if FAILURES else 0


async def _stdio_pass() -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parent / "mcp_server.py")],
        env={**os.environ, "ENGINEERING_URL": BASE_URL},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(t.name for t in tools.tools)
            show("stdio MCP tools", names)
            expect("stdio MCP lists all 11 tools", names == sorted(TOOL_SPECS),
                   f"{len(names)} tools")
            expect("no merge/delete tool on the MCP surface",
                   not any("merge" in n or "delete" in n for n in names))
            result = await session.call_tool("read_stats_summary", {})
            text = result.content[0].text if result.content else ""
            expect("stdio MCP read_stats_summary call returns live state",
                   '"total_issues": 12' in text.replace(" ", " ").replace('":', '":')
                   or "total_issues" in text, text[:160])


if __name__ == "__main__":
    code = main()
    print("\nRESULT:", "ALL CHECKS PASSED" if code == 0 else f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    sys.exit(code)
