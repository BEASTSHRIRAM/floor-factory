"""ExtDesk — a SIMULATED external issue system (a customer's "Jira").

This is NOT Jira. It is a small, self-contained stand-in — its own
FastAPI app and its own SQLite file — that exists so THE FLOOR's
connections layer and intake/bug loop can be exercised end-to-end
against a genuinely separate system, with no external account. Every
surface labels it a simulator; the floor reaches it only through the
`localdesk` connection provider (orchestrator/connections.py), the
same provider interface a real Composio connection will use later.

Run:   uvicorn app:app --port 8108
Seed:  python3 seed.py     (creates extdesk.db with the seeded issues)
Reset: python3 reset.py    (deletes extdesk.db and reseeds)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="ExtDesk (SIMULATOR — not Jira)", version="1.0.0")

STATUSES = ("Open", "In Progress", "Done")
SEVERITIES = ("critical", "high", "medium", "low")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _issue_or_404(conn: sqlite3.Connection, issue_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM issues WHERE id = ?",
                       (issue_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404,
                            detail=f"issue {issue_id} not found")
    return row


def _issue_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["comments"] = [dict(r) for r in conn.execute(
        "SELECT id, author, body, created_at FROM comments"
        " WHERE issue_id = ? ORDER BY id", (row["id"],)).fetchall()]
    return d


class IssueCreate(BaseModel):
    title: str
    body: str = ""
    severity: str = "medium"
    source: str = "api"


class TransitionBody(BaseModel):
    status: str
    comment: Optional[str] = None
    author: str = "floor"


class CommentBody(BaseModel):
    author: str = "floor"
    body: str


@app.get("/health")
def health():
    return {"status": "ok", "system": "extdesk-simulator"}


@app.get("/issues")
def list_issues(status: Optional[str] = None):
    conn = _conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM issues WHERE status = ? ORDER BY id",
                (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM issues ORDER BY id").fetchall()
        return {"issues": [_issue_dict(conn, r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    conn = _conn()
    try:
        return _issue_dict(conn, _issue_or_404(conn, issue_id))
    finally:
        conn.close()


@app.post("/issues")
def create_issue(body: IssueCreate):
    if body.severity not in SEVERITIES:
        raise HTTPException(status_code=422,
                            detail=f"invalid severity {body.severity!r}")
    now = _now_iso()
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO issues (title, body, severity, status, source,
                   created_at, updated_at)
               VALUES (?,?,?, 'Open', ?, ?, ?)""",
            (body.title, body.body, body.severity, body.source, now, now))
        conn.commit()
        return _issue_dict(conn, _issue_or_404(conn, int(cur.lastrowid)))
    finally:
        conn.close()


@app.post("/issues/{issue_id}/transition")
def transition_issue(issue_id: int, body: TransitionBody):
    if body.status not in STATUSES:
        raise HTTPException(status_code=422,
                            detail=f"invalid status {body.status!r} "
                                   f"(one of {', '.join(STATUSES)})")
    conn = _conn()
    try:
        _issue_or_404(conn, issue_id)
        conn.execute("UPDATE issues SET status = ?, updated_at = ?"
                     " WHERE id = ?", (body.status, _now_iso(), issue_id))
        if body.comment:
            conn.execute(
                "INSERT INTO comments (issue_id, author, body, created_at)"
                " VALUES (?,?,?,?)",
                (issue_id, body.author, body.comment, _now_iso()))
        conn.commit()
        return _issue_dict(conn, _issue_or_404(conn, issue_id))
    finally:
        conn.close()


@app.post("/issues/{issue_id}/comments")
def add_comment(issue_id: int, body: CommentBody):
    conn = _conn()
    try:
        _issue_or_404(conn, issue_id)
        conn.execute(
            "INSERT INTO comments (issue_id, author, body, created_at)"
            " VALUES (?,?,?,?)",
            (issue_id, body.author, body.body, _now_iso()))
        conn.execute("UPDATE issues SET updated_at = ? WHERE id = ?",
                     (_now_iso(), issue_id))
        conn.commit()
        return _issue_dict(conn, _issue_or_404(conn, issue_id))
    finally:
        conn.close()


@app.post("/admin/reset")
def admin_reset():
    """Restore the exact seeded simulator state."""
    n = seed_module.seed(DB_PATH)
    return {"reset": True, "issues": n, "simulator": True}
