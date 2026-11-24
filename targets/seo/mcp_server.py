"""Generated-style MCP server for SEODash — THE FLOOR's SEO workplace.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`).
Like a Synapse Auto build, it exposes ONLY the allowlisted endpoints of
the target app (see README.md) as MCP tools — no delete/admin routes
exist here, because endpoint exposure is a safety decision. Each tool is
a thin passthrough: it performs one HTTP call to the running SEODash
API and returns its JSON. Tool names carry a read_/write_ prefix and
every description states its effect, so the factory's confirmation gate
can classify calls by name alone.

The write surface is records only — audit reports, content briefs,
keyword targets and link PLANS. Nothing here publishes content or
mutates a live website.

Base URL: env SEO_URL (default http://localhost:8109).
The SEODash app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("SEO_URL", "http://localhost:8109").rstrip("/")

mcp = MCPServer("seo")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to SEODash; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls (and a bracketed IPv6 entry in NO_PROXY makes
    httpx's env parsing raise before the client is even built)."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"SEODash unreachable at {BASE_URL}: {exc}"}
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
def read_list_pages(page_type: Optional[str] = None) -> dict:
    """READ: list the site's pages (url, title, meta description, H1,
    word count, load time, page type, traffic, inbound link count),
    optionally filtered by page_type (home | landing | guide)."""
    return _call("GET", "/pages", params=_params(page_type=page_type))


@mcp.tool()
def read_get_page_audit(page_id: int) -> dict:
    """READ: deterministic on-page audit of one page — the raw fields
    plus the issues derived from them (missing title/meta/H1, thin
    content under 300 words, slow template over 2500 ms)."""
    return _call("GET", f"/pages/{page_id}/audit")


@mcp.tool()
def read_list_keywords() -> dict:
    """READ: list tracked keywords (term, volume, difficulty, current
    rank, intent, target page, seeded competitor angles)."""
    return _call("GET", "/keywords")


@mcp.tool()
def read_get_keyword(keyword_id: int) -> dict:
    """READ: fetch one keyword with its competitor angles, target page
    and every content brief saved for it."""
    return _call("GET", f"/keywords/{keyword_id}")


@mcp.tool()
def read_list_links() -> dict:
    """READ: list the site's existing internal links (from/to page ids
    and urls, anchor text)."""
    return _call("GET", "/links")


@mcp.tool()
def read_list_audit_reports() -> dict:
    """READ: list saved audit reports with their per-page findings."""
    return _call("GET", "/audit-reports")


@mcp.tool()
def read_list_link_plans() -> dict:
    """READ: list saved internal-link plans with their planned links."""
    return _call("GET", "/link-plans")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation;
# every one writes a planning record, none publishes or edits a live page)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_save_audit_report(scope: str, findings: list, author: str = "seo") -> dict:
    """WRITE: save an audit report (scope + per-page issue lists) as a
    record. Changes SEODash state; no page is modified."""
    return _call("POST", "/audit-reports",
                 json={"scope": scope, "findings": findings, "author": author})


@mcp.tool()
def write_save_content_brief(keyword_id: int, title: str, intent: str,
                             outline: list, angles_used: Optional[list] = None,
                             target_page_id: Optional[int] = None,
                             author: str = "seo") -> dict:
    """WRITE: save a content brief for a keyword (title, intent, outline
    sections, competitor angles used, optional target page). A draft
    record — nothing is published. Changes SEODash state."""
    return _call("POST", "/briefs",
                 json={"keyword_id": keyword_id, "title": title,
                       "intent": intent, "outline": outline,
                       "angles_used": angles_used or [],
                       "target_page_id": target_page_id, "author": author})


@mcp.tool()
def write_update_keyword_target(keyword_id: int,
                                target_page_id: Optional[int] = None,
                                author: str = "seo") -> dict:
    """WRITE: point a keyword at a target page (or clear its target with
    null). A planning record only. Changes SEODash state."""
    return _call("POST", f"/keywords/{keyword_id}/target",
                 json={"target_page_id": target_page_id, "author": author})


@mcp.tool()
def write_save_link_plan(links: list, author: str = "seo") -> dict:
    """WRITE: save an internal-link fix plan (planned links between
    existing pages). The plan is a record — the site's actual link
    graph does not change. Changes SEODash state."""
    return _call("POST", "/link-plans",
                 json={"links": links, "author": author})


if __name__ == "__main__":
    mcp.run(transport="stdio")
