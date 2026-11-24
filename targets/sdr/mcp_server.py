"""Generated-style MCP server for the SDR workplace — THE FLOOR's SDR dept.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`).
Like a Synapse Auto build, it exposes ONLY the allowlisted endpoints of
the workplace API as MCP tools. Each tool is a thin passthrough: one HTTP
call to the running SDR workplace API, JSON back. Every description
states its effect (READ:/WRITE:) so the factory's confirmation gate can
classify calls: reads run free, writes are confirmation-gated.

DRAFTS ONLY — there is NO send tool in this file and none can appear:
the workplace API has no send endpoint. Outreach is stored as drafts on
leads; sending is a human-gated promotion outside this tool surface.

Base URL: env SDR_URL (default http://localhost:8105).
The SDR workplace app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("SDR_URL", "http://localhost:8105").rstrip("/")

mcp = MCPServer("sdr")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to the SDR workplace; errors come back as data, not
    crashes, so a worker agent can observe a failure and adapt.
    trust_env=False: the workplace API is local — proxy env vars must
    never reroute these calls."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"SDR workplace unreachable at {BASE_URL}: {exc}"}
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
def list_accounts(industry: Optional[str] = None, min_size: Optional[int] = None,
                  max_size: Optional[int] = None) -> dict:
    """READ: list CRM accounts, optionally filtered by industry and/or
    employee-count band."""
    return _call("GET", "/accounts",
                 params=_params(industry=industry, min_size=min_size,
                                max_size=max_size))


@mcp.tool()
def get_account(account_id: int) -> dict:
    """READ: fetch one account with its leads and CRM notes."""
    return _call("GET", f"/accounts/{account_id}")


@mcp.tool()
def list_leads(stage: Optional[str] = None,
               account_id: Optional[int] = None) -> dict:
    """READ: list leads, optionally filtered by stage
    (new|researching|drafted|qualified) and/or account."""
    return _call("GET", "/leads",
                 params=_params(stage=stage, account_id=account_id))


@mcp.tool()
def research_account(account_id: int) -> dict:
    """READ: research one account over its STORED CRM signals only —
    firmographics, tech/buying signals with rubric points, and engagement
    (last touch, lead stages). No live web exists in this workplace."""
    return _call("GET", f"/accounts/{account_id}/research")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def score_lead(lead_id: int, score: int, reasons: list[str]) -> dict:
    """WRITE: record an ICP-fit score (0-100) with reasons on a lead.
    The score must follow the department's ICP rubric — the Reviewer's
    deterministic check recomputes it from account data and fails
    off-rubric scores. Changes CRM state."""
    return _call("POST", f"/leads/{lead_id}/score",
                 json={"score": score, "reasons": reasons})


@mcp.tool()
def draft_outreach(lead_id: int, subject: str, body: str) -> dict:
    """WRITE: store an outreach DRAFT on a lead. This creates a draft
    only — it does NOT send anything, and no send tool exists in this
    workplace. Sending is a human-gated promotion. Changes CRM state."""
    return _call("POST", f"/leads/{lead_id}/draft",
                 json={"subject": subject, "body": body})


@mcp.tool()
def qualify_lead(lead_id: int) -> dict:
    """WRITE: mark a lead qualified. Requires a recorded score at or
    above the rubric's qualify threshold. Changes CRM state."""
    return _call("POST", f"/leads/{lead_id}/qualify", json={})


@mcp.tool()
def add_crm_note(target_type: str, target_id: int, text: str,
                 author: str = "sdr-agent") -> dict:
    """WRITE: add a CRM note to a lead or an account
    (target_type: lead|account). Changes CRM state."""
    return _call("POST", "/notes",
                 json={"target_type": target_type, "target_id": target_id,
                       "author": author, "text": text})


if __name__ == "__main__":
    mcp.run(transport="stdio")
