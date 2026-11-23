"""TicketDesk — a deliberately ordinary internal support-ticket API.

THE FLOOR's primary target system (ARCHITECTURE §6.1). Plain FastAPI + its
own SQLite file. THE FLOOR never modifies this code; agents only reach it
through Synapse-generated MCP tools.

Run:   uvicorn app:app --port 8101
Seed:  python3 seed.py     (creates ticketdesk.db with the messy dataset)
Reset: python3 reset.py    (deletes ticketdesk.db and reseeds)
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="TicketDesk", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _ticket_dict(row: sqlite3.Row, comments: Optional[list] = None) -> dict:
    d = dict(row)
    if comments is not None:
        d["comments"] = comments
    return d


def _get_ticket_or_404(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"ticket {ticket_id} not found")
    return row


def _comments_for(conn: sqlite3.Connection, ticket_id: int) -> list:
    rows = conn.execute(
        "SELECT id, author, kind, text, created_at FROM comments"
        " WHERE ticket_id = ? ORDER BY id",
        (ticket_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _normalize_subject(subject: str) -> str:
    s = subject.lower().strip()
    s = re.sub(r"^(re|fwd|fw)\s*:\s*", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class TicketCreate(BaseModel):
    subject: str
    body: str = ""
    customer: str = ""
    category: str = "general"
    priority: str = "P3"
    assignee: Optional[str] = None


class AssignBody(BaseModel):
    assignee: Optional[str] = None


class PriorityBody(BaseModel):
    priority: str


class CommentBody(BaseModel):
    author: str = "support"
    text: str
    kind: str = "comment"  # comment | escalation | resolution


class StatusBody(BaseModel):
    status: str


class MergeBody(BaseModel):
    source_id: int
    target_id: int


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist — ARCHITECTURE §6.1)
# --------------------------------------------------------------------------

@app.get("/tickets")
def list_tickets(
    status: Optional[str] = Query(default=None),
    assignee: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
):
    """List tickets, optionally filtered. assignee=none lists unassigned."""
    sql = "SELECT * FROM tickets WHERE merged_into IS NULL"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if assignee is not None:
        if assignee.lower() == "none":
            sql += " AND assignee IS NULL"
        else:
            sql += " AND assignee = ?"
            params.append(assignee)
    if priority:
        sql += " AND priority = ?"
        params.append(priority)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"tickets": [_ticket_dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/tickets/duplicates")
def find_duplicates():
    """Group live tickets that look like duplicates of each other."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE merged_into IS NULL AND status != 'closed'"
            " ORDER BY id"
        ).fetchall()
        groups: dict[str, list] = {}
        for r in rows:
            groups.setdefault(_normalize_subject(r["subject"]), []).append(dict(r))
        dupes = [
            {"subject_normalized": key, "ticket_ids": [t["id"] for t in members],
             "tickets": members}
            for key, members in groups.items() if len(members) > 1
        ]
        return {"groups": dupes, "group_count": len(dupes)}
    finally:
        conn.close()


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int):
    """Fetch one ticket, including its comments."""
    conn = _conn()
    try:
        row = _get_ticket_or_404(conn, ticket_id)
        return _ticket_dict(row, comments=_comments_for(conn, ticket_id))
    finally:
        conn.close()


@app.post("/tickets")
def create_ticket(body: TicketCreate):
    """Create a new ticket."""
    from datetime import timedelta

    now = _now()
    sla_hours = seed_module.SLA_HOURS.get(body.priority.upper(), 72)
    sla_due = now + timedelta(hours=sla_hours)
    conn = _conn()
    try:
        cur = conn.execute(
            """INSERT INTO tickets
               (subject, body, customer, category, priority, status, assignee,
                created_at, updated_at, resolved_at, sla_due_at, merged_into)
               VALUES (?,?,?,?,?,?,?, ?, ?, NULL, ?, NULL)""",
            (body.subject, body.body, body.customer, body.category,
             body.priority.upper(), "new", body.assignee,
             seed_module._iso(now), seed_module._iso(now), seed_module._iso(sla_due)),
        )
        conn.commit()
        row = _get_ticket_or_404(conn, cur.lastrowid)
        return _ticket_dict(row, comments=[])
    finally:
        conn.close()


@app.post("/tickets/{ticket_id}/assign")
def assign_ticket(ticket_id: int, body: AssignBody):
    """Assign a ticket to a support agent (or unassign with null)."""
    conn = _conn()
    try:
        _get_ticket_or_404(conn, ticket_id)
        conn.execute(
            "UPDATE tickets SET assignee = ?, updated_at = ? WHERE id = ?",
            (body.assignee, seed_module._iso(_now()), ticket_id),
        )
        conn.commit()
        return _ticket_dict(_get_ticket_or_404(conn, ticket_id),
                            comments=_comments_for(conn, ticket_id))
    finally:
        conn.close()


@app.post("/tickets/{ticket_id}/priority")
def set_priority(ticket_id: int, body: PriorityBody):
    """Change a ticket's priority (P1-P4)."""
    priority = body.priority.upper()
    if priority not in seed_module.SLA_HOURS:
        raise HTTPException(status_code=422, detail=f"invalid priority {body.priority}")
    conn = _conn()
    try:
        _get_ticket_or_404(conn, ticket_id)
        conn.execute(
            "UPDATE tickets SET priority = ?, updated_at = ? WHERE id = ?",
            (priority, seed_module._iso(_now()), ticket_id),
        )
        conn.commit()
        return _ticket_dict(_get_ticket_or_404(conn, ticket_id),
                            comments=_comments_for(conn, ticket_id))
    finally:
        conn.close()


@app.post("/tickets/{ticket_id}/comment")
def add_comment(ticket_id: int, body: CommentBody):
    """Add a comment to a ticket (kind: comment | escalation | resolution)."""
    if body.kind not in ("comment", "escalation", "resolution"):
        raise HTTPException(status_code=422, detail=f"invalid comment kind {body.kind}")
    conn = _conn()
    try:
        _get_ticket_or_404(conn, ticket_id)
        cur = conn.execute(
            "INSERT INTO comments (ticket_id, author, kind, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (ticket_id, body.author, body.kind, body.text, seed_module._iso(_now())),
        )
        conn.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (seed_module._iso(_now()), ticket_id),
        )
        conn.commit()
        comment = conn.execute(
            "SELECT id, author, kind, text, created_at FROM comments WHERE id = ?",
            (cur.lastrowid,),
        ).fetchone()
        return {"comment": dict(comment),
                "ticket": _ticket_dict(_get_ticket_or_404(conn, ticket_id))}
    finally:
        conn.close()


@app.post("/tickets/{ticket_id}/status")
def set_status(ticket_id: int, body: StatusBody):
    """Change a ticket's status (new|open|in_progress|resolved|closed)."""
    valid = {"new", "open", "in_progress", "resolved", "closed"}
    if body.status not in valid:
        raise HTTPException(status_code=422, detail=f"invalid status {body.status}")
    conn = _conn()
    try:
        _get_ticket_or_404(conn, ticket_id)
        now = seed_module._iso(_now())
        if body.status == "resolved":
            conn.execute(
                "UPDATE tickets SET status = ?, resolved_at = ?, updated_at = ?"
                " WHERE id = ?",
                (body.status, now, now, ticket_id),
            )
        elif body.status in ("new", "open", "in_progress"):
            conn.execute(
                "UPDATE tickets SET status = ?, resolved_at = NULL, updated_at = ?"
                " WHERE id = ?",
                (body.status, now, ticket_id),
            )
        else:
            conn.execute(
                "UPDATE tickets SET status = ?, updated_at = ? WHERE id = ?",
                (body.status, now, ticket_id),
            )
        conn.commit()
        return _ticket_dict(_get_ticket_or_404(conn, ticket_id),
                            comments=_comments_for(conn, ticket_id))
    finally:
        conn.close()


@app.post("/tickets/merge")
def merge_tickets(body: MergeBody):
    """Merge a duplicate ticket into a canonical one (source is closed)."""
    if body.source_id == body.target_id:
        raise HTTPException(status_code=422, detail="source and target must differ")
    conn = _conn()
    try:
        _get_ticket_or_404(conn, body.source_id)
        _get_ticket_or_404(conn, body.target_id)
        now = seed_module._iso(_now())
        conn.execute(
            "UPDATE tickets SET status = 'closed', merged_into = ?, updated_at = ?"
            " WHERE id = ?",
            (body.target_id, now, body.source_id),
        )
        conn.execute(
            "INSERT INTO comments (ticket_id, author, kind, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (body.target_id, "ticketdesk", "comment",
             f"Merged duplicate ticket #{body.source_id} into this ticket.", now),
        )
        conn.execute(
            "INSERT INTO comments (ticket_id, author, kind, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (body.source_id, "ticketdesk", "comment",
             f"Closed as duplicate of ticket #{body.target_id}.", now),
        )
        conn.commit()
        return {"merged": body.source_id, "into": body.target_id,
                "target": _ticket_dict(_get_ticket_or_404(conn, body.target_id),
                                       comments=_comments_for(conn, body.target_id))}
    finally:
        conn.close()


@app.get("/sla/breaches")
def sla_breaches():
    """Tickets past their SLA deadline and not resolved/closed."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE merged_into IS NULL"
            " AND status NOT IN ('resolved', 'closed') AND sla_due_at IS NOT NULL"
            " ORDER BY id"
        ).fetchall()
        now = _now()
        breached = []
        for r in rows:
            due = _parse(r["sla_due_at"])
            if due and due < now:
                d = dict(r)
                d["hours_overdue"] = round((now - due).total_seconds() / 3600, 1)
                breached.append(d)
        return {"breaches": breached, "count": len(breached)}
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    conn = _conn()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE merged_into IS NULL").fetchone()[0]
        by_status = {
            r["status"]: r["c"] for r in conn.execute(
                "SELECT status, COUNT(*) AS c FROM tickets"
                " WHERE merged_into IS NULL GROUP BY status").fetchall()
        }
        unassigned = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE merged_into IS NULL"
            " AND assignee IS NULL AND status != 'closed'").fetchone()[0]
        categories = [r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM tickets WHERE merged_into IS NULL"
            " ORDER BY category").fetchall()]
        merged = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE merged_into IS NOT NULL").fetchone()[0]
    finally:
        conn.close()
    breaches = sla_breaches()
    dupes = find_duplicates()
    return {
        "total_tickets": total,
        "by_status": by_status,
        "unassigned": unassigned,
        "sla_breaches": breaches["count"],
        "duplicate_groups": dupes["group_count"],
        "merged_tickets": merged,
        "categories": categories,
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
    return {"reset": True, "tickets": n}
