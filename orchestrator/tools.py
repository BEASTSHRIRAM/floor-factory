"""Tool access for THE FLOOR's orchestrator — the factory's only hands.

Primary path: ``mcp_manager.ToolClient`` (real MCP over stdio against the
Synapse-style server files in targets/*/, with its own direct fallback).
If ``mcp_manager`` cannot be imported at all, this module's
``DirectToolClient`` speaks the exact same allowlisted tool mapping over
plain httpx, so the engine's contract (call_tool / is_write / effect /
list_tools / last_transport) is identical either way.

The confirmation gate also lives here: every write tool call must be
confirmed before dispatch (ARCHITECTURE §4.3). The gate branches on the
floor mode (``orchestrator.mode``, settable via the API — see
``docs/MODES.md``):

* ``manual`` (default): the gate registers a pending approval and blocks
  until someone resolves it via ``resolve_approval()`` (the API exposes
  this as ``POST /approvals/{confirmation_id}``) or
  ``FLOOR_CONFIRM_TIMEOUT_S`` seconds pass (default 120), after which the
  write is DENIED and never executed.
* ``auto``: writes auto-approve with ``confirmed_by='auto'``, and every
  auto-approval is audited — a ``confirmation.auto_approved`` event is
  emitted to the floor event log (plus an in-memory record served by the
  API). Auto mode changes the approval flow ONLY: tool allowlists and the
  deterministic checks are untouched, and tools that don't exist (money
  movement, merge, hire/reject decisions) stay nonexistent.

Boot seeding: ``FLOOR_MODE`` env, else an explicitly-set legacy
``POLICY_AUTO_APPROVE_WRITES`` (``true`` -> auto, ``false`` -> manual),
else ``manual``.
"""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections import deque
from typing import Any, Optional

import httpx

try:
    from . import mode as _floor_mode
except Exception:  # noqa: BLE001 — imported as a top-level module
    from orchestrator import mode as _floor_mode  # type: ignore

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
}

_BASE_URLS = {
    "ticketdesk": ("TICKETDESK_URL", "http://localhost:8101"),
    "stockroom": ("STOCKROOM_URL", "http://localhost:8102"),
    "qa": ("QA_URL", "http://localhost:8103"),
    "bookkeeping": ("BOOKKEEPING_URL", "http://localhost:8104"),
    "sdr": ("SDR_URL", "http://localhost:8105"),
    "engineering": ("ENGINEERING_URL", "http://localhost:8106"),
    "hrdesk": ("HRDESK_URL", "http://localhost:8107"),
}

_PATH_PARAMS = ("ticket_id", "item_id", "failure_id", "run_id",
                "txn_id", "invoice_id", "account_id", "lead_id",
                "issue_id", "pr_id", "candidate_id", "step_key")


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

# Audit trail for auto-mode approvals (the event log is the durable copy;
# this bounded in-memory record backs the API's /mode response).
_auto_approval_log: deque = deque(maxlen=500)
_auto_log_lock = threading.Lock()


def auto_approve_writes() -> bool:
    """True iff the floor is in auto mode (writes auto-approve, audited).

    Kept under its legacy name for the API's /approvals response; the
    branch is the floor mode now, not the POLICY_AUTO_APPROVE_WRITES env
    (that env only seeds the initial mode — see orchestrator.mode).
    """
    return _floor_mode.get_mode() == "auto"


def recent_auto_approvals(limit: int = 50) -> list[dict]:
    """Most recent auto-mode approvals, newest first (audit surface)."""
    with _auto_log_lock:
        return list(reversed(_auto_approval_log))[:limit]


def _emit_auto_approved(record: dict) -> None:
    """Best-effort: append confirmation.auto_approved to the floor event log.

    Uses its own short-lived connection (same pattern as the API's event
    emission). A failure here never blocks the gate — the in-memory audit
    record and the engine's tool.confirmation_requested event (which
    carries confirmed_by='auto') still stand.
    """
    try:
        try:
            from economy import db as _db
        except Exception:  # noqa: BLE001 — same fallback as the engine
            from orchestrator import shim as _db  # type: ignore
        conn = _db.get_conn()
        try:
            with conn:
                _db.emit_event(conn, "confirmation.auto_approved", record)
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — audit emit must never break the gate
        pass


def request_confirmation(work_order_id: int, tool_name: str, args: dict) -> tuple[str, bool, str]:
    """Gate a write call. Returns (confirmation_id, approved, confirmed_by).

    Auto mode: instant approval by 'auto', fully audited (see
    _emit_auto_approved). Manual mode: blocks until resolve_approval() is
    called (API approval endpoint) or the timeout expires, in which case
    the write is denied by 'policy' (timeout). The mode is read per call,
    so switching to manual mid-run stops auto-approvals for subsequent
    writes immediately.
    """
    confirmation_id = uuid.uuid4().hex
    if _floor_mode.get_mode() == "auto":
        record = {"confirmation_id": confirmation_id,
                  "work_order_id": work_order_id, "tool_name": tool_name,
                  "args": args, "mode": "auto", "approved_by": "auto"}
        with _auto_log_lock:
            _auto_approval_log.append(record)
        _emit_auto_approved(record)
        return confirmation_id, True, "auto"
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
