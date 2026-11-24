"""HRDesk — a deliberately ordinary internal ATS-lite API (THE FLOOR,
HR department workplace; mirrors targets/ticketdesk exactly in shape).

Plain FastAPI + its own SQLite file. THE FLOOR never modifies this code;
agents only reach it through Synapse-shaped MCP tools.

PLATFORM RULE — the hiring decision stays human. This API deliberately
has NO hire/reject endpoint and no delete endpoint: screening records a
rubric-scored RECOMMENDATION (score computed here, from the role's stated
rubric — never taken from the caller), interviews may only be scheduled
for candidates whose screening passed the rubric threshold, and whether
anyone is actually hired is decided by a human, outside this system.

Run:   uvicorn app:app --port 8107
Seed:  python3 seed.py     (creates hrdesk.db with the seeded dataset)
Reset: python3 reset.py    (deletes hrdesk.db and reseeds)
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

app = FastAPI(title="HRDesk", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _role(conn: sqlite3.Connection, role_key: str) -> dict:
    row = conn.execute("SELECT * FROM roles WHERE key = ?", (role_key,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"role {role_key} not found")
    d = dict(row)
    d["required_skills"] = json.loads(d["required_skills"])
    return d


def _candidate_dict(conn: sqlite3.Connection, row: sqlite3.Row,
                    detail: bool = False) -> dict:
    d = dict(row)
    d["skills"] = json.loads(d["skills"])
    d["role"] = _role(conn, d["role_key"])
    if detail:
        d["interviews"] = [dict(r) for r in conn.execute(
            "SELECT * FROM interviews WHERE candidate_id = ? ORDER BY id",
            (d["id"],)).fetchall()]
        d["notes"] = [dict(r) for r in conn.execute(
            "SELECT * FROM hr_notes WHERE candidate_id = ? ORDER BY id",
            (d["id"],)).fetchall()]
        d["onboarding_steps"] = [dict(r) for r in conn.execute(
            "SELECT * FROM onboarding_steps WHERE candidate_id = ? ORDER BY id",
            (d["id"],)).fetchall()]
    return d


def _get_candidate_or_404(conn: sqlite3.Connection, candidate_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM candidates WHERE id = ?",
                       (candidate_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404,
                            detail=f"candidate {candidate_id} not found")
    return row


def _onboarding_for(conn: sqlite3.Connection, candidate_id: int) -> dict:
    cand = _candidate_dict(conn, _get_candidate_or_404(conn, candidate_id))
    steps = [dict(r) for r in conn.execute(
        "SELECT * FROM onboarding_steps WHERE candidate_id = ? ORDER BY id",
        (candidate_id,)).fetchall()]
    required = [s["step_key"] for s in steps if s["required"]]
    return {
        "candidate_id": candidate_id,
        "candidate_name": cand["name"],
        "role_key": cand["role_key"],
        "required_documents": required,
        "steps": steps,
        "complete": bool(required) and all(
            s["done"] for s in steps if s["required"]),
    }


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class ScreenBody(BaseModel):
    screener: str = "hr-agent"
    notes: str = ""


class InterviewBody(BaseModel):
    scheduled_at: str  # ISO-8601
    interviewer: str = ""
    kind: str = "panel"  # phone | panel | final


class NoteBody(BaseModel):
    author: str = "hr"
    text: str


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist)
# --------------------------------------------------------------------------

@app.get("/candidates")
def list_candidates(
    stage: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
):
    """List candidates, optionally filtered by stage / role key."""
    sql = "SELECT * FROM candidates WHERE 1=1"
    params: list = []
    if stage:
        sql += " AND stage = ?"
        params.append(stage)
    if role:
        sql += " AND role_key = ?"
        params.append(role)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"candidates": [_candidate_dict(conn, r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/candidates/{candidate_id}")
def get_candidate(candidate_id: int):
    """Fetch one candidate with screening record, interviews, notes, steps."""
    conn = _conn()
    try:
        return _candidate_dict(conn, _get_candidate_or_404(conn, candidate_id),
                               detail=True)
    finally:
        conn.close()


@app.post("/candidates/{candidate_id}/screen")
def screen_candidate(candidate_id: int, body: ScreenBody):
    """WRITE: record a screening for a candidate. The score and verdict are
    computed HERE from the role's stated rubric (required skills present /
    absent) — the caller supplies only notes. The verdict is a
    recommendation (recommend_interview | recommend_hold); it is NOT a
    hire/reject decision, which stays human by platform rule."""
    conn = _conn()
    try:
        row = _get_candidate_or_404(conn, candidate_id)
        role = _role(conn, row["role_key"])
        skills = json.loads(row["skills"])
        score = seed_module.rubric_score(skills, role)
        verdict = seed_module.rubric_verdict(score, role)
        now = seed_module._iso(_now())
        stage = "screening" if row["stage"] == "applied" else row["stage"]
        conn.execute(
            "UPDATE candidates SET screening_score = ?, screening_verdict = ?,"
            " screening_notes = ?, screened_by = ?, screened_at = ?,"
            " stage = ?, updated_at = ? WHERE id = ?",
            (score, verdict, body.notes, body.screener, now, stage, now,
             candidate_id),
        )
        conn.execute(
            "INSERT INTO hr_notes (candidate_id, author, text, created_at)"
            " VALUES (?,?,?,?)",
            (candidate_id, body.screener,
             f"Screening: rubric score {score}/100 vs threshold "
             f"{role['pass_threshold']} for {role['title']} -> {verdict}. "
             f"{body.notes}".strip(), now),
        )
        conn.commit()
        return _candidate_dict(conn, _get_candidate_or_404(conn, candidate_id),
                               detail=True)
    finally:
        conn.close()


@app.post("/candidates/{candidate_id}/interviews")
def schedule_interview(candidate_id: int, body: InterviewBody):
    """WRITE: schedule an interview. Refused (422) unless the candidate's
    screening passed the role's rubric threshold — interviews are scheduled
    only for candidates whose screening recommends one."""
    if body.kind not in ("phone", "panel", "final"):
        raise HTTPException(status_code=422, detail=f"invalid kind {body.kind}")
    conn = _conn()
    try:
        row = _get_candidate_or_404(conn, candidate_id)
        role = _role(conn, row["role_key"])
        skills = json.loads(row["skills"])
        score = seed_module.rubric_score(skills, role)
        if row["screening_verdict"] != "recommend_interview" or \
                score < role["pass_threshold"]:
            raise HTTPException(
                status_code=422,
                detail="candidate's screening does not recommend an interview "
                       f"(verdict={row['screening_verdict']}, rubric score "
                       f"{score} vs threshold {role['pass_threshold']})")
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO interviews (candidate_id, scheduled_at, interviewer,"
            " kind, status, created_at) VALUES (?,?,?,?,?,?)",
            (candidate_id, body.scheduled_at, body.interviewer, body.kind,
             "scheduled", now),
        )
        stage = "interview" if row["stage"] in ("applied", "screening") else row["stage"]
        conn.execute("UPDATE candidates SET stage = ?, updated_at = ? WHERE id = ?",
                     (stage, now, candidate_id))
        conn.commit()
        interview = conn.execute("SELECT * FROM interviews WHERE id = ?",
                                 (cur.lastrowid,)).fetchone()
        return {"interview": dict(interview),
                "candidate": _candidate_dict(
                    conn, _get_candidate_or_404(conn, candidate_id))}
    finally:
        conn.close()


@app.get("/onboarding")
def list_onboarding():
    """List this week's joiners with their onboarding checklists."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id FROM candidates WHERE stage = 'onboarding' ORDER BY id"
        ).fetchall()
        joiners = [_onboarding_for(conn, r["id"]) for r in rows]
        return {"joiners": joiners, "count": len(joiners)}
    finally:
        conn.close()


@app.post("/onboarding/{candidate_id}/steps/{step_key}/complete")
def complete_onboarding_step(candidate_id: int, step_key: str):
    """WRITE: mark one onboarding checklist step complete for a joiner."""
    conn = _conn()
    try:
        _get_candidate_or_404(conn, candidate_id)
        row = conn.execute(
            "SELECT * FROM onboarding_steps WHERE candidate_id = ? AND step_key = ?",
            (candidate_id, step_key)).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"no onboarding step {step_key!r} for candidate {candidate_id}")
        now = seed_module._iso(_now())
        conn.execute(
            "UPDATE onboarding_steps SET done = 1, done_at = ?"
            " WHERE candidate_id = ? AND step_key = ?",
            (now, candidate_id, step_key))
        conn.commit()
        return _onboarding_for(conn, candidate_id)
    finally:
        conn.close()


@app.post("/candidates/{candidate_id}/notes")
def add_hr_note(candidate_id: int, body: NoteBody):
    """WRITE: add a free-text HR note to a candidate's record."""
    conn = _conn()
    try:
        _get_candidate_or_404(conn, candidate_id)
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO hr_notes (candidate_id, author, text, created_at)"
            " VALUES (?,?,?,?)",
            (candidate_id, body.author, body.text, now))
        conn.commit()
        note = conn.execute("SELECT * FROM hr_notes WHERE id = ?",
                            (cur.lastrowid,)).fetchone()
        return {"note": dict(note)}
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    conn = _conn()
    try:
        by_stage = {r["stage"]: r["c"] for r in conn.execute(
            "SELECT stage, COUNT(*) AS c FROM candidates GROUP BY stage").fetchall()}
        unscreened = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE screening_verdict IS NULL"
        ).fetchone()[0]
        joiners = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE stage = 'onboarding'"
        ).fetchone()[0]
        incomplete = 0
        for r in conn.execute(
                "SELECT id FROM candidates WHERE stage = 'onboarding'").fetchall():
            if not _onboarding_for(conn, r["id"])["complete"]:
                incomplete += 1
        return {"total_candidates": sum(by_stage.values()), "by_stage": by_stage,
                "unscreened": unscreened, "joiners": joiners,
                "joiners_incomplete_checklists": incomplete}
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
    n = seed_module.seed(DB_PATH)
    return {"reset": True, "candidates": n}
