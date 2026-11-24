"""Generated-style MCP server for HRDesk — THE FLOOR, HR department.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`),
exactly as targets/ticketdesk/mcp_server.py does for TicketDesk. Like a
Synapse Auto build, it exposes ONLY the allowlisted endpoints of the
target app as MCP tools — no hire/reject route and no delete route exist
here, because endpoint exposure is a safety decision and the hiring
decision stays human (platform rule). Each tool is a thin passthrough:
one HTTP call to the running HRDesk API, JSON back. Tool names carry a
read_/write_ prefix and every description states its effect, so the
factory's confirmation gate can classify calls by name alone.

Base URL: env HRDESK_URL (default http://localhost:8107).
The HRDesk app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("HRDESK_URL", "http://localhost:8107").rstrip("/")

mcp = MCPServer("hrdesk")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to HRDesk; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"HRDesk unreachable at {BASE_URL}: {exc}"}
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
def read_list_candidates(stage: Optional[str] = None,
                         role: Optional[str] = None) -> dict:
    """READ: list candidates, optionally filtered by stage
    (applied|screening|interview|onboarding) / role key."""
    return _call("GET", "/candidates",
                 params=_params(stage=stage, role=role))


@mcp.tool()
def read_get_candidate(candidate_id: int) -> dict:
    """READ: fetch one candidate with screening record, interviews,
    HR notes and onboarding steps."""
    return _call("GET", f"/candidates/{candidate_id}")


@mcp.tool()
def read_list_onboarding() -> dict:
    """READ: list this week's joiners with their onboarding checklists
    and each joiner's required-documents list."""
    return _call("GET", "/onboarding")


@mcp.tool()
def read_stats_summary() -> dict:
    """READ: aggregate HRDesk counts (by stage, unscreened, joiners,
    incomplete checklists)."""
    return _call("GET", "/stats/summary")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_screen_candidate(candidate_id: int, notes: str = "",
                           screener: str = "hr-agent") -> dict:
    """WRITE: record a screening for a candidate. The score and verdict
    are computed by HRDesk from the role's stated rubric (required skills
    present/absent) — this tool supplies notes only. The verdict is a
    recommendation, NOT a hire/reject decision; hiring stays human.
    Changes HRDesk state."""
    return _call("POST", f"/candidates/{candidate_id}/screen",
                 json={"screener": screener, "notes": notes})


@mcp.tool()
def write_schedule_interview(candidate_id: int, scheduled_at: str,
                             interviewer: str = "", kind: str = "panel") -> dict:
    """WRITE: schedule an interview (ISO-8601 scheduled_at; kind:
    phone|panel|final). HRDesk refuses unless the candidate's screening
    passed the role's rubric threshold. Changes HRDesk state."""
    return _call("POST", f"/candidates/{candidate_id}/interviews",
                 json={"scheduled_at": scheduled_at,
                       "interviewer": interviewer, "kind": kind})


@mcp.tool()
def write_complete_onboarding_step(candidate_id: int, step_key: str) -> dict:
    """WRITE: mark one onboarding checklist step complete for a joiner.
    Changes HRDesk state."""
    return _call("POST", f"/onboarding/{candidate_id}/steps/{step_key}/complete")


@mcp.tool()
def write_add_hr_note(candidate_id: int, text: str, author: str = "hr") -> dict:
    """WRITE: add a free-text HR note to a candidate's record.
    Changes HRDesk state."""
    return _call("POST", f"/candidates/{candidate_id}/notes",
                 json={"author": author, "text": text})


if __name__ == "__main__":
    mcp.run(transport="stdio")
