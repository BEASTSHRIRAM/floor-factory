#!/usr/bin/env python3
"""End-to-end verification for the SEO workplace (targets/seo).

Requires the SEODash app running:  uvicorn app:app --port 8109

Phases:
  1. Exercise EVERY tool (reads + writes) in direct mode, using the
     tool_specs mapping from department.json — the same direct-mode
     tool layer shape the orchestrator uses (FLOOR_MCP_MODE=direct).
  2. Reset, then run all three jobs from jobs.json end-to-end with a
     deterministic worker (execute tools -> Reviewer checks via
     checks.py). All checks must pass; a tampered audit report must
     make the audit check FAIL (negative control).
  3. MCP over stdio: spawn mcp_server.py with the official mcp client,
     list tools (expect the 11 allowlisted), call two reads.

Exit code 0 iff every assertion passes. Prints one line per assertion.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checks as CHECKS  # noqa: E402

BASE_URL = os.environ.get("SEO_URL", "http://localhost:8109").rstrip("/")
MANIFEST = json.loads((HERE / "department.json").read_text())
JOBS = json.loads((HERE / "jobs.json").read_text())
TOOL_SPECS = MANIFEST["tool_specs"]
PATH_PARAMS = ("page_id", "keyword_id")

RESULTS: list[tuple[str, bool, str]] = []


def expect(label: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((label, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}  {detail}")


# ---------------------------------------------------------------------------
# Direct-mode tool client (mirrors mcp_manager/orchestrator direct fallback)
# ---------------------------------------------------------------------------

def call_tool(tool_name: str, args: dict | None = None) -> dict:
    args = dict(args or {})
    spec = TOOL_SPECS[tool_name]
    path = spec["path"]
    remaining = dict(args)
    for key in list(remaining):
        token = "{" + key + "}"
        if token in path:
            path = path.replace(token, str(remaining.pop(key)))
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        if spec["method"] == "GET":
            resp = client.get(path, params=remaining or None)
        else:
            resp = client.request(spec["method"], path, json=remaining)
    if resp.status_code >= 400:
        try:
            detail = resp.json()
        except ValueError:
            detail = resp.text
        return {"error": detail, "status_code": resp.status_code}
    return resp.json()


def call(tool_name: str, args: dict | None = None) -> dict:
    return call_tool(tool_name, args)


def admin_reset() -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        resp = client.post("/admin/reset")
        resp.raise_for_status()
        return resp.json()


def landing_pages() -> list[dict]:
    pages = call("read_list_pages", {"page_type": "landing"})["pages"]
    return sorted(pages, key=lambda p: p["id"])


def brief_keyword() -> dict:
    return CHECKS.find_keyword(call, CHECKS.BRIEF_KEYWORD)


# ---------------------------------------------------------------------------
# Deterministic workers (the same steps the engine executors perform)
# ---------------------------------------------------------------------------

def worker_audit() -> None:
    findings = []
    for page in landing_pages():
        audit = call("read_get_page_audit", {"page_id": page["id"]})
        findings.append({"page_id": page["id"], "issues": audit["issues"]})
    call("write_save_audit_report", {
        "scope": CHECKS.AUDIT_SCOPE, "findings": findings, "author": "worker"})


def worker_brief() -> None:
    kw = brief_keyword()
    detail = call("read_get_keyword", {"keyword_id": kw["id"]})
    angles = detail["competitor_angles"]
    pages = call("read_list_pages", {})["pages"]
    target = next(p for p in pages if p["url"] == "/trail-running-shoes")
    outline = [
        f"Search intent, audience and SERP summary for '{CHECKS.BRIEF_KEYWORD}'",
        f"Angle: {angles[0]}",
        f"Angle: {angles[1]}",
        f"Angle: {angles[2]}",
        "Internal linking plan and call to action",
    ]
    call("write_save_content_brief", {
        "keyword_id": kw["id"],
        "title": f"Content brief: {CHECKS.BRIEF_KEYWORD}",
        "intent": kw["intent"], "outline": outline,
        "angles_used": angles[:3], "target_page_id": target["id"],
        "author": "worker"})
    call("write_update_keyword_target", {
        "keyword_id": kw["id"], "target_page_id": target["id"],
        "author": "worker"})


def worker_link_plan() -> None:
    pages = call("read_list_pages", {})["pages"]
    by_id = {p["id"]: p for p in pages}
    home = next(p for p in pages if p["url"] == "/")
    orphans = sorted(CHECKS.compute_orphans(call))
    links = [{"from_page_id": home["id"], "to_page_id": oid,
              "anchor": by_id[oid]["h1"] or by_id[oid]["title"]}
             for oid in orphans]
    call("write_save_link_plan", {"links": links, "author": "worker"})


# ---------------------------------------------------------------------------
# Phase 1 — exercise every tool
# ---------------------------------------------------------------------------

def phase1() -> None:
    print("\n== Phase 1: exercise every tool (direct mode) ==")
    out = admin_reset()
    expect("reset reseeds dataset",
           out == {"reset": True, "pages": 10, "keywords": 8, "links": 12},
           str(out))

    pages = call("read_list_pages", {})
    expect("read_list_pages: 10 pages", pages.get("count") == 10,
           f"count={pages.get('count')}")
    landing = landing_pages()
    expect("read_list_pages(landing): 5 landing pages", len(landing) == 5,
           f"landing={[p['url'] for p in landing]}")

    shoes = next(p for p in pages["pages"] if p["url"] == "/trail-running-shoes")
    audit = call("read_get_page_audit", {"page_id": shoes["id"]})
    expect("read_get_page_audit: /trail-running-shoes -> [missing_meta]",
           audit.get("issues") == ["missing_meta"], f"issues={audit.get('issues')}")
    sale = next(p for p in pages["pages"] if p["url"] == "/sale")
    audit = call("read_get_page_audit", {"page_id": sale["id"]})
    expect("read_get_page_audit: /sale -> [missing_meta, missing_h1, thin_content]",
           audit.get("issues") == ["missing_meta", "missing_h1", "thin_content"],
           f"issues={audit.get('issues')}")
    ghost = call("read_get_page_audit", {"page_id": 99999})
    expect("read_get_page_audit 404s on unknown page",
           ghost.get("status_code") == 404, f"status={ghost.get('status_code')}")

    kws = call("read_list_keywords", {})
    expect("read_list_keywords: 8 keywords", kws.get("count") == 8,
           f"count={kws.get('count')}")
    kw = brief_keyword()
    expect("brief keyword tracked, not ranking, no target yet",
           kw is not None and kw["current_rank"] is None
           and kw["target_page_id"] is None,
           f"rank={kw and kw['current_rank']} target={kw and kw['target_page_id']}")
    detail = call("read_get_keyword", {"keyword_id": kw["id"]})
    expect("read_get_keyword: 4 seeded competitor angles, no briefs yet",
           len(detail.get("competitor_angles", [])) == 4
           and detail.get("briefs") == [],
           f"angles={len(detail.get('competitor_angles', []))}")

    links = call("read_list_links", {})
    expect("read_list_links: 12 existing links", links.get("count") == 12,
           f"count={links.get('count')}")
    orphans = sorted(CHECKS.compute_orphans(call))
    orphan_urls = sorted(next(p["url"] for p in pages["pages"] if p["id"] == oid)
                         for oid in orphans)
    expect("computed orphan set is exactly the 2 planted orphans",
           orphan_urls == ["/trail-shoes-vs-boots", "/winter-layering-guide"],
           f"orphans={orphan_urls}")

    worker_audit()
    reports = call("read_list_audit_reports", {})
    expect("write_save_audit_report + read_list_audit_reports: 1 report",
           reports.get("count") == 1
           and len(reports["reports"][0]["findings"]) == 5,
           f"count={reports.get('count')}")
    bad = call("write_save_audit_report", {
        "scope": "landing_pages", "author": "verify",
        "findings": [{"page_id": 99999, "issues": []}]})
    expect("write_save_audit_report 404s on unknown page in findings",
           bad.get("status_code") == 404, f"status={bad.get('status_code')}")
    admin_reset()  # drop the phase-1 report; phase 2 starts clean

    worker_brief()
    detail = call("read_get_keyword", {"keyword_id": kw["id"]})
    expect("write_save_content_brief: brief stored on the keyword",
           len(detail.get("briefs", [])) == 1,
           f"briefs={len(detail.get('briefs', []))}")
    expect("write_update_keyword_target: keyword now targets the shoes page",
           detail.get("target_page_id") is not None
           and detail["target_page"]["url"] == "/trail-running-shoes",
           f"target={detail.get('target_page')}")

    worker_link_plan()
    plans = call("read_list_link_plans", {})
    expect("write_save_link_plan + read_list_link_plans: 1 plan, 2 links",
           plans.get("count") == 1 and len(plans["plans"][0]["links"]) == 2,
           f"count={plans.get('count')}")
    expect("saving a plan does NOT change the site's link graph",
           call("read_list_links", {}).get("count") == 12,
           f"links={call('read_list_links', {}).get('count')}")


# ---------------------------------------------------------------------------
# Phase 2 — run the jobs pack end-to-end
# ---------------------------------------------------------------------------

def phase2() -> None:
    print("\n== Phase 2: jobs pack end-to-end (direct mode) ==")
    admin_reset()
    templates = {t["key"]: t for t in JOBS["templates"]}

    t = templates["audit_top_pages"]
    worker_audit()
    findings = CHECKS.check_audit_top_pages(call, t["acceptance_criteria"])
    expect(f"JOB audit_top_pages (₡{t['budget_credits']}): checks pass",
           all(f["passed"] for f in findings),
           "; ".join(f["detail"] for f in findings))

    t = templates["content_brief"]
    worker_brief()
    findings = CHECKS.check_content_brief(call, t["acceptance_criteria"])
    expect(f"JOB content_brief (₡{t['budget_credits']}): checks pass",
           all(f["passed"] for f in findings),
           "; ".join(f["detail"] for f in findings))

    t = templates["internal_link_plan"]
    worker_link_plan()
    findings = CHECKS.check_internal_link_plan(call, t["acceptance_criteria"])
    expect(f"JOB internal_link_plan (₡{t['budget_credits']}): checks pass",
           all(f["passed"] for f in findings),
           "; ".join(f["detail"] for f in findings))

    # Negative control: a fresh report with WRONG findings for one page
    # becomes the latest report — the audit check must now FAIL, proving
    # the check compares against recomputation, not the worker's word.
    findings = [{"page_id": p["id"], "issues": []} for p in landing_pages()]
    call("write_save_audit_report", {
        "scope": CHECKS.AUDIT_SCOPE, "findings": findings, "author": "verify"})
    t = templates["audit_top_pages"]
    findings = CHECKS.check_audit_top_pages(call, t["acceptance_criteria"])
    expect("NEGATIVE CONTROL: emptied findings make the audit check fail",
           not all(f["passed"] for f in findings),
           "; ".join(f["detail"] for f in findings))
    admin_reset()


# ---------------------------------------------------------------------------
# Phase 3 — MCP over stdio
# ---------------------------------------------------------------------------

async def _stdio_probe() -> tuple[list[str], dict, dict]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["SEO_URL"] = BASE_URL
    params = StdioServerParameters(
        command=sys.executable, args=[str(HERE / "mcp_server.py")], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            r1 = await session.call_tool("read_list_pages", {})
            r2 = await session.call_tool("read_list_keywords", {})
            def parse(r):
                return json.loads(r.content[0].text)
            return names, parse(r1), parse(r2)


def phase3() -> None:
    print("\n== Phase 3: MCP over stdio ==")
    names, pages, keywords = asyncio.run(_stdio_probe())
    expect("stdio list_tools: exactly the 11 allowlisted tools",
           sorted(names) == sorted(TOOL_SPECS), f"tools={sorted(names)}")
    expect("stdio read_list_pages works", pages.get("count") == 10,
           f"count={pages.get('count')}")
    expect("stdio read_list_keywords works", keywords.get("count") == 8,
           f"count={keywords.get('count')}")
    expect("no delete/admin/publish tools exposed via MCP",
           not any("delete" in n or "reset" in n or "admin" in n
                   or "publish" in n for n in names), "")


def main() -> int:
    try:
        with httpx.Client(timeout=5.0, trust_env=False) as client:
            client.get(BASE_URL + "/health").raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(f"SEODash not reachable at {BASE_URL}: {exc}")
        print("Start it first:  uvicorn app:app --port 8109")
        return 2
    phase1()
    phase2()
    phase3()
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n== SUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} assertions passed ==")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
