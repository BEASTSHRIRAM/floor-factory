"""Engineering — a deliberately ordinary repo-lite system of record.

THE FLOOR's Engineering department workplace (mirrors targets/ticketdesk).
Plain FastAPI + its own SQLite file holding engineering issues,
pull-request records and CI results. THE FLOOR never modifies this code;
agents only reach it through Synapse-shaped MCP tools.

Platform rules baked into this service:
  * Agents prepare PRs; HUMANS merge them. There is deliberately NO merge
    endpoint and NO delete endpoint — a PR record can only reach
    `approved`; what happens after approval is a human's decision, taken
    outside this system. Exposure is a safety decision.
  * CI is deterministic and service-owned: a PR's CI result is computed
    once, at PR creation, by seed.compute_ci (change summary must address
    the issue's acceptance keywords AND the PR must touch every file the
    issue lists). CI rows are immutable — answer a red PR with a new PR.

Run:   uvicorn app:app --port 8106
Seed:  python3 seed.py     (creates engineering.db with the demo dataset)
Reset: python3 reset.py    (deletes engineering.db and reseeds)
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="Engineering", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _issue_dict(row: sqlite3.Row, conn: Optional[sqlite3.Connection] = None,
                full: bool = False) -> dict:
    d = dict(row)
    d["labels"] = json.loads(d["labels"] or "[]")
    d["acceptance_keywords"] = json.loads(d["acceptance_keywords"] or "[]")
    d["files"] = json.loads(d["files"] or "[]")
    if conn is not None:
        prs = conn.execute(
            "SELECT id, status FROM pull_requests WHERE issue_id = ? ORDER BY id",
            (d["id"],),
        ).fetchall()
        d["pull_requests"] = [dict(r) for r in prs]
        if full:
            notes = conn.execute(
                "SELECT id, pr_id, author, text, created_at FROM notes"
                " WHERE issue_id = ? ORDER BY id",
                (d["id"],),
            ).fetchall()
            d["notes"] = [dict(r) for r in notes]
    return d


def _pr_dict(row: sqlite3.Row, conn: Optional[sqlite3.Connection] = None) -> dict:
    d = dict(row)
    d["files_touched"] = json.loads(d["files_touched"] or "[]")
    if conn is not None:
        ci = _ci_for(conn, d["id"])
        d["ci"] = ci
    return d


def _ci_for(conn: sqlite3.Connection, pr_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, pr_id, status, detail, created_at FROM ci_results"
        " WHERE pr_id = ? ORDER BY id DESC LIMIT 1",
        (pr_id,),
    ).fetchone()
    return dict(row) if row else None


def _get_issue_or_404(conn: sqlite3.Connection, issue_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"issue {issue_id} not found")
    return row


def _get_pr_or_404(conn: sqlite3.Connection, pr_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM pull_requests WHERE id = ?", (pr_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"pull request {pr_id} not found")
    return row


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class ClaimBody(BaseModel):
    assignee: str


class TriageBody(BaseModel):
    labels: list[str]
    priority: str


class OpenPRBody(BaseModel):
    issue_id: int
    author: str
    title: str
    change_summary: str
    files_touched: list[str] = []


class ReviewBody(BaseModel):
    reviewer: str
    note: str = ""


class NoteBody(BaseModel):
    author: str
    text: str
    pr_id: Optional[int] = None


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist for this department)
# NOTE: /issues/unlabelled-style filters ride on /issues; there is NO merge
# route and NO delete route anywhere in this service, by design.
# --------------------------------------------------------------------------

@app.get("/issues")
def list_issues(
    status: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    label: Optional[str] = Query(default=None),
    unlabelled: Optional[bool] = Query(default=None),
    assignee: Optional[str] = Query(default=None),
):
    """List issues, optionally filtered. unlabelled=true lists issues with
    no labels (the triage queue). assignee=none lists unclaimed issues."""
    sql = "SELECT * FROM issues WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if assignee is not None:
        if assignee.lower() == "none":
            sql += " AND assignee IS NULL"
        else:
            sql += " AND assignee = ?"
            params.append(assignee)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = [_issue_dict(r, conn) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    if label is not None:
        rows = [r for r in rows if label in r["labels"]]
    if unlabelled:
        rows = [r for r in rows if not r["labels"]]
    return {"issues": rows, "count": len(rows)}


@app.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    """Fetch one issue, including its notes and linked PR records."""
    conn = _conn()
    try:
        row = _get_issue_or_404(conn, issue_id)
        return _issue_dict(row, conn, full=True)
    finally:
        conn.close()


@app.post("/issues/{issue_id}/claim")
def claim_issue(issue_id: int, body: ClaimBody):
    """Claim an issue for an agent. Fails if another agent holds it."""
    conn = _conn()
    try:
        row = _get_issue_or_404(conn, issue_id)
        if row["assignee"] is not None and row["assignee"] != body.assignee:
            raise HTTPException(
                status_code=409,
                detail=f"issue {issue_id} already claimed by {row['assignee']}")
        if row["status"] == "done":
            raise HTTPException(status_code=422, detail="issue is done")
        conn.execute(
            "UPDATE issues SET assignee = ?, status = 'claimed', updated_at = ?"
            " WHERE id = ?",
            (body.assignee, seed_module._iso(_now()), issue_id),
        )
        conn.commit()
        return _issue_dict(_get_issue_or_404(conn, issue_id), conn, full=True)
    finally:
        conn.close()


@app.post("/issues/{issue_id}/triage")
def triage_issue(issue_id: int, body: TriageBody):
    """Assign labels + priority to an issue (the triage job's write)."""
    if body.priority.upper() not in seed_module.PRIORITIES:
        raise HTTPException(status_code=422, detail=f"invalid priority {body.priority}")
    if not body.labels:
        raise HTTPException(status_code=422, detail="triage requires at least one label")
    conn = _conn()
    try:
        _get_issue_or_404(conn, issue_id)
        conn.execute(
            "UPDATE issues SET labels = ?, priority = ?, updated_at = ? WHERE id = ?",
            (json.dumps(body.labels), body.priority.upper(),
             seed_module._iso(_now()), issue_id),
        )
        conn.commit()
        return _issue_dict(_get_issue_or_404(conn, issue_id), conn, full=True)
    finally:
        conn.close()


@app.post("/issues/{issue_id}/note")
def add_eng_note(issue_id: int, body: NoteBody):
    """Add an engineering note to an issue (optionally tied to a PR)."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="note text must not be empty")
    conn = _conn()
    try:
        _get_issue_or_404(conn, issue_id)
        if body.pr_id is not None:
            _get_pr_or_404(conn, body.pr_id)
        cur = conn.execute(
            "INSERT INTO notes (issue_id, pr_id, author, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (issue_id, body.pr_id, body.author, body.text,
             seed_module._iso(_now())),
        )
        conn.commit()
        note = conn.execute(
            "SELECT id, issue_id, pr_id, author, text, created_at FROM notes"
            " WHERE id = ?", (cur.lastrowid,)).fetchone()
        return {"note": dict(note),
                "issue": _issue_dict(_get_issue_or_404(conn, issue_id), conn, full=True)}
    finally:
        conn.close()


@app.get("/prs/{pr_id}")
def get_pr(pr_id: int):
    """Fetch one pull-request record, including its CI result."""
    conn = _conn()
    try:
        return _pr_dict(_get_pr_or_404(conn, pr_id), conn)
    finally:
        conn.close()


@app.get("/prs/{pr_id}/ci")
def get_ci_status(pr_id: int):
    """The recorded CI result for a PR (computed at PR creation; immutable)."""
    conn = _conn()
    try:
        _get_pr_or_404(conn, pr_id)
        ci = _ci_for(conn, pr_id)
        if ci is None:
            raise HTTPException(status_code=404, detail=f"no CI result for PR {pr_id}")
        return ci
    finally:
        conn.close()


@app.post("/prs")
def open_pr(body: OpenPRBody):
    """Open a PR record linked to a claimed issue and run CI on it.

    The issue must be claimed by the PR's author first (claim_issue).
    CI runs immediately and deterministically (seed.compute_ci) and the
    result is stored. The issue moves to status 'pr_opened'. There is no
    merge step in this service — approval is a reviewer record, merging
    is a human gate outside the system.
    """
    if not body.change_summary.strip():
        raise HTTPException(status_code=422, detail="change_summary must not be empty")
    conn = _conn()
    try:
        issue_row = _get_issue_or_404(conn, body.issue_id)
        if issue_row["assignee"] != body.author:
            holder = (f"claimed by {issue_row['assignee']!r}"
                      if issue_row["assignee"] else "unclaimed")
            raise HTTPException(
                status_code=409,
                detail=f"issue {body.issue_id} is {holder}, not "
                       f"{body.author!r} (claim it first)")
        now = seed_module._iso(_now())
        cur = conn.execute(
            """INSERT INTO pull_requests
               (issue_id, title, author, change_summary, files_touched, status,
                reviewer, reviewer_note, created_at, updated_at)
               VALUES (?,?,?,?,?, 'open', NULL, NULL, ?, ?)""",
            (body.issue_id, body.title, body.author, body.change_summary,
             json.dumps(body.files_touched), now, now),
        )
        pr_id = cur.lastrowid
        issue = {k: issue_row[k] for k in issue_row.keys()}
        ci_status, ci_detail = seed_module.compute_ci(
            issue, body.change_summary, body.files_touched)
        conn.execute(
            "INSERT INTO ci_results (pr_id, status, detail, created_at)"
            " VALUES (?,?,?,?)",
            (pr_id, ci_status, ci_detail, now),
        )
        conn.execute(
            "UPDATE issues SET status = 'pr_opened', updated_at = ? WHERE id = ?",
            (now, body.issue_id),
        )
        conn.commit()
        return _pr_dict(_get_pr_or_404(conn, pr_id), conn)
    finally:
        conn.close()


@app.post("/prs/{pr_id}/request-changes")
def request_changes(pr_id: int, body: ReviewBody):
    """Reviewer-side record: send an open PR back with a note."""
    conn = _conn()
    try:
        pr = _get_pr_or_404(conn, pr_id)
        if pr["status"] != "open":
            raise HTTPException(
                status_code=409, detail=f"PR {pr_id} is {pr['status']}, not open")
        if body.reviewer == pr["author"]:
            raise HTTPException(
                status_code=422, detail="a PR's author cannot review their own PR")
        conn.execute(
            "UPDATE pull_requests SET status = 'changes_requested', reviewer = ?,"
            " reviewer_note = ?, updated_at = ? WHERE id = ?",
            (body.reviewer, body.note, seed_module._iso(_now()), pr_id),
        )
        conn.commit()
        return _pr_dict(_get_pr_or_404(conn, pr_id), conn)
    finally:
        conn.close()


@app.post("/prs/{pr_id}/approve")
def approve_pr(pr_id: int, body: ReviewBody):
    """Reviewer-side record: approve an open PR whose CI is green.

    Approval is NOT a merge. The PR record stops at 'approved'; a human
    merges outside this system (per-PR human gate, platform rule).
    """
    conn = _conn()
    try:
        pr = _get_pr_or_404(conn, pr_id)
        if pr["status"] != "open":
            raise HTTPException(
                status_code=409, detail=f"PR {pr_id} is {pr['status']}, not open")
        if body.reviewer == pr["author"]:
            raise HTTPException(
                status_code=422, detail="a PR's author cannot approve their own PR")
        ci = _ci_for(conn, pr_id)
        if ci is None or ci["status"] != "pass":
            raise HTTPException(
                status_code=422,
                detail=f"PR {pr_id} cannot be approved: CI is "
                       f"{ci['status'] if ci else 'missing'} (must be pass)")
        conn.execute(
            "UPDATE pull_requests SET status = 'approved', reviewer = ?,"
            " reviewer_note = ?, updated_at = ? WHERE id = ?",
            (body.reviewer, body.note, seed_module._iso(_now()), pr_id),
        )
        conn.commit()
        return _pr_dict(_get_pr_or_404(conn, pr_id), conn)
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
        by_status = {
            r["status"]: r["c"] for r in conn.execute(
                "SELECT status, COUNT(*) AS c FROM issues GROUP BY status").fetchall()
        }
        unlabelled = conn.execute(
            "SELECT COUNT(*) FROM issues WHERE labels = '[]'").fetchone()[0]
        unprioritised = conn.execute(
            "SELECT COUNT(*) FROM issues WHERE priority IS NULL").fetchone()[0]
        unclaimed = conn.execute(
            "SELECT COUNT(*) FROM issues WHERE assignee IS NULL"
            " AND status != 'done'").fetchone()[0]
        prs_by_status = {
            r["status"]: r["c"] for r in conn.execute(
                "SELECT status, COUNT(*) AS c FROM pull_requests"
                " GROUP BY status").fetchall()
        }
        ci = {
            r["status"]: r["c"] for r in conn.execute(
                "SELECT status, COUNT(*) AS c FROM ci_results"
                " GROUP BY status").fetchall()
        }
    finally:
        conn.close()
    return {
        "total_issues": total,
        "issues_by_status": by_status,
        "unlabelled": unlabelled,
        "unprioritised": unprioritised,
        "unclaimed": unclaimed,
        "prs_by_status": prs_by_status,
        "ci_results": ci,
    }


# --------------------------------------------------------------------------
# internal routes (NOT part of the Synapse allowlist)
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/admin/reset")
def admin_reset():
    """Restore the exact seeded demo state."""
    n = seed_module.seed(DB_PATH)
    return {"reset": True, "issues": n}
