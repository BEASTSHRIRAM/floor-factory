"""ToolClient — the orchestrator's one door to the target systems.

What this actually does (honest version):

* PRIMARY path — real MCP over stdio. With ``mode="auto"`` (the default)
  or ``mode="stdio"``, every call spawns the target's MCP server file
  (``targets/<app>/mcp_server.py``, our stand-in for Synapse's generated
  ``synapse_auto_server.py``) as a subprocess using the official ``mcp``
  Python client, runs the initialize handshake, calls the tool, and
  shuts the server down. One short-lived server process per call: not
  the fastest design, but simple, stateless, and genuinely MCP — the
  tool that executes is the tool defined in the server file.

* FALLBACK path — direct mapping. If the stdio handshake fails for any
  reason (and only in ``mode="auto"``), ``call_tool`` falls back to
  executing the same tool definition directly: TOOL_SPECS below mirror
  the server files tool-for-tool (same name, same HTTP method/path,
  same read/write effect) and the call is made with httpx against the
  target app. ``client.last_transport`` records which path served the
  most recent call (``"stdio"`` or ``"direct"``) so nothing is hidden.
  ``mode="direct"`` forces the fallback (useful in tests); ``mode=
  "stdio"`` disables it and lets errors propagate.

Either way the invariant THE FLOOR cares about holds: the orchestrator
can only ever invoke the allowlisted tools — there is no code path here
that reaches a non-tool endpoint of a target app.

Usage:
    client = ToolClient()                       # auto mode
    tools = client.list_tools("ticketdesk")     # [{name, description, effect, input_schema}]
    out = client.call_tool("ticketdesk", "read_list_tickets", {"assignee": "none"})
    out = client.call_tool("stockroom", "write_adjust_item",
                           {"item_id": 3, "delta": 50})   # write — gate BEFORE calling
    client.is_write("ticketdesk", "write_assign_ticket")  # True

server_kind is one of the keys of SERVERS (ticketdesk, stockroom,
qa, bookkeeping, sdr, engineering, hrdesk, seo). Base URLs come from the
TICKETDESK_URL / STOCKROOM_URL env vars (defaults :8101 / :8102), the
same vars the MCP server files read.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent

SERVERS: dict[str, dict[str, Any]] = {
    "ticketdesk": {
        "server_file": REPO_ROOT / "targets" / "ticketdesk" / "mcp_server.py",
        "env_var": "TICKETDESK_URL",
        "default_url": "http://localhost:8101",
    },
    "stockroom": {
        "server_file": REPO_ROOT / "targets" / "stockroom" / "mcp_server.py",
        "env_var": "STOCKROOM_URL",
        "default_url": "http://localhost:8102",
    },
    "qa": {
        "server_file": REPO_ROOT / "targets" / "qa" / "mcp_server.py",
        "env_var": "QA_URL",
        "default_url": "http://localhost:8103",
    },
    "bookkeeping": {
        "server_file": REPO_ROOT / "targets" / "bookkeeping" / "mcp_server.py",
        "env_var": "BOOKKEEPING_URL",
        "default_url": "http://localhost:8104",
    },
    "sdr": {
        "server_file": REPO_ROOT / "targets" / "sdr" / "mcp_server.py",
        "env_var": "SDR_URL",
        "default_url": "http://localhost:8105",
    },
    "engineering": {
        "server_file": REPO_ROOT / "targets" / "engineering" / "mcp_server.py",
        "env_var": "ENGINEERING_URL",
        "default_url": "http://localhost:8106",
    },
    "hrdesk": {
        "server_file": REPO_ROOT / "targets" / "hrdesk" / "mcp_server.py",
        "env_var": "HRDESK_URL",
        "default_url": "http://localhost:8107",
    },
    "seo": {
        "server_file": REPO_ROOT / "targets" / "seo" / "mcp_server.py",
        "env_var": "SEO_URL",
        "default_url": "http://localhost:8109",
    },
}

# Mirror of the tools defined in targets/*/mcp_server.py — same names,
# same HTTP mapping, same effects. Used by the direct fallback path and
# by list_tools() when stdio is unavailable. Keep in sync with the
# server files; the verification in this package's history exercised
# both paths against the live apps.
TOOL_SPECS: dict[str, dict[str, dict[str, str]]] = {
    "ticketdesk": {
        "read_list_tickets":        {"method": "GET",  "path": "/tickets", "effect": "read"},
        "read_get_ticket":          {"method": "GET",  "path": "/tickets/{ticket_id}", "effect": "read"},
        "read_find_duplicate_tickets": {"method": "GET", "path": "/tickets/duplicates", "effect": "read"},
        "read_sla_breaches":        {"method": "GET",  "path": "/sla/breaches", "effect": "read"},
        "read_stats_summary":       {"method": "GET",  "path": "/stats/summary", "effect": "read"},
        "write_create_ticket":      {"method": "POST", "path": "/tickets", "effect": "write"},
        "write_assign_ticket":      {"method": "POST", "path": "/tickets/{ticket_id}/assign", "effect": "write"},
        "write_set_ticket_priority": {"method": "POST", "path": "/tickets/{ticket_id}/priority", "effect": "write"},
        "write_add_ticket_comment": {"method": "POST", "path": "/tickets/{ticket_id}/comment", "effect": "write"},
        "write_set_ticket_status":  {"method": "POST", "path": "/tickets/{ticket_id}/status", "effect": "write"},
        "write_merge_tickets":      {"method": "POST", "path": "/tickets/merge", "effect": "write"},
    },
    "stockroom": {
        "read_list_items":          {"method": "GET",  "path": "/items", "effect": "read"},
        "read_get_item":            {"method": "GET",  "path": "/items/{item_id}", "effect": "read"},
        "read_low_stock":           {"method": "GET",  "path": "/items/low-stock", "effect": "read"},
        "read_pending_orders":      {"method": "GET",  "path": "/orders/pending", "effect": "read"},
        "read_stats_summary":       {"method": "GET",  "path": "/stats/summary", "effect": "read"},
        "write_adjust_item":        {"method": "POST", "path": "/items/{item_id}/adjust", "effect": "write"},
    },
    "qa": {
        "read_get_failure_detail": {"method": "GET", "path": "/failures/{failure_id}", "effect": "read"},
        "read_list_failures": {"method": "GET", "path": "/failures", "effect": "read"},
        "read_list_runs": {"method": "GET", "path": "/runs", "effect": "read"},
        "write_add_triage_note": {"method": "POST", "path": "/triage-notes", "effect": "write"},
        "write_cluster_failures": {"method": "POST", "path": "/failures/cluster", "effect": "write"},
        "write_quarantine_test": {"method": "POST", "path": "/tests/quarantine", "effect": "write"},
        "write_set_regression_verdict": {"method": "POST", "path": "/runs/{run_id}/regression-verdict", "effect": "write"},
    },
    "bookkeeping": {
        "read_chart_of_accounts": {"method": "GET", "path": "/chart", "effect": "read"},
        "read_find_duplicates": {"method": "GET", "path": "/transactions/duplicates", "effect": "read"},
        "read_list_accounts": {"method": "GET", "path": "/accounts", "effect": "read"},
        "read_list_notes": {"method": "GET", "path": "/notes", "effect": "read"},
        "read_list_receivables": {"method": "GET", "path": "/receivables", "effect": "read"},
        "read_list_transactions": {"method": "GET", "path": "/transactions", "effect": "read"},
        "read_list_uncategorised": {"method": "GET", "path": "/transactions/uncategorised", "effect": "read"},
        "read_reconcile_account": {"method": "GET", "path": "/accounts/{account_id}/reconcile", "effect": "read"},
        "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
        "write_add_finance_note": {"method": "POST", "path": "/notes", "effect": "write"},
        "write_categorise_transaction": {"method": "POST", "path": "/transactions/{txn_id}/categorise", "effect": "write"},
        "write_flag_duplicate": {"method": "POST", "path": "/transactions/{txn_id}/flag-duplicate", "effect": "write"},
        "write_send_reminder": {"method": "POST", "path": "/receivables/{invoice_id}/reminder", "effect": "write"},
    },
    "sdr": {
        "get_account": {"method": "GET", "path": "/accounts/{account_id}", "effect": "read"},
        "list_accounts": {"method": "GET", "path": "/accounts", "effect": "read"},
        "list_leads": {"method": "GET", "path": "/leads", "effect": "read"},
        "research_account": {"method": "GET", "path": "/accounts/{account_id}/research", "effect": "read"},
        "add_crm_note": {"method": "POST", "path": "/notes", "effect": "write"},
        "draft_outreach": {"method": "POST", "path": "/leads/{lead_id}/draft", "effect": "write"},
        "qualify_lead": {"method": "POST", "path": "/leads/{lead_id}/qualify", "effect": "write"},
        "score_lead": {"method": "POST", "path": "/leads/{lead_id}/score", "effect": "write"},
    },
    "engineering": {
        "read_get_ci_status": {"method": "GET", "path": "/prs/{pr_id}/ci", "effect": "read"},
        "read_get_issue": {"method": "GET", "path": "/issues/{issue_id}", "effect": "read"},
        "read_get_pr": {"method": "GET", "path": "/prs/{pr_id}", "effect": "read"},
        "read_list_issues": {"method": "GET", "path": "/issues", "effect": "read"},
        "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
        "write_add_eng_note": {"method": "POST", "path": "/issues/{issue_id}/note", "effect": "write"},
        "write_approve_pr": {"method": "POST", "path": "/prs/{pr_id}/approve", "effect": "write"},
        "write_claim_issue": {"method": "POST", "path": "/issues/{issue_id}/claim", "effect": "write"},
        "write_open_pr": {"method": "POST", "path": "/prs", "effect": "write"},
        "write_request_changes": {"method": "POST", "path": "/prs/{pr_id}/request-changes", "effect": "write"},
        "write_triage_issue": {"method": "POST", "path": "/issues/{issue_id}/triage", "effect": "write"},
    },
    "hrdesk": {
        "read_get_candidate": {"method": "GET", "path": "/candidates/{candidate_id}", "effect": "read"},
        "read_list_candidates": {"method": "GET", "path": "/candidates", "effect": "read"},
        "read_list_onboarding": {"method": "GET", "path": "/onboarding", "effect": "read"},
        "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
        "write_add_hr_note": {"method": "POST", "path": "/candidates/{candidate_id}/notes", "effect": "write"},
        "write_complete_onboarding_step": {"method": "POST", "path": "/onboarding/{candidate_id}/steps/{step_key}/complete", "effect": "write"},
        "write_schedule_interview": {"method": "POST", "path": "/candidates/{candidate_id}/interviews", "effect": "write"},
        "write_screen_candidate": {"method": "POST", "path": "/candidates/{candidate_id}/screen", "effect": "write"},
    },
    "seo": {
        "read_get_keyword": {"method": "GET", "path": "/keywords/{keyword_id}", "effect": "read"},
        "read_get_page_audit": {"method": "GET", "path": "/pages/{page_id}/audit", "effect": "read"},
        "read_list_audit_reports": {"method": "GET", "path": "/audit-reports", "effect": "read"},
        "read_list_keywords": {"method": "GET", "path": "/keywords", "effect": "read"},
        "read_list_link_plans": {"method": "GET", "path": "/link-plans", "effect": "read"},
        "read_list_links": {"method": "GET", "path": "/links", "effect": "read"},
        "read_list_pages": {"method": "GET", "path": "/pages", "effect": "read"},
        "write_save_audit_report": {"method": "POST", "path": "/audit-reports", "effect": "write"},
        "write_save_content_brief": {"method": "POST", "path": "/briefs", "effect": "write"},
        "write_save_link_plan": {"method": "POST", "path": "/link-plans", "effect": "write"},
        "write_update_keyword_target": {"method": "POST", "path": "/keywords/{keyword_id}/target", "effect": "write"},
    },
}


class ToolClient:
    """Synchronous MCP tool client for THE FLOOR's orchestrator."""

    def __init__(self, mode: str = "auto"):
        if mode not in ("auto", "stdio", "direct"):
            raise ValueError(f"unknown mode {mode!r} (auto|stdio|direct)")
        self.mode = mode
        self.last_transport: Optional[str] = None
        self.last_error: Optional[str] = None

    # -- public API --------------------------------------------------------

    def base_url(self, server_kind: str) -> str:
        cfg = self._cfg(server_kind)
        return os.environ.get(cfg["env_var"], cfg["default_url"]).rstrip("/")

    def is_write(self, server_kind: str, tool_name: str) -> bool:
        return self._spec(server_kind, tool_name)["effect"] == "write"

    def effect(self, server_kind: str, tool_name: str) -> str:
        return self._spec(server_kind, tool_name)["effect"]

    def list_tools(self, server_kind: str) -> list[dict]:
        """Tool list for a server: from the live MCP server when possible,
        otherwise from TOOL_SPECS. Each entry: name, description (stdio
        path only), effect, input_schema (stdio path only)."""
        if self.mode in ("auto", "stdio"):
            try:
                tools = asyncio.run(self._stdio_list_tools(server_kind))
                self.last_transport = "stdio"
                return [self._with_effect(server_kind, t) for t in tools]
            except Exception as exc:  # noqa: BLE001 — fallback is the point
                self.last_error = f"stdio list_tools failed: {exc}"
                if self.mode == "stdio":
                    raise
        self.last_transport = "direct"
        return [
            {"name": name, "description": "", "effect": spec["effect"],
             "input_schema": {}}
            for name, spec in TOOL_SPECS[server_kind].items()
        ]

    def call_tool(self, server_kind: str, tool_name: str,
                  args: Optional[dict] = None) -> Any:
        """Execute one allowlisted tool and return its parsed result."""
        args = dict(args or {})
        self._spec(server_kind, tool_name)  # validate before doing anything
        if self.mode in ("auto", "stdio"):
            try:
                result = asyncio.run(
                    self._stdio_call_tool(server_kind, tool_name, args))
                self.last_transport = "stdio"
                return result
            except Exception as exc:  # noqa: BLE001 — fallback is the point
                self.last_error = f"stdio call_tool failed: {exc}"
                if self.mode == "stdio":
                    raise
        self.last_transport = "direct"
        return self._direct_call_tool(server_kind, tool_name, args)

    # -- stdio (real MCP) path ----------------------------------------------

    def _server_params(self, server_kind: str):
        from mcp import StdioServerParameters

        cfg = self._cfg(server_kind)
        env = dict(os.environ)
        env[cfg["env_var"]] = self.base_url(server_kind)
        return StdioServerParameters(
            command=sys.executable,
            args=[str(cfg["server_file"])],
            env=env,
        )

    async def _stdio_list_tools(self, server_kind: str) -> list[dict]:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._server_params(server_kind)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [
                    {"name": t.name, "description": t.description or "",
                     "input_schema": getattr(t, "input_schema", None)
                     or getattr(t, "inputSchema", None) or {}}
                    for t in result.tools
                ]

    async def _stdio_call_tool(self, server_kind: str, tool_name: str,
                               args: dict) -> Any:
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async with stdio_client(self._server_params(server_kind)) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                return self._parse_result(result)

    @staticmethod
    def _parse_result(result) -> Any:
        if getattr(result, "is_error", False):
            texts = [getattr(b, "text", "") for b in result.content or []]
            raise RuntimeError(f"MCP tool returned an error: {texts}")
        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured
        texts = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text is not None:
                texts.append(text)
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except ValueError:
                return texts[0]
        return texts

    # -- direct fallback path -------------------------------------------------

    def _direct_call_tool(self, server_kind: str, tool_name: str,
                          args: dict) -> Any:
        spec = self._spec(server_kind, tool_name)
        path = spec["path"]
        remaining = dict(args)
        # Fill {placeholders} in the path from args.
        for key in list(remaining):
            token = "{" + key + "}"
            if token in path:
                path = path.replace(token, str(remaining.pop(key)))
        if "{" in path:
            return {"error": f"missing path argument for {tool_name}: {path}"}
        base = self.base_url(server_kind)
        try:
            with httpx.Client(base_url=base, timeout=10.0, trust_env=False) as client:
                if spec["method"] == "GET":
                    resp = client.get(path, params=remaining or None)
                else:
                    resp = client.request(spec["method"], path, json=remaining)
        except httpx.HTTPError as exc:
            return {"error": f"{server_kind} unreachable at {base}: {exc}"}
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            return {"error": detail, "status_code": resp.status_code}
        return resp.json()

    # -- internals -------------------------------------------------------------

    def _cfg(self, server_kind: str) -> dict:
        try:
            return SERVERS[server_kind]
        except KeyError:
            raise ValueError(
                f"unknown server_kind {server_kind!r} "
                f"(expected one of {sorted(SERVERS)})") from None

    def _spec(self, server_kind: str, tool_name: str) -> dict:
        self._cfg(server_kind)
        try:
            return TOOL_SPECS[server_kind][tool_name]
        except KeyError:
            raise ValueError(
                f"unknown tool {tool_name!r} for {server_kind} "
                f"(allowlist: {sorted(TOOL_SPECS[server_kind])})") from None

    def _with_effect(self, server_kind: str, tool: dict) -> dict:
        spec = TOOL_SPECS.get(server_kind, {}).get(tool["name"])
        tool["effect"] = spec["effect"] if spec else (
            "write" if tool["name"].startswith("write_") else "read")
        return tool
