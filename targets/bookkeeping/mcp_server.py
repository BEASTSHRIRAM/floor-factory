"""Generated-style MCP server for Bookkeeping — THE FLOOR's Bookkeeping
department workplace.

This file stands in for the output of `synapse build --local --auto`
(exactly as targets/ticketdesk/mcp_server.py does for TicketDesk — the
synapse CLI is not installed on this VM, so the real generated file,
which would be named `synapse_auto_server.py`, is pending; see the
department report). Like a Synapse Auto build, it exposes ONLY the
allowlisted endpoints of the target app as MCP tools — no delete, admin,
payment or money-movement routes exist here, because endpoint exposure
is a safety decision. Each tool is a thin passthrough: it performs one
HTTP call to the running Bookkeeping API and returns its JSON. Tool
names carry a read_/write_ prefix and every description states its
effect, so the factory's confirmation gate can classify calls by name
alone. Writes in this department organise and draft only — no tool here
can move money.

Base URL: env BOOKKEEPING_URL (default http://localhost:8104).
The Bookkeeping app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("BOOKKEEPING_URL", "http://localhost:8104").rstrip("/")

mcp = MCPServer("bookkeeping")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to Bookkeeping; errors come back as data, not
    crashes, so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"Bookkeeping unreachable at {BASE_URL}: {exc}"}
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
def read_list_transactions(account_id: Optional[int] = None,
                           category: Optional[str] = None,
                           uncategorised: Optional[bool] = None) -> dict:
    """READ: list transactions, optionally filtered by account_id /
    category. uncategorised=true lists only transactions with no
    category yet."""
    return _call("GET", "/transactions",
                 params=_params(account_id=account_id, category=category,
                                uncategorised=uncategorised))


@mcp.tool()
def read_list_uncategorised() -> dict:
    """READ: the categorisation queue — transactions with no category,
    oldest first, each with its age in days."""
    return _call("GET", "/transactions/uncategorised")


@mcp.tool()
def read_find_duplicates() -> dict:
    """READ: group unflagged transactions that look like exact duplicates
    (same account, date, payee, amount). Empty result = all duplicates
    already flagged."""
    return _call("GET", "/transactions/duplicates")


@mcp.tool()
def read_reconcile_account(account_id: int) -> dict:
    """READ: reconcile one account — recorded balance (the books) vs
    statement balance, with the delta. Explains differences; never
    moves money."""
    return _call("GET", f"/accounts/{account_id}/reconcile")


@mcp.tool()
def read_list_receivables(status: Optional[str] = None) -> dict:
    """READ: list invoices/receivables with days overdue, chase level
    due, and reminders already recorded. status='open' filters to open
    invoices."""
    return _call("GET", "/receivables", params=_params(status=status))


@mcp.tool()
def read_list_accounts() -> dict:
    """READ: all accounts with their recorded balances."""
    return _call("GET", "/accounts")


@mcp.tool()
def read_chart_of_accounts() -> dict:
    """READ: the chart of accounts — the only valid category names."""
    return _call("GET", "/chart")


@mcp.tool()
def read_list_notes() -> dict:
    """READ: finance notes recorded so far (incl. reconciliation
    write-ups)."""
    return _call("GET", "/notes")


@mcp.tool()
def read_stats_summary() -> dict:
    """READ: aggregate Bookkeeping counts (uncategorised, duplicates,
    overdue receivables, balances)."""
    return _call("GET", "/stats/summary")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation;
# every write here organises or drafts — none of them moves money)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_categorise_transaction(txn_id: int, category: str) -> dict:
    """WRITE: set a transaction's category (must be a chart-of-accounts
    name). Changes Bookkeeping state."""
    return _call("POST", f"/transactions/{txn_id}/categorise",
                 json={"category": category})


@mcp.tool()
def write_flag_duplicate(txn_id: int, duplicate_of: int) -> dict:
    """WRITE: flag a transaction as a duplicate of the canonical one.
    Marks the row only — nothing is deleted. Changes Bookkeeping state."""
    return _call("POST", f"/transactions/{txn_id}/flag-duplicate",
                 json={"duplicate_of": duplicate_of})


@mcp.tool()
def write_send_reminder(invoice_id: int, note: str = "") -> dict:
    """WRITE: record a payment-chase reminder for an overdue invoice.
    Records a draft/event in the books only — sends no real email and
    moves no money. The chase level is set by how overdue the invoice
    is (+3 gentle, +15 firm, +30 final). Changes Bookkeeping state."""
    return _call("POST", f"/receivables/{invoice_id}/reminder",
                 json={"note": note})


@mcp.tool()
def write_add_finance_note(text: str, account_id: Optional[int] = None,
                           kind: str = "note") -> dict:
    """WRITE: record a finance note (kind: note | reconciliation |
    audit), optionally tied to an account. Changes Bookkeeping state."""
    return _call("POST", "/notes",
                 json={"text": text, "account_id": account_id, "kind": kind})


if __name__ == "__main__":
    mcp.run(transport="stdio")
