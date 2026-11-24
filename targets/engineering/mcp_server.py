"""Generated-style MCP server for Engineering — THE FLOOR department
workplace "repo-lite".

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`;
see department.json for the onboarding status). Like a Synapse Auto
build, it exposes ONLY the allowlisted endpoints of the department app
as MCP tools — no merge route and no delete routes exist here, because
endpoint exposure is a safety decision: agents prepare PRs, humans merge
them. Each tool is a thin passthrough: it performs one HTTP call to the
running Engineering API and returns its JSON. Tool names carry a
read_/write_ prefix and every description states its effect, so the
factory's confirmation gate can classify calls by name alone.

Base URL: env ENGINEERING_URL (default http://localhost:8106).
The Engineering app must be running for tool calls to succeed.

Run (stdio transport, as an MCP client would spawn it):
    python3 mcp_server.py

Requires: mcp (>=2, uses mcp.server.mcpserver.MCPServer — the renamed
FastMCP), httpx.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx
from mcp.server.mcpserver import MCPServer

BASE_URL = os.environ.get("ENGINEERING_URL", "http://localhost:8106").rstrip("/")

mcp = MCPServer("engineering")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to Engineering; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls (and a bracketed IPv6 entry in NO_PROXY makes
    httpx's env parsing raise before the client is even built)."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"Engineering unreachable at {BASE_URL}: {exc}"}
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        return {"error": detail, "status_code": resp.status_code}
    return resp.json()


def _params(**kw) -> dict:
    return {k: v for k, v in kw.items() if v is not None}


# ---------------------------------------------------------------------------
# READ tools (no side effects — the factory runs these without confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def read_list_issues(status: Optional[str] = None, priority: Optional[str] = None,
                     label: Optional[str] = None, unlabelled: Optional[bool] = None,
                     assignee: Optional[str] = None) -> dict:
    """READ: list engineering issues, optionally filtered by status /
    priority / label / assignee. unlabelled=true lists the triage queue
    (issues with no labels); assignee='none' lists unclaimed issues."""
    return _call("GET", "/issues",
                 params=_params(status=status, priority=priority, label=label,
                                unlabelled=unlabelled, assignee=assignee))


@mcp.tool()
def read_get_issue(issue_id: int) -> dict:
    """READ: fetch one issue by id, including its engineering notes and
    linked pull-request records."""
    return _call("GET", f"/issues/{issue_id}")


@mcp.tool()
def read_get_pr(pr_id: int) -> dict:
    """READ: fetch one pull-request record by id, including its recorded
    CI result."""
    return _call("GET", f"/prs/{pr_id}")


@mcp.tool()
def read_get_ci_status(pr_id: int) -> dict:
    """READ: the recorded CI result for a pull request. CI is computed
    deterministically by the service when the PR is opened and never
    changes afterwards."""
    return _call("GET", f"/prs/{pr_id}/ci")


@mcp.tool()
def read_stats_summary() -> dict:
    """READ: aggregate Engineering counts (issues by status, unlabelled,
    unprioritised, unclaimed, PRs by status, CI pass/fail)."""
    return _call("GET", "/stats/summary")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# There is deliberately NO merge tool and NO delete tool: a PR record can
# only be opened, sent back, or approved. Merging is a human gate.
# ---------------------------------------------------------------------------

@mcp.tool()
def write_claim_issue(issue_id: int, assignee: str) -> dict:
    """WRITE: claim an issue for an agent (fails if another agent holds
    it). Changes Engineering state."""
    return _call("POST", f"/issues/{issue_id}/claim", json={"assignee": assignee})


@mcp.tool()
def write_triage_issue(issue_id: int, labels: list[str], priority: str) -> dict:
    """WRITE: assign labels and a priority (P1-P4) to an issue — the
    triage job's write. Changes Engineering state."""
    return _call("POST", f"/issues/{issue_id}/triage",
                 json={"labels": labels, "priority": priority})


@mcp.tool()
def write_open_pr(issue_id: int, author: str, title: str, change_summary: str,
                  files_touched: list[str]) -> dict:
    """WRITE: open a pull-request record linked to an issue the author has
    claimed, with a change summary and the files touched. Opening a PR
    runs the service's deterministic CI immediately and records the
    result. Changes Engineering state."""
    return _call("POST", "/prs", json={
        "issue_id": issue_id, "author": author, "title": title,
        "change_summary": change_summary, "files_touched": files_touched,
    })


@mcp.tool()
def write_request_changes(pr_id: int, reviewer: str, note: str = "") -> dict:
    """WRITE (reviewer-side): record a changes-requested review on an open
    PR, with a note for the author. Changes Engineering state."""
    return _call("POST", f"/prs/{pr_id}/request-changes",
                 json={"reviewer": reviewer, "note": note})


@mcp.tool()
def write_approve_pr(pr_id: int, reviewer: str, note: str = "") -> dict:
    """WRITE (reviewer-side): record an approval on an open PR whose CI is
    green. Approval is NOT a merge — merging stays with a human, outside
    this tool surface. Changes Engineering state."""
    return _call("POST", f"/prs/{pr_id}/approve",
                 json={"reviewer": reviewer, "note": note})


@mcp.tool()
def write_add_eng_note(issue_id: int, author: str, text: str,
                       pr_id: Optional[int] = None) -> dict:
    """WRITE: add an engineering note to an issue (optionally tied to a
    PR). Changes Engineering state."""
    return _call("POST", f"/issues/{issue_id}/note",
                 json={"author": author, "text": text, "pr_id": pr_id})


if __name__ == "__main__":
    mcp.run(transport="stdio")
