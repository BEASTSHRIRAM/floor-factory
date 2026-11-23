"""Tool access for THE FLOOR's orchestrator — the factory's only hands.

Primary path: ``mcp_manager.ToolClient`` (real MCP over stdio against the
Synapse-style server files in targets/*/, with its own direct fallback).
If ``mcp_manager`` cannot be imported at all, this module's
``DirectToolClient`` speaks the exact same allowlisted tool mapping over
plain httpx, so the engine's contract (call_tool / is_write / effect /
list_tools / last_transport) is identical either way.

The confirmation gate also lives here: every write tool call must be
confirmed before dispatch (ARCHITECTURE §4.3). Policy:

* ``POLICY_AUTO_APPROVE_WRITES`` env, default ``True`` (per the headless-demo
  brief): writes are auto-approved, ``confirmed_by='policy'``, and a
  ``tool.confirmation_requested`` + decision is still logged by the engine.
* When ``False``: the gate registers a pending approval and blocks until
  someone resolves it via ``resolve_approval()`` (the API exposes this as
  ``POST /approvals/{confirmation_id}``) or ``FLOOR_CONFIRM_TIMEOUT_S``
  seconds pass (default 120), after which the write is DENIED and never
  executed.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# Direct fallback client (same tool mapping as mcp_manager.TOOL_SPECS)
# ---------------------------------------------------------------------------

TOOL_SPECS: dict[str, dict[str, dict[str, str]]] = {
    "ticketdesk": {
        "read_list_tickets": {"method": "GET", "path": "/tickets", "effect": "read"},
        "read_get_ticket": {"method": "GET", "path": "/tickets/{ticket_id}", "effect": "read"},
        "read_find_duplicate_tickets": {"method": "GET", "path": "/tickets/duplicates", "effect": "read"},
        "read_sla_breaches": {"method": "GET", "path": "/sla/breaches", "effect": "read"},
        "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
        "write_create_ticket": {"method": "POST", "path": "/tickets", "effect": "write"},
        "write_assign_ticket": {"method": "POST", "path": "/tickets/{ticket_id}/assign", "effect": "write"},
        "write_set_ticket_priority": {"method": "POST", "path": "/tickets/{ticket_id}/priority", "effect": "write"},
        "write_add_ticket_comment": {"method": "POST", "path": "/tickets/{ticket_id}/comment", "effect": "write"},
        "write_set_ticket_status": {"method": "POST", "path": "/tickets/{ticket_id}/status", "effect": "write"},
        "write_merge_tickets": {"method": "POST", "path": "/tickets/merge", "effect": "write"},
    },
    "stockroom": {
        "read_list_items": {"method": "GET", "path": "/items", "effect": "read"},
        "read_get_item": {"method": "GET", "path": "/items/{item_id}", "effect": "read"},
        "read_low_stock": {"method": "GET", "path": "/items/low-stock", "effect": "read"},
        "read_pending_orders": {"method": "GET", "path": "/orders/pending", "effect": "read"},
        "read_stats_summary": {"method": "GET", "path": "/stats/summary", "effect": "read"},
        "write_adjust_item": {"method": "POST", "path": "/items/{item_id}/adjust", "effect": "write"},
    },
}

_BASE_URLS = {
    "ticketdesk": ("TICKETDESK_URL", "http://localhost:8101"),
    "stockroom": ("STOCKROOM_URL", "http://localhost:8102"),
}

_PATH_PARAMS = ("ticket_id", "item_id")


class DirectToolClient:
    """httpx implementation of the ToolClient contract (fallback only)."""

    def __init__(self, mode: str = "direct"):
        self.mode = mode
        self.last_transport: Optional[str] = "direct"
        self.last_error: Optional[str] = None

    def base_url(self, server_kind: str) -> str:
        env_var, default = _BASE_URLS[server_kind]
        return os.environ.get(env_var, default).rstrip("/")

    def _spec(self, server_kind: str, tool_name: str) -> dict:
        try:
            return TOOL_SPECS[server_kind][tool_name]
        except KeyError:
            raise ValueError(f"unknown tool {tool_name!r} for {server_kind!r}") from None

    def is_write(self, server_kind: str, tool_name: str) -> bool:
        return self._spec(server_kind, tool_name)["effect"] == "write"

    def effect(self, server_kind: str, tool_name: str) -> str:
        return self._spec(server_kind, tool_name)["effect"]

    def list_tools(self, server_kind: str) -> list[dict]:
        return [
            {"name": name, "description": "", "effect": spec["effect"], "input_schema": {}}
            for name, spec in TOOL_SPECS[server_kind].items()
        ]

    def call_tool(self, server_kind: str, tool_name: str, args: Optional[dict] = None) -> Any:
        args = dict(args or {})
        spec = self._spec(server_kind, tool_name)
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
        url = self.base_url(server_kind) + path
        # trust_env=False: local targets only, and this VM's no_proxy value
        # (bracketed IPv6 entries) breaks this httpx version's proxy parsing.
        with httpx.Client(timeout=15.0, trust_env=False) as client:
            if spec["method"] == "GET":
                resp = client.get(url, params=params)
            else:
                resp = client.post(url, json=body)
        resp.raise_for_status()
        self.last_transport = "direct"
        return resp.json()


def get_tool_client():
    """Return mcp_manager.ToolClient if importable, else DirectToolClient."""
    mode = os.environ.get("FLOOR_MCP_MODE", "auto")
    try:
        from mcp_manager import ToolClient

        return ToolClient(mode=mode)
    except Exception:  # noqa: BLE001 — engine must run even if the MCP layer is absent
        return DirectToolClient()


# ---------------------------------------------------------------------------
# Confirmation gate (ARCHITECTURE §4.3)
# ---------------------------------------------------------------------------

_pending: dict[str, dict] = {}
_pending_lock = threading.Lock()


def auto_approve_writes() -> bool:
    return os.environ.get("POLICY_AUTO_APPROVE_WRITES", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


def request_confirmation(work_order_id: int, tool_name: str, args: dict) -> tuple[str, bool, str]:
    """Gate a write call. Returns (confirmation_id, approved, confirmed_by).

    Policy mode: instant approval by 'policy'. Manual mode: blocks until
    resolve_approval() is called (API approval endpoint) or the timeout
    expires, in which case the write is denied by 'policy' (timeout).
    """
    confirmation_id = uuid.uuid4().hex
    if auto_approve_writes():
        return confirmation_id, True, "policy"
    timeout = float(os.environ.get("FLOOR_CONFIRM_TIMEOUT_S", "120"))
    with _pending_lock:
        _pending[confirmation_id] = {
            "work_order_id": work_order_id, "tool_name": tool_name, "args": args,
            "decision": None, "by": None, "event": threading.Event(),
        }
    entry = _pending[confirmation_id]
    entry["event"].wait(timeout=timeout)
    with _pending_lock:
        _pending.pop(confirmation_id, None)
    if entry["decision"] is None:
        return confirmation_id, False, "policy"  # timed out -> denied
    return confirmation_id, bool(entry["decision"]), entry["by"] or "human"


def resolve_approval(confirmation_id: str, approved: bool, by: str = "human") -> bool:
    """Resolve a pending manual confirmation. Returns False if unknown id."""
    with _pending_lock:
        entry = _pending.get(confirmation_id)
        if entry is None:
            return False
        entry["decision"] = approved
        entry["by"] = by
        entry["event"].set()
        return True


def pending_approvals() -> list[dict]:
    with _pending_lock:
        return [
            {"confirmation_id": cid, "work_order_id": e["work_order_id"],
             "tool_name": e["tool_name"], "args": e["args"]}
            for cid, e in _pending.items() if e["decision"] is None
        ]
