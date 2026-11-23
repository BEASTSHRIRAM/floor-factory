"""Generated-style MCP server for TicketDesk — THE FLOOR target system #1.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`).
Like a Synapse Auto build, it exposes ONLY the allowlisted endpoints of
the target app (ARCHITECTURE §6.1) as MCP tools — no delete/admin routes
exist here, because endpoint exposure is a safety decision. Each tool is
a thin passthrough: it performs one HTTP call to the running TicketDesk
API and returns its JSON. Tool names carry a read_/write_ prefix and
every description states its effect, so the factory's confirmation gate
can classify calls by name alone.

Base URL: env TICKETDESK_URL (default http://localhost:8101).
The TicketDesk app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("TICKETDESK_URL", "http://localhost:8101").rstrip("/")

mcp = MCPServer("ticketdesk")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to TicketDesk; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls (and a bracketed IPv6 entry in NO_PROXY makes
    httpx's env parsing raise before the client is even built)."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"TicketDesk unreachable at {BASE_URL}: {exc}"}
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
def read_list_tickets(status: Optional[str] = None, assignee: Optional[str] = None,
                      priority: Optional[str] = None,
                      category: Optional[str] = None) -> dict:
    """READ: list tickets, optionally filtered by status / assignee /
    priority / category. assignee='none' lists unassigned tickets."""
    return _call("GET", "/tickets",
                 params=_params(status=status, assignee=assignee,
                                priority=priority, category=category))


@mcp.tool()
def read_get_ticket(ticket_id: int) -> dict:
    """READ: fetch one ticket by id, including its comments."""
    return _call("GET", f"/tickets/{ticket_id}")


@mcp.tool()
def read_find_duplicate_tickets() -> dict:
    """READ: group live tickets that look like duplicates of each other."""
    return _call("GET", "/tickets/duplicates")


@mcp.tool()
def read_sla_breaches() -> dict:
    """READ: list tickets past their SLA deadline and not resolved/closed."""
    return _call("GET", "/sla/breaches")


@mcp.tool()
def read_stats_summary() -> dict:
    """READ: aggregate TicketDesk counts (by status, unassigned, SLA
    breaches, duplicate groups, categories)."""
    return _call("GET", "/stats/summary")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_create_ticket(subject: str, body: str = "", customer: str = "",
                        category: str = "general", priority: str = "P3",
                        assignee: Optional[str] = None) -> dict:
    """WRITE: create a new ticket. Changes TicketDesk state."""
    return _call("POST", "/tickets", json={
        "subject": subject, "body": body, "customer": customer,
        "category": category, "priority": priority, "assignee": assignee,
    })


@mcp.tool()
def write_assign_ticket(ticket_id: int, assignee: Optional[str] = None) -> dict:
    """WRITE: assign a ticket to a support agent (null unassigns it).
    Changes TicketDesk state."""
    return _call("POST", f"/tickets/{ticket_id}/assign",
                 json={"assignee": assignee})


@mcp.tool()
def write_set_ticket_priority(ticket_id: int, priority: str) -> dict:
    """WRITE: change a ticket's priority (P1-P4). Changes TicketDesk state."""
    return _call("POST", f"/tickets/{ticket_id}/priority",
                 json={"priority": priority})


@mcp.tool()
def write_add_ticket_comment(ticket_id: int, text: str, author: str = "support",
                             kind: str = "comment") -> dict:
    """WRITE: add a comment to a ticket (kind: comment | escalation |
    resolution). Changes TicketDesk state."""
    return _call("POST", f"/tickets/{ticket_id}/comment",
                 json={"author": author, "text": text, "kind": kind})


@mcp.tool()
def write_set_ticket_status(ticket_id: int, status: str) -> dict:
    """WRITE: change a ticket's status (new|open|in_progress|resolved|
    closed). Changes TicketDesk state."""
    return _call("POST", f"/tickets/{ticket_id}/status", json={"status": status})


@mcp.tool()
def write_merge_tickets(source_id: int, target_id: int) -> dict:
    """WRITE: merge a duplicate ticket into a canonical one (the source is
    closed). Changes TicketDesk state."""
    return _call("POST", "/tickets/merge",
                 json={"source_id": source_id, "target_id": target_id})


if __name__ == "__main__":
    mcp.run(transport="stdio")
