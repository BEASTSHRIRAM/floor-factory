"""Deterministic Reviewer checks for the SEO department.

Mirrors targets/qa/checks.py: each check re-reads live SEODash state
THROUGH THE TOOL LAYER (never the DB) and returns findings — one per
acceptance criterion — as {"criterion": str, "passed": bool,
"detail": str}.

The `call` argument is any callable with the engine's shape:
    call(tool_name: str, args: dict) -> dict
and the second argument is the family's full criteria list (the SEO
adapter in orchestrator/departments.py passes family.criteria whole,
unlike QA's single-criterion shape).

Nothing here trusts the worker's saved records: the audit check
RECOMPUTES the audit rules from raw page fields and compares against
the saved report; the brief check re-derives the keyword's seeded
angles; the link-plan check recomputes the orphan set from the live
link graph. All money/review decisions downstream key off these
findings; nothing here is an LLM judgement.
"""
from __future__ import annotations

from typing import Any, Callable

CallFn = Callable[[str, dict], dict]

THIN_CONTENT_WORDS = 300
SLOW_TEMPLATE_MS = 2500
BRIEF_KEYWORD = "best trail running shoes for monsoon"
AUDIT_SCOPE = "landing_pages"


def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": passed, "detail": detail}


# ---------------------------------------------------------------------------
# Independent recomputations (from raw state, via tools only)
# ---------------------------------------------------------------------------

def recompute_issues(page: dict) -> list[str]:
    """The audit rules applied to a raw page record, in canonical
    order — the same rules app.py's audit endpoint states, derived
    here from the page's fields alone."""
    issues = []
    if not (page.get("title") or "").strip():
        issues.append("missing_title")
    if not (page.get("meta_description") or "").strip():
        issues.append("missing_meta")
    if not (page.get("h1") or "").strip():
        issues.append("missing_h1")
    if page.get("word_count", 0) < THIN_CONTENT_WORDS:
        issues.append("thin_content")
    if page.get("load_ms", 0) > SLOW_TEMPLATE_MS:
        issues.append("slow_template")
    return issues


def compute_orphans(call: CallFn) -> set[int]:
    """Non-root pages with zero inbound internal links, from the live
    link graph."""
    pages = call("read_list_pages", {})["pages"]
    links = call("read_list_links", {})["links"]
    inbound = {link["to_page_id"] for link in links}
    return {p["id"] for p in pages
            if p["url"] != "/" and p["id"] not in inbound}


def find_keyword(call: CallFn, term: str) -> dict | None:
    for kw in call("read_list_keywords", {})["keywords"]:
        if kw["term"] == term:
            return kw
    return None


# ---------------------------------------------------------------------------
# Job checks — one per job template in jobs.json
# ---------------------------------------------------------------------------

def check_audit_top_pages(call: CallFn, criteria: list[str]) -> list[dict]:
    """A saved audit report covers exactly the landing pages, and its
    per-page findings equal the audit recomputed from live page data."""
    pages = call("read_list_pages", {})["pages"]
    landing = sorted(p["id"] for p in pages if p["page_type"] == "landing")
    reports = call("read_list_audit_reports", {})["reports"]
    scoped = [r for r in reports if r["scope"] == AUDIT_SCOPE]
    report = scoped[-1] if scoped else None

    if report is None:
        return [_finding(criteria[0], False,
                         f"no audit report saved with scope {AUDIT_SCOPE!r}"),
                _finding(criteria[1], False, "no report to compare")]
    covered = sorted(f["page_id"] for f in report["findings"])
    findings = [_finding(
        criteria[0], covered == landing,
        f"report covers page ids {covered}; landing pages are {landing}")]

    by_id = {p["id"]: p for p in pages}
    mismatched = []
    for f in report["findings"]:
        page = by_id.get(f["page_id"])
        if page is None:
            mismatched.append(f["page_id"])
            continue
        if sorted(f["issues"]) != sorted(recompute_issues(page)):
            mismatched.append(f["page_id"])
    findings.append(_finding(
        criteria[1], not mismatched,
        f"pages whose saved findings disagree with recomputation: "
        f"{mismatched}"))
    return findings


def check_content_brief(call: CallFn, criteria: list[str]) -> list[dict]:
    """A brief is saved for the brief keyword, tied to it with the
    seeded intent, with >= 4 outline sections drawing on >= 2 seeded
    competitor angles (at least 2 sections referencing one verbatim)."""
    keyword = find_keyword(call, BRIEF_KEYWORD)
    if keyword is None:
        return [_finding(c, False, f"keyword {BRIEF_KEYWORD!r} not tracked")
                for c in criteria]
    detail = call("read_get_keyword", {"keyword_id": keyword["id"]})
    briefs = detail.get("briefs", [])
    brief = briefs[-1] if briefs else None
    if brief is None:
        return [_finding(criteria[0], False,
                         f"no brief saved for keyword {BRIEF_KEYWORD!r}"),
                _finding(criteria[1], False, "no brief to compare"),
                _finding(criteria[2], False, "no brief to compare")]

    findings = [_finding(
        criteria[0], brief["keyword_id"] == keyword["id"],
        f"latest brief #{brief['id']} is for keyword_id "
        f"{brief['keyword_id']} (expected {keyword['id']})")]
    findings.append(_finding(
        criteria[1],
        brief["intent"] == keyword["intent"]
        and BRIEF_KEYWORD in brief["title"],
        f"brief intent {brief['intent']!r} vs seeded {keyword['intent']!r}; "
        f"title names the keyword: {BRIEF_KEYWORD in brief['title']}"))

    seeded_angles = keyword["competitor_angles"]
    used = brief.get("angles_used", [])
    outline = brief.get("outline", [])
    referencing = [s for s in outline
                   if any(a in s for a in seeded_angles)]
    ok = (len(outline) >= 4 and len(used) >= 2
          and all(a in seeded_angles for a in used)
          and len(referencing) >= 2)
    findings.append(_finding(
        criteria[2], ok,
        f"outline sections: {len(outline)}; angles used: {len(used)} "
        f"(all seeded: {all(a in seeded_angles for a in used)}); "
        f"sections referencing a seeded angle: {len(referencing)}"))
    return findings


def check_internal_link_plan(call: CallFn, criteria: list[str]) -> list[dict]:
    """The latest saved link plan targets exactly the computed orphan
    set, references only real pages, and has no self-links."""
    orphans = compute_orphans(call)
    pages = call("read_list_pages", {})["pages"]
    page_ids = {p["id"] for p in pages}
    plans = call("read_list_link_plans", {})["plans"]
    plan = plans[-1] if plans else None
    if plan is None:
        return [_finding(criteria[0], False, "no link plan saved"),
                _finding(criteria[1], False, "no plan to validate")]

    targets = sorted({item["to_page_id"] for item in plan["links"]})
    findings = [_finding(
        criteria[0], targets == sorted(orphans),
        f"plan targets {targets}; computed orphan set is "
        f"{sorted(orphans)}")]
    invalid = [i for i in plan["links"]
               if i["from_page_id"] not in page_ids
               or i["to_page_id"] not in page_ids
               or i["from_page_id"] == i["to_page_id"]]
    findings.append(_finding(
        criteria[1], not invalid,
        f"invalid/self-referencing planned links: {invalid}"))
    return findings


CHECKS = {
    "audit_top_pages": check_audit_top_pages,
    "content_brief": check_content_brief,
    "internal_link_plan": check_internal_link_plan,
}
