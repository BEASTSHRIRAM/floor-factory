"""SEODash — a deliberately ordinary internal SEO console for one site.

THE FLOOR's SEO department workplace (department id "seo"). Plain
FastAPI + its own SQLite file, mirroring QADesk's shape exactly. THE
FLOOR never modifies this code; agents only reach it through
Synapse-generated MCP tools.

The surface is ANALYSIS AND DRAFTS ONLY: audits, content briefs,
keyword targets and link PLANS are stored as records. There is no tool
that publishes anything or mutates a live website — the seeded site
below is the whole universe, and even it only changes through the
record-keeping writes above.

Run:   uvicorn app:app --port 8109
Seed:  python3 seed.py     (creates seo.db with the seeded site)
Reset: python3 reset.py    (deletes seo.db and reseeds)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="SEODash", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_page_or_404(conn: sqlite3.Connection, page_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"page {page_id} not found")
    return row


def _get_keyword_or_404(conn: sqlite3.Connection, keyword_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM keywords WHERE id = ?",
                       (keyword_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404,
                            detail=f"keyword {keyword_id} not found")
    return row


def page_issues(page: sqlite3.Row) -> list[str]:
    """The deterministic audit rules, in canonical order. checks.py
    recomputes these independently from raw page fields; the two must
    never disagree (the audit job's check is exactly that comparison)."""
    issues = []
    if not (page["title"] or "").strip():
        issues.append("missing_title")
    if not (page["meta_description"] or "").strip():
        issues.append("missing_meta")
    if not (page["h1"] or "").strip():
        issues.append("missing_h1")
    if page["word_count"] < seed_module.THIN_CONTENT_WORDS:
        issues.append("thin_content")
    if page["load_ms"] > seed_module.SLOW_TEMPLATE_MS:
        issues.append("slow_template")
    return issues


def _page_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["inbound_link_count"] = conn.execute(
        "SELECT COUNT(*) FROM page_links WHERE to_page_id = ?",
        (row["id"],)).fetchone()[0]
    return d


def _keyword_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["competitor_angles"] = [r["angle"] for r in conn.execute(
        "SELECT angle FROM keyword_angles WHERE keyword_id = ? ORDER BY id",
        (row["id"],)).fetchall()]
    target = None
    if row["target_page_id"] is not None:
        t = conn.execute("SELECT id, url FROM pages WHERE id = ?",
                         (row["target_page_id"],)).fetchone()
        if t is not None:
            target = dict(t)
    d["target_page"] = target
    return d


def _report_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["findings"] = json.loads(d.pop("findings_json"))
    return d


def _brief_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["outline"] = json.loads(d.pop("outline_json"))
    d["angles_used"] = json.loads(d.pop("angles_json"))
    return d


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class AuditReportBody(BaseModel):
    scope: str
    findings: list[dict]          # [{"page_id": int, "issues": [str]}]
    author: str = "seo"


class BriefBody(BaseModel):
    keyword_id: int
    title: str
    intent: str
    outline: list[str]
    angles_used: list[str] = []
    target_page_id: Optional[int] = None
    author: str = "seo"


class KeywordTargetBody(BaseModel):
    target_page_id: Optional[int] = None
    author: str = "seo"


class LinkPlanBody(BaseModel):
    links: list[dict]             # [{"from_page_id": int, "to_page_id": int, "anchor": str}]
    author: str = "seo"


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist — exactly 11 tools)
# --------------------------------------------------------------------------

@app.get("/pages")
def list_pages(page_type: Optional[str] = Query(default=None)):
    """List the site's pages with their on-page fields and inbound
    internal-link counts, optionally filtered by page_type."""
    sql = "SELECT * FROM pages WHERE 1=1"
    params: list = []
    if page_type:
        sql += " AND page_type = ?"
        params.append(page_type)
    sql += " ORDER BY traffic DESC, id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"pages": [_page_dict(conn, r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/pages/{page_id}/audit")
def get_page_audit(page_id: int):
    """Deterministic on-page audit of one page: the raw fields plus the
    issues the audit rules derive from them (missing title/meta/H1,
    thin content, slow template)."""
    conn = _conn()
    try:
        row = _get_page_or_404(conn, page_id)
        d = _page_dict(conn, row)
        d["issues"] = page_issues(row)
        d["rules"] = {"thin_content_words": seed_module.THIN_CONTENT_WORDS,
                      "slow_template_ms": seed_module.SLOW_TEMPLATE_MS}
        return d
    finally:
        conn.close()


@app.get("/keywords")
def list_keywords():
    """List tracked keywords: term, search volume, difficulty, current
    rank (null = not ranking), intent, target page and the seeded
    competitor angles for each."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM keywords ORDER BY volume DESC").fetchall()
        return {"keywords": [_keyword_dict(conn, r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/keywords/{keyword_id}")
def get_keyword(keyword_id: int):
    """Fetch one keyword with its competitor angles, its target page,
    and every content brief saved for it (newest last)."""
    conn = _conn()
    try:
        row = _get_keyword_or_404(conn, keyword_id)
        d = _keyword_dict(conn, row)
        d["briefs"] = [_brief_dict(r) for r in conn.execute(
            "SELECT * FROM briefs WHERE keyword_id = ? ORDER BY id",
            (keyword_id,)).fetchall()]
        return d
    finally:
        conn.close()


@app.get("/links")
def list_links():
    """List the site's existing internal links (from/to page + anchor)."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT l.*, pf.url AS from_url, pt.url AS to_url"
            " FROM page_links l"
            " JOIN pages pf ON pf.id = l.from_page_id"
            " JOIN pages pt ON pt.id = l.to_page_id ORDER BY l.id").fetchall()
        return {"links": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/audit-reports")
def list_audit_reports():
    """List saved audit reports (newest last), findings included."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM audit_reports ORDER BY id").fetchall()
        return {"reports": [_report_dict(r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/link-plans")
def list_link_plans():
    """List saved internal-link plans with their planned links."""
    conn = _conn()
    try:
        plans = []
        for row in conn.execute("SELECT * FROM link_plans ORDER BY id").fetchall():
            d = dict(row)
            d["links"] = [dict(r) for r in conn.execute(
                "SELECT * FROM link_plan_items WHERE plan_id = ? ORDER BY id",
                (row["id"],)).fetchall()]
            plans.append(d)
        return {"plans": plans, "count": len(plans)}
    finally:
        conn.close()


@app.post("/audit-reports")
def save_audit_report(body: AuditReportBody):
    """Save an audit report: a scope plus per-page issue lists. Every
    referenced page must exist. Reports are records — saving one never
    changes a page."""
    conn = _conn()
    try:
        for f in body.findings:
            _get_page_or_404(conn, int(f["page_id"]))
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO audit_reports (scope, author, findings_json,"
            " created_at) VALUES (?,?,?,?)",
            (body.scope, body.author, json.dumps(body.findings), now))
        conn.commit()
        row = conn.execute("SELECT * FROM audit_reports WHERE id = ?",
                           (cur.lastrowid,)).fetchone()
        return {"report": _report_dict(row)}
    finally:
        conn.close()


@app.post("/briefs")
def save_content_brief(body: BriefBody):
    """Save a content brief for a keyword: title, intent, outline
    sections and the competitor angles it draws from. A draft record —
    nothing is published."""
    conn = _conn()
    try:
        _get_keyword_or_404(conn, body.keyword_id)
        if body.target_page_id is not None:
            _get_page_or_404(conn, body.target_page_id)
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO briefs (keyword_id, title, intent, outline_json,"
            " angles_json, target_page_id, author, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (body.keyword_id, body.title, body.intent,
             json.dumps(body.outline), json.dumps(body.angles_used),
             body.target_page_id, body.author, now))
        conn.commit()
        row = conn.execute("SELECT * FROM briefs WHERE id = ?",
                           (cur.lastrowid,)).fetchone()
        return {"brief": _brief_dict(row)}
    finally:
        conn.close()


@app.post("/keywords/{keyword_id}/target")
def update_keyword_target(keyword_id: int, body: KeywordTargetBody):
    """Point a keyword at a target page (or clear the target with
    null). A planning record only — no page changes."""
    conn = _conn()
    try:
        _get_keyword_or_404(conn, keyword_id)
        if body.target_page_id is not None:
            _get_page_or_404(conn, body.target_page_id)
        conn.execute("UPDATE keywords SET target_page_id = ? WHERE id = ?",
                     (body.target_page_id, keyword_id))
        conn.commit()
        return {"keyword": _keyword_dict(
            conn, _get_keyword_or_404(conn, keyword_id))}
    finally:
        conn.close()


@app.post("/link-plans")
def save_link_plan(body: LinkPlanBody):
    """Save an internal-link fix plan: planned links between existing
    pages. The plan is a record — the site's actual link graph does
    NOT change (applying a plan is a human publishing decision)."""
    conn = _conn()
    try:
        for link in body.links:
            _get_page_or_404(conn, int(link["from_page_id"]))
            _get_page_or_404(conn, int(link["to_page_id"]))
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO link_plans (author, created_at) VALUES (?,?)",
            (body.author, now))
        plan_id = cur.lastrowid
        for link in body.links:
            conn.execute(
                "INSERT INTO link_plan_items (plan_id, from_page_id,"
                " to_page_id, anchor) VALUES (?,?,?,?)",
                (plan_id, int(link["from_page_id"]), int(link["to_page_id"]),
                 str(link.get("anchor", ""))))
        conn.commit()
        row = conn.execute("SELECT * FROM link_plans WHERE id = ?",
                           (plan_id,)).fetchone()
        d = dict(row)
        d["links"] = [dict(r) for r in conn.execute(
            "SELECT * FROM link_plan_items WHERE plan_id = ? ORDER BY id",
            (plan_id,)).fetchall()]
        return {"plan": d}
    finally:
        conn.close()


# --------------------------------------------------------------------------
# internal routes (NOT part of the Synapse allowlist)
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/admin/reset")
def admin_reset():
    """Restore the exact seeded demo state."""
    out = seed_module.seed(DB_PATH)
    return {"reset": True, "pages": out["pages"],
            "keywords": out["keywords"], "links": out["links"]}
