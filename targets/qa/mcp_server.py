"""Generated-style MCP server for QADesk — THE FLOOR's QA triage workplace.

This file stands in for the output of `synapse build --local --auto`
(the real Synapse-generated file would be named `synapse_auto_server.py`).
Like a Synapse Auto build, it exposes ONLY the allowlisted endpoints of
the target app (see README.md) as MCP tools — no delete/admin routes
exist here, because endpoint exposure is a safety decision. Each tool is
a thin passthrough: it performs one HTTP call to the running QADesk
API and returns its JSON. Tool names carry a read_/write_ prefix and
every description states its effect, so the factory's confirmation gate
can classify calls by name alone.

Base URL: env QA_URL (default http://localhost:8103).
The QADesk app must be running for tool calls to succeed.

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

BASE_URL = os.environ.get("QA_URL", "http://localhost:8103").rstrip("/")

mcp = MCPServer("qa")


def _call(method: str, path: str, **kwargs) -> dict:
    """One HTTP call to QADesk; errors come back as data, not crashes,
    so a worker agent can observe a failure and adapt.
    trust_env=False: the target API is local — proxy env vars must never
    reroute these calls (and a bracketed IPv6 entry in NO_PROXY makes
    httpx's env parsing raise before the client is even built)."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
            resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        return {"error": f"QADesk unreachable at {BASE_URL}: {exc}"}
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
def read_list_runs(status: Optional[str] = None,
                   branch: Optional[str] = None) -> dict:
    """READ: list CI runs, newest first, each with failure_count,
    new_failure_count and any recorded regression verdict."""
    return _call("GET", "/runs", params=_params(status=status, branch=branch))


@mcp.tool()
def read_list_failures(run_id: Optional[int] = None, suite: Optional[str] = None,
                       status: Optional[str] = None,
                       signature: Optional[str] = None,
                       test_name: Optional[str] = None,
                       cluster_id: Optional[int] = None) -> dict:
    """READ: list failures, optionally filtered by run / suite / status /
    signature / test name / cluster. Each failure shows its cluster
    assignment and whether its signature is new in its run."""
    return _call("GET", "/failures",
                 params=_params(run_id=run_id, suite=suite, status=status,
                                signature=signature, test_name=test_name,
                                cluster_id=cluster_id))


@mcp.tool()
def read_get_failure_detail(failure_id: int) -> dict:
    """READ: fetch one failure with its cluster, the full pass/fail
    history of its test across all runs, signature stats (first-seen
    run, totals) and the test's quarantine state."""
    return _call("GET", f"/failures/{failure_id}")


# ---------------------------------------------------------------------------
# WRITE tools (side effects — the factory gates these behind confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def write_cluster_failures(run_id: Optional[int] = None,
                           author: str = "qa") -> dict:
    """WRITE: group unclustered failures by error signature — creates one
    cluster per signature and assigns every matching failure to it
    (optionally only within one run). Changes QADesk state."""
    return _call("POST", "/failures/cluster",
                 json={"run_id": run_id, "author": author})


@mcp.tool()
def write_quarantine_test(test_name: str, author: str = "qa",
                          reason: str = "") -> dict:
    """WRITE: mark a test as flaky and quarantine it; its open failures
    move to status 'quarantined'. Changes QADesk state."""
    return _call("POST", "/tests/quarantine",
                 json={"test_name": test_name, "author": author, "reason": reason})


@mcp.tool()
def write_set_regression_verdict(run_id: int, verdict: str, author: str = "qa",
                                 note: str = "") -> dict:
    """WRITE: record a run's regression verdict ('regression' or
    'no_regression'); a non-empty note is stored as a triage note on the
    run. Changes QADesk state."""
    return _call("POST", f"/runs/{run_id}/regression-verdict",
                 json={"verdict": verdict, "author": author, "note": note})


@mcp.tool()
def write_add_triage_note(target_type: str, target_id: str, text: str,
                          author: str = "qa") -> dict:
    """WRITE: add a triage note to a failure, cluster, run, or test
    (target_type: failure | cluster | run | test). Changes QADesk state."""
    return _call("POST", "/triage-notes",
                 json={"target_type": target_type, "target_id": target_id,
                       "author": author, "text": text})


if __name__ == "__main__":
    mcp.run(transport="stdio")
