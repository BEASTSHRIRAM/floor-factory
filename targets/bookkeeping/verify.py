#!/usr/bin/env python3
"""End-to-end verification for the Bookkeeping department workplace.

Mirrors the factory's FLOOR_MCP_MODE=direct path: tools are invoked
through the same allowlisted name -> HTTP mapping the direct tool layer
uses (orchestrator/tools.py / mcp_manager TOOL_SPECS shape), against the
live app on :8104. Then each job in the jobs pack is worked by its
deterministic reference worker and graded by its deterministic Reviewer
check. Finally the MCP server file is smoke-tested over real stdio MCP.

Usage:  uvicorn app:app --port 8104   (in another terminal)
        python3 verify.py
Exits non-zero if anything fails.
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jobs as jobs_pack  # noqa: E402

BASE_URL = os.environ.get("BOOKKEEPING_URL", "http://localhost:8104").rstrip("/")

TOOL_SPECS = {
    "read_list_transactions": ("GET", "/transactions"),
    "read_list_uncategorised": ("GET", "/transactions/uncategorised"),
    "read_find_duplicates": ("GET", "/transactions/duplicates"),
    "read_reconcile_account": ("GET", "/accounts/{account_id}/reconcile"),
    "read_list_receivables": ("GET", "/receivables"),
    "read_list_accounts": ("GET", "/accounts"),
    "read_chart_of_accounts": ("GET", "/chart"),
    "read_list_notes": ("GET", "/notes"),
    "read_stats_summary": ("GET", "/stats/summary"),
    "write_categorise_transaction": ("POST", "/transactions/{txn_id}/categorise"),
    "write_flag_duplicate": ("POST", "/transactions/{txn_id}/flag-duplicate"),
    "write_send_reminder": ("POST", "/receivables/{invoice_id}/reminder"),
    "write_add_finance_note": ("POST", "/notes"),
}

FAILURES: list[str] = []


def call(tool_name: str, args: dict | None = None) -> dict:
    """Direct-mode tool call — the same contract the engine uses."""
    args = dict(args or {})
    method, path = TOOL_SPECS[tool_name]
    body: dict = {}
    params: dict = {}
    for key, value in list(args.items()):
        token = "{" + key + "}"
        if token in path:
            path = path.replace(token, str(value))
        elif method == "GET":
            if value is not None:
                params[key] = value
        else:
            body[key] = value
    with httpx.Client(base_url=BASE_URL, timeout=15.0, trust_env=False) as client:
        resp = client.request(method, path, params=params or None,
                              json=body or None)
    try:
        data = resp.json()
    except ValueError:
        data = {"raw": resp.text}
    if resp.status_code >= 400:
        return {"error": data, "status_code": resp.status_code}
    return data


def expect(label: str, cond: bool, evidence: str = "") -> None:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {evidence}" if evidence else ""))
    if not cond:
        FAILURES.append(label)


def main() -> int:
    print(f"== Bookkeeping verification against {BASE_URL} (direct mode) ==\n")

    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as c:
        assert c.get("/health").status_code == 200, "app not healthy — is it running?"
        r = c.post("/admin/reset")
        assert r.status_code == 200, f"reset failed: {r.text}"
    print(f"Reset to seeded state: {r.json()}\n")

    print("-- Seed shape --")
    stats = call("read_stats_summary", {})
    expect("49 transactions seeded", stats["total_transactions"] == 49,
           str(stats["total_transactions"]))
    expect("12 uncategorised", stats["uncategorised"] == 12, str(stats["uncategorised"]))
    expect("8 uncategorised older than 7d", stats["uncategorised_older_than_7d"] == 8,
           str(stats["uncategorised_older_than_7d"]))
    expect("3 duplicate groups open", stats["duplicate_groups_open"] == 3,
           str(stats["duplicate_groups_open"]))
    expect("0 duplicates flagged yet", stats["duplicates_flagged"] == 0)
    expect("6 overdue invoices", stats["overdue_invoices"] == 6,
           str(stats["overdue_invoices"]))

    print("\n-- Every read tool --")
    txns = call("read_list_transactions", {})
    expect("read_list_transactions", txns["count"] == 49, f"count={txns['count']}")
    uncat = call("read_list_uncategorised", {})
    expect("read_list_uncategorised", uncat["count"] == 12, f"count={uncat['count']}")
    dup = call("read_find_duplicates", {})
    expect("read_find_duplicates", dup["group_count"] == 3,
           f"groups={dup['group_count']}")
    rec = call("read_reconcile_account", {"account_id": 1})
    expect("read_reconcile_account delta is +751", rec.get("delta") == 751,
           f"recorded={rec.get('recorded_balance')} statement="
           f"{rec.get('statement_balance')} delta={rec.get('delta')}")
    recv = call("read_list_receivables", {})
    expect("read_list_receivables", recv["count"] == 11, f"count={recv['count']}")
    accts = call("read_list_accounts", {})
    expect("read_list_accounts", accts["count"] == 3, f"count={accts['count']}")
    chart = call("read_chart_of_accounts", {})
    expect("read_chart_of_accounts", chart["count"] == 14, f"count={chart['count']}")
    notes = call("read_list_notes", {})
    expect("read_list_notes (empty at seed)", notes["count"] == 0)

    print("\n-- Safety rails (must all be refused) --")
    bad = call("write_categorise_transaction", {"txn_id": 37, "category": "bogus"})
    expect("invalid category refused (422)", bad.get("status_code") == 422)
    not_due = [i for i in recv["invoices"] if i["invoice_no"] == "INV-1046"][0]
    early = call("write_send_reminder", {"invoice_id": not_due["id"], "note": "too soon"})
    expect("reminder for not-yet-due invoice refused (422)",
           early.get("status_code") == 422)
    selfdup = call("write_flag_duplicate", {"txn_id": 3, "duplicate_of": 3})
    expect("self-duplicate flag refused (422)", selfdup.get("status_code") == 422)

    print("\n-- Jobs end-to-end (reference worker + deterministic check) --")
    for family in jobs_pack.JOB_FAMILIES:
        print(f"\nJob: {family.title} (budget ₡{family.budget})")
        actions = jobs_pack.WORKERS[family.key](call)
        print(f"  worker actions: {actions}")
        for finding in jobs_pack.CHECKS[family.key](call):
            expect(f"check: {finding['criterion'][:60]}...", finding["pass"],
                   finding["evidence"])

    print("\n-- Final stats --")
    stats = call("read_stats_summary", {})
    print(f"  {stats}")
    expect("queue cleared of old uncategorised",
           stats["uncategorised_older_than_7d"] == 0)
    expect("all duplicates flagged", stats["duplicates_flagged"] == 3)
    expect("no open duplicate groups", stats["duplicate_groups_open"] == 0)

    print("\n-- MCP server over stdio (real MCP handshake) --")
    mcp_ok = asyncio.run(_mcp_smoke())
    expect("stdio MCP: list_tools + one read + one write call", mcp_ok)

    print()
    if FAILURES:
        print(f"RESULT: FAIL ({len(FAILURES)}): {FAILURES}")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


async def _mcp_smoke() -> bool:
    try:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client
    except Exception as exc:  # noqa: BLE001
        print(f"  mcp package unavailable: {exc}")
        return False
    import json

    server_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "mcp_server.py")
    env = dict(os.environ)
    env["BOOKKEEPING_URL"] = BASE_URL
    params = StdioServerParameters(command=sys.executable, args=[server_file], env=env)
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = sorted(t.name for t in tools.tools)
                print(f"  tools via MCP: {names}")
                if names != sorted(TOOL_SPECS):
                    return False

                def _parse(result):
                    if getattr(result, "structured_content", None) is not None:
                        return result.structured_content
                    texts = [getattr(b, "text", "") for b in result.content or []]
                    return json.loads(texts[0]) if texts else {}

                out = _parse(await session.call_tool("read_stats_summary", {}))
                print(f"  read_stats_summary via MCP: total={out.get('total_transactions')}")
                if out.get("total_transactions") != 49:
                    return False
                # One write through MCP: note against petty cash, then reset
                # state is NOT restored (verify.py starts from a fresh reset
                # on its next run; the note is additive only).
                note = _parse(await session.call_tool(
                    "write_add_finance_note",
                    {"text": "MCP stdio smoke-test note", "kind": "audit"}))
                print(f"  write_add_finance_note via MCP: id={note.get('id')}")
                return note.get("id") is not None
    except Exception as exc:  # noqa: BLE001
        print(f"  MCP stdio smoke failed: {exc}")
        return False


if __name__ == "__main__":
    raise SystemExit(main())
