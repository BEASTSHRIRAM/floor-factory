"""SDR workplace — a CRM-lite system of record for THE FLOOR's SDR dept.

The department's workplace (company blueprint: department = one
Synapse-onboarded system + one Manager + scoped roster). Plain FastAPI +
its own SQLite file, exactly like TicketDesk. THE FLOOR never modifies
this code; agents only reach it through the department's MCP tools.

DRAFTS ONLY — platform rule: this API has NO send endpoint and the tool
surface built on it has NO send tool. Outreach leaves this system only
when a human promotes a draft outside the agent tool surface. Sending
is a human-gated promotion, never an agent action.

Run:   uvicorn app:app --port 8105
Seed:  python3 seed.py     (creates sdr.db with the demo dataset)
Reset: python3 reset.py    (deletes sdr.db and reseeds)
"""
from __future__ import annotations

import json
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module
from rubric import QUALIFY_THRESHOLD

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="SDR Workplace (CRM-lite)", version="1.0.0")

STAGES = {"new", "researching", "drafted", "qualified"}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _account_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["tech_signals"] = json.loads(d.get("tech_signals") or "[]")
    return d


def _lead_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    raw = d.get("score_reasons")
    d["score_reasons"] = json.loads(raw) if raw else None
    d["has_draft"] = bool(d.get("draft_body"))
    return d


def _get_account_or_404(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"account {account_id} not found")
    return row


def _get_lead_or_404(conn: sqlite3.Connection, lead_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"lead {lead_id} not found")
    return row


def _notes_for(conn: sqlite3.Connection, target_type: str, target_id: int) -> list:
    rows = conn.execute(
        "SELECT id, target_type, target_id, author, text, created_at FROM crm_notes"
        " WHERE target_type = ? AND target_id = ? ORDER BY id",
        (target_type, target_id),
    ).fetchall()
    return [dict(r) for r in rows]


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class ScoreBody(BaseModel):
    score: int
    reasons: list[str]


class DraftBody(BaseModel):
    subject: str
    body: str


class NoteBody(BaseModel):
    target_type: str  # lead | account
    target_id: int
    author: str = "sdr-agent"
    text: str


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist for the SDR department)
# NOTE: /accounts/{id}/research is declared BEFORE /accounts/{id} is not
# required (distinct path shape), but keep research grouped with reads.
# There is deliberately NO send endpoint anywhere in this file.
# --------------------------------------------------------------------------

@app.get("/accounts")
def list_accounts(
    industry: Optional[str] = Query(default=None),
    min_size: Optional[int] = Query(default=None),
    max_size: Optional[int] = Query(default=None),
):
    """List accounts, optionally filtered by industry / size band."""
    sql = "SELECT * FROM accounts WHERE 1=1"
    params: list = []
    if industry:
        sql += " AND industry = ?"
        params.append(industry)
    if min_size is not None:
        sql += " AND employee_count >= ?"
        params.append(min_size)
    if max_size is not None:
        sql += " AND employee_count <= ?"
        params.append(max_size)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"accounts": [_account_dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/accounts/{account_id}/research")
def research_account(account_id: int):
    """Research one account over its STORED CRM data only.

    Returns the account's firmographics, its stored tech/buying signals
    (with the rubric points each carries), engagement facts (last touch,
    lead stages on the account) — everything an SDR agent may legitimately
    'research' here. There is no live web in this workplace by design:
    research is over this data, nothing else.
    """
    from rubric import SIGNAL_POINTS

    conn = _conn()
    try:
        acct = _account_dict(_get_account_or_404(conn, account_id))
        leads = conn.execute(
            "SELECT stage, COUNT(*) AS c FROM leads WHERE account_id = ?"
            " GROUP BY stage", (account_id,)).fetchall()
        return {
            "account": acct,
            "signals": [
                {"signal": s, "rubric_points": SIGNAL_POINTS.get(s, 0)}
                for s in acct["tech_signals"]
            ],
            "engagement": {
                "last_touch_days": acct["last_touch_days"],
                "leads_by_stage": {r["stage"]: r["c"] for r in leads},
            },
            "source": "stored CRM data only — no live web research in this workplace",
        }
    finally:
        conn.close()


@app.get("/accounts/{account_id}")
def get_account(account_id: int):
    """Fetch one account, including its leads and CRM notes."""
    conn = _conn()
    try:
        acct = _account_dict(_get_account_or_404(conn, account_id))
        leads = conn.execute(
            "SELECT * FROM leads WHERE account_id = ? ORDER BY id",
            (account_id,)).fetchall()
        acct["leads"] = [_lead_dict(r) for r in leads]
        acct["notes"] = _notes_for(conn, "account", account_id)
        return acct
    finally:
        conn.close()


@app.get("/leads")
def list_leads(
    stage: Optional[str] = Query(default=None),
    account_id: Optional[int] = Query(default=None),
):
    """List leads, optionally filtered by stage and/or account."""
    sql = "SELECT * FROM leads WHERE 1=1"
    params: list = []
    if stage:
        if stage not in STAGES:
            raise HTTPException(status_code=422, detail=f"invalid stage {stage}")
        sql += " AND stage = ?"
        params.append(stage)
    if account_id is not None:
        sql += " AND account_id = ?"
        params.append(account_id)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"leads": [_lead_dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.post("/leads/{lead_id}/score")
def score_lead(lead_id: int, body: ScoreBody):
    """Record an ICP-fit score (0-100) with reasons on a lead.

    WRITE — confirmation-gated at the tool layer. Scoring a `new` lead
    moves it to `researching`. Whether the score FOLLOWS THE RUBRIC is
    not decided here — the Reviewer's deterministic check recomputes it
    from account data (see checks.py); an off-rubric score fails review.
    """
    if not 0 <= body.score <= 100:
        raise HTTPException(status_code=422, detail="score must be 0..100")
    if not body.reasons or not any(r.strip() for r in body.reasons):
        raise HTTPException(status_code=422, detail="score requires at least one reason")
    conn = _conn()
    try:
        lead = _get_lead_or_404(conn, lead_id)
        stage = "researching" if lead["stage"] == "new" else lead["stage"]
        conn.execute(
            "UPDATE leads SET score = ?, score_reasons = ?, stage = ?,"
            " updated_at = ? WHERE id = ?",
            (body.score, json.dumps(body.reasons), stage, _now_iso(), lead_id),
        )
        conn.commit()
        return _lead_dict(_get_lead_or_404(conn, lead_id))
    finally:
        conn.close()


@app.post("/leads/{lead_id}/draft")
def draft_outreach(lead_id: int, body: DraftBody):
    """Create an outreach DRAFT stored on the lead. DRAFTS ONLY.

    WRITE — confirmation-gated at the tool layer. This stores a draft
    message; it does NOT and CANNOT send anything. There is no send
    endpoint in this workplace: sending is a human-gated promotion that
    happens outside the agent tool surface.
    """
    if not body.subject.strip() or not body.body.strip():
        raise HTTPException(status_code=422, detail="draft requires subject and body")
    conn = _conn()
    try:
        lead = _get_lead_or_404(conn, lead_id)
        stage = lead["stage"] if lead["stage"] == "qualified" else "drafted"
        conn.execute(
            "UPDATE leads SET draft_subject = ?, draft_body = ?, stage = ?,"
            " updated_at = ? WHERE id = ?",
            (body.subject, body.body, stage, _now_iso(), lead_id),
        )
        conn.commit()
        return _lead_dict(_get_lead_or_404(conn, lead_id))
    finally:
        conn.close()


@app.post("/leads/{lead_id}/qualify")
def qualify_lead(lead_id: int):
    """Mark a lead qualified. WRITE — confirmation-gated at the tool layer.

    Requires a recorded score at or above the rubric's qualify threshold;
    qualification of an unscored or below-threshold lead is refused here
    and would fail the Reviewer's deterministic check regardless.
    """
    conn = _conn()
    try:
        lead = _get_lead_or_404(conn, lead_id)
        if lead["score"] is None:
            raise HTTPException(status_code=422, detail="lead has no score yet")
        if lead["score"] < QUALIFY_THRESHOLD:
            raise HTTPException(
                status_code=422,
                detail=f"score {lead['score']} below qualify threshold {QUALIFY_THRESHOLD}")
        conn.execute(
            "UPDATE leads SET stage = 'qualified', updated_at = ? WHERE id = ?",
            (_now_iso(), lead_id),
        )
        conn.commit()
        return _lead_dict(_get_lead_or_404(conn, lead_id))
    finally:
        conn.close()


@app.post("/notes")
def add_crm_note(body: NoteBody):
    """Add a CRM note to a lead or an account. WRITE — confirmation-gated
    at the tool layer."""
    if body.target_type not in ("lead", "account"):
        raise HTTPException(status_code=422, detail="target_type must be lead|account")
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="note text required")
    conn = _conn()
    try:
        if body.target_type == "lead":
            _get_lead_or_404(conn, body.target_id)
        else:
            _get_account_or_404(conn, body.target_id)
        cur = conn.execute(
            "INSERT INTO crm_notes (target_type, target_id, author, text, created_at)"
            " VALUES (?,?,?,?,?)",
            (body.target_type, body.target_id, body.author, body.text, _now_iso()),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM crm_notes WHERE id = ?",
                           (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    conn = _conn()
    try:
        accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        by_stage = {
            r["stage"]: r["c"] for r in conn.execute(
                "SELECT stage, COUNT(*) AS c FROM leads GROUP BY stage").fetchall()
        }
        unscored_new = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE stage = 'new' AND score IS NULL"
        ).fetchone()[0]
        qualified_no_draft = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE stage = 'qualified'"
            " AND (draft_body IS NULL OR draft_body = '')").fetchone()[0]
        return {
            "total_accounts": accounts,
            "total_leads": sum(by_stage.values()),
            "leads_by_stage": by_stage,
            "unscored_new_leads": unscored_new,
            "qualified_without_draft": qualified_no_draft,
        }
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
    counts = seed_module.seed(DB_PATH)
    return {"reset": True, **counts}
