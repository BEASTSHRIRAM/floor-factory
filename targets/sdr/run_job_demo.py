"""Run one SDR jobs-pack job end-to-end in DIRECT mode.

Mirrors orchestrator/tools.py's DirectToolClient contract: the same
allowlisted tool mapping the MCP server exposes, executed over plain
httpx (FLOOR_MCP_MODE=direct semantics), with writes passing the
confirmation gate first (policy auto-approve, confirmed_by='policy' —
the same default the TicketDesk engine runs headless with).

Job executed: `research_score_new_leads` (jobs pack #1) —
for every lead still in stage `new`: research_account over stored CRM
signals, compute the ICP score with rubric.compute_score, record it via
score_lead, then run the Reviewer's deterministic checks
(checks.score_new_batch). Exit 0 only if every check passes.

Usage:  python3 run_job_demo.py            (workplace must be running)
Env:    SDR_URL (default http://localhost:8105)
"""
from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks  # noqa: E402
from rubric import compute_score  # noqa: E402

BASE_URL = os.environ.get("SDR_URL", "http://localhost:8105").rstrip("/")

# Direct-mode tool mapping — tool-for-tool mirror of mcp_server.py
# (same names, same HTTP method/path, same read/write effect).
TOOL_SPECS = {
    "list_accounts":    {"method": "GET",  "path": "/accounts", "effect": "read"},
    "get_account":      {"method": "GET",  "path": "/accounts/{account_id}", "effect": "read"},
    "list_leads":       {"method": "GET",  "path": "/leads", "effect": "read"},
    "research_account": {"method": "GET",  "path": "/accounts/{account_id}/research", "effect": "read"},
    "score_lead":       {"method": "POST", "path": "/leads/{lead_id}/score", "effect": "write"},
    "draft_outreach":   {"method": "POST", "path": "/leads/{lead_id}/draft", "effect": "write"},
    "qualify_lead":     {"method": "POST", "path": "/leads/{lead_id}/qualify", "effect": "write"},
    "add_crm_note":     {"method": "POST", "path": "/notes", "effect": "write"},
}
_PATH_PARAMS = ("account_id", "lead_id")


def call_tool(tool_name: str, args: dict | None = None) -> dict:
    """Direct-mode tool call. Writes are confirmation-gated first
    (policy auto-approve for the headless demo, logged as such)."""
    args = dict(args or {})
    spec = TOOL_SPECS[tool_name]
    if spec["effect"] == "write":
        print(f"  [gate] WRITE {tool_name} {args} -> confirmed_by=policy (auto-approve)")
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
    with httpx.Client(base_url=BASE_URL, timeout=15.0, trust_env=False) as client:
        if spec["method"] == "GET":
            resp = client.get(path, params=params)
        else:
            resp = client.post(path, json=body)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    transcript = []
    new_leads = call_tool("list_leads", {"stage": "new"})["leads"]
    print(f"Job 'research_score_new_leads': {len(new_leads)} new lead(s) to research + score")
    for lead in new_leads:
        research = call_tool("research_account", {"account_id": lead["account_id"]})
        account = research["account"]
        score, reasons = compute_score(account)
        result = call_tool("score_lead", {
            "lead_id": lead["id"], "score": score, "reasons": reasons})
        line = (f"lead {lead['id']} ({lead['contact_name']} @ {account['name']}): "
                f"signals={[s['signal'] for s in research['signals']]} "
                f"-> score {score} [{result['stage']}]")
        print(" ", line)
        transcript.append(line)

    findings, passed = checks.run(["score_new_batch"])
    print("\nReviewer deterministic checks (score_new_batch):")
    print(json.dumps({"passed": passed, "findings": findings}, indent=2))
    print(f"\nJOB RESULT: {'PASS — all deterministic checks green' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
