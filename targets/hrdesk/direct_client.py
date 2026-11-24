"""Direct-mode tool layer for HRDesk — the FLOOR_MCP_MODE=direct path.

Mirrors orchestrator/tools.py's DirectToolClient contract exactly (same
TOOL_SPECS shape, same call_tool / is_write / effect / list_tools surface,
same read_/write_ tool names as mcp_server.py), scoped to this one
department so the HR workplace can be exercised standalone, without the
orchestrator. Writes pass a confirmation gate identical in policy to the
factory's: POLICY_AUTO_APPROVE_WRITES env, default True — auto-approved
by 'policy' and logged; when False, writes are denied unless the caller
passes an explicit human approval via approve_next_write().

Base URL: env HRDESK_URL (default http://localhost:8107).
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

SERVER_KIND = "hr"

TOOL_SPECS: dict[str, dict[str, str]] = {
    "read_list_candidates":          {"method": "GET",  "path": "/candidates", "effect": "read"},
    "read_get_candidate":            {"method": "GET",  "path": "/candidates/{candidate_id}", "effect": "read"},
    "read_list_onboarding":          {"method": "GET",  "path": "/onboarding", "effect": "read"},
    "read_stats_summary":            {"method": "GET",  "path": "/stats/summary", "effect": "read"},
    "write_screen_candidate":        {"method": "POST", "path": "/candidates/{candidate_id}/screen", "effect": "write"},
    "write_schedule_interview":      {"method": "POST", "path": "/candidates/{candidate_id}/interviews", "effect": "write"},
    "write_complete_onboarding_step": {"method": "POST", "path": "/onboarding/{candidate_id}/steps/{step_key}/complete", "effect": "write"},
    "write_add_hr_note":             {"method": "POST", "path": "/candidates/{candidate_id}/notes", "effect": "write"},
}

_PATH_PARAMS = ("candidate_id", "step_key")


def auto_approve_writes() -> bool:
    return os.environ.get("POLICY_AUTO_APPROVE_WRITES", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


class ConfirmationDenied(PermissionError):
    pass


class DirectToolClient:
    """httpx implementation of the factory ToolClient contract for HRDesk."""

    def __init__(self):
        self.last_transport: Optional[str] = "direct"
        self.confirmations: list[dict] = []  # gate log: every write decision
        self._human_approvals = 0

    def base_url(self) -> str:
        return os.environ.get("HRDESK_URL", "http://localhost:8107").rstrip("/")

    def _spec(self, tool_name: str) -> dict:
        try:
            return TOOL_SPECS[tool_name]
        except KeyError:
            raise ValueError(f"unknown tool {tool_name!r} for {SERVER_KIND!r}") from None

    def is_write(self, tool_name: str) -> bool:
        return self._spec(tool_name)["effect"] == "write"

    def effect(self, tool_name: str) -> str:
        return self._spec(tool_name)["effect"]

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "description": "", "effect": spec["effect"],
             "input_schema": {}}
            for name, spec in TOOL_SPECS.items()
        ]

    def approve_next_write(self) -> None:
        """A human approves the next write when policy auto-approve is off."""
        self._human_approvals += 1

    def _gate(self, tool_name: str, args: dict) -> None:
        if auto_approve_writes():
            self.confirmations.append(
                {"tool": tool_name, "args": args, "approved": True,
                 "confirmed_by": "policy"})
            return
        if self._human_approvals > 0:
            self._human_approvals -= 1
            self.confirmations.append(
                {"tool": tool_name, "args": args, "approved": True,
                 "confirmed_by": "human"})
            return
        self.confirmations.append(
            {"tool": tool_name, "args": args, "approved": False,
             "confirmed_by": "policy"})
        raise ConfirmationDenied(
            f"write {tool_name} denied at confirmation gate "
            "(POLICY_AUTO_APPROVE_WRITES off, no human approval)")

    def call_tool(self, tool_name: str, args: Optional[dict] = None) -> Any:
        args = dict(args or {})
        spec = self._spec(tool_name)
        if spec["effect"] == "write":
            self._gate(tool_name, args)
        path = spec["path"]
        params: dict[str, Any] = {}
        body: dict[str, Any] = {}
        for key, value in args.items():
            if key in _PATH_PARAMS and "{" + key + "}" in path:
                path = path.replace("{" + key + "}", str(value))
            elif spec["method"] == "GET":
                if value is not None:
                    params[key] = value
            else:
                body[key] = value
        url = self.base_url() + path
        # trust_env=False: local target only (same rationale as TicketDesk).
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            if spec["method"] == "GET":
                resp = client.get(url, params=params)
            else:
                resp = client.post(url, json=body)
        resp.raise_for_status()
        self.last_transport = "direct"
        return resp.json()
