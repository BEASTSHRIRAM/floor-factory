"""Generated-style MCP server for StockRoom — THE FLOOR target system #2.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`).
Like a Synapse Auto build, it exposes ONLY the allowlisted endpoints of
the target app (ARCHITECTURE §6.2) as MCP tools — no delete/admin routes
exist here, because endpoint exposure is a safety decision. Each tool is
a thin passthrough: it performs one HTTP call to the running StockRoom
API and returns its JSON. Tool names carry a read_/write_ prefix and
every description states its effect, so the factory's confirmation gate
can classify calls by name alone.

`read_low_stock` is the tool the demo's finale adds live via
`synapse build --discover` (ARCHITECTURE §4.5); it is included here so
the finale is rehearsable end-to-end.

Base URL: env STOCKROOM_URL (default http://localhost:8102).
The StockRoom app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("STOCKROOM_URL", "http://localhost:8102").rstrip("/")

mcp = MCPServer("stockroom")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to StockRoom; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls (and a bracketed IPv6 entry in NO_PROXY makes
    httpx's env parsing raise before the client is even built)."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"StockRoom unreachable at {BASE_URL}: {exc}"}
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
def read_list_items(category: Optional[str] = None,
                    location: Optional[str] = None) -> dict:
    """READ: list inventory items, optionally filtered by category or
    storage location."""
    return _call("GET", "/items",
                 params=_params(category=category, location=location))


@mcp.tool()
def read_get_item(item_id: int) -> dict:
    """READ: fetch one inventory item by id."""
    return _call("GET", f"/items/{item_id}")


@mcp.tool()
def read_low_stock(threshold: int = 10) -> dict:
    """READ: list items whose quantity is below the threshold — the
    reorder list. (The tool added live by `synapse build --discover`
    in the demo finale.)"""
    return _call("GET", "/items/low-stock", params={"threshold": threshold})


@mcp.tool()
def read_pending_orders() -> dict:
    """READ: list purchase orders still pending, with their item details."""
    return _call("GET", "/orders/pending")


@mcp.tool()
def read_stats_summary() -> dict:
    """READ: aggregate StockRoom counts (total items/units, low-stock
    count, out-of-stock, pending orders, categories)."""
    return _call("GET", "/stats/summary")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_adjust_item(item_id: int, delta: int, reason: str = "") -> dict:
    """WRITE: adjust an item's stock quantity by delta (+ in, - out;
    never below zero). Changes StockRoom state."""
    return _call("POST", f"/items/{item_id}/adjust",
                 json={"delta": delta, "reason": reason})


if __name__ == "__main__":
    mcp.run(transport="stdio")
