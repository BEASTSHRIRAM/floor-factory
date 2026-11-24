"""QADesk — a deliberately ordinary internal CI-triage API.

THE FLOOR's QA triage department workplace (department id "qa"). Plain
FastAPI + its own SQLite file, mirroring TicketDesk's shape exactly.
THE FLOOR never modifies this code; agents only reach it through
Synapse-generated MCP tools.

Run:   uvicorn app:app --port 8103
Seed:  python3 seed.py     (creates qa.db with the CI failure dataset)
Reset: python3 reset.py    (deletes qa.db and reseeds)
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="QADesk", version="1.0.0")

VERDICTS = {"regression", "no_regression"}
NOTE_TARGETS = {"failure", "cluster", "run", "test"}


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


def _get_run_or_404(conn: sqlite3.Connection, run_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    return row


def _get_failure_or_404(conn: sqlite3.Connection, failure_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM failures WHERE id = ?", (failure_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"failure {failure_id} not found")
    return row


def _first_seen_run(conn: sqlite3.Connection, signature: str) -> Optional[int]:
    row = conn.execute(
        "SELECT MIN(run_id) AS r FROM failures WHERE signature = ?",
        (signature,)).fetchone()
    return row["r"]


def _new_failure_count(conn: sqlite3.Connection, run_id: int) -> int:
    """Failures in this run whose signature was first seen in this run."""
    return conn.execute(
        "SELECT COUNT(*) FROM failures f WHERE f.run_id = ? AND"
        " (SELECT MIN(run_id) FROM failures WHERE signature = f.signature) = ?",
        (run_id, run_id)).fetchone()[0]


def _run_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["failure_count"] = conn.execute(
        "SELECT COUNT(*) FROM failures WHERE run_id = ?", (row["id"],)).fetchone()[0]
    d["new_failure_count"] = _new_failure_count(conn, row["id"])
    return d


def _failure_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    d = dict(row)
    d["is_new_signature"] = _first_seen_run(conn, row["signature"]) == row["run_id"]
    return d


def _cluster_title(signature: str) -> str:
    head = signature.split(":")[0]
    return f"{head} cluster"


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class ClusterBody(BaseModel):
    run_id: Optional[int] = None   # null = cluster every unclustered failure
    author: str = "qa"


class QuarantineBody(BaseModel):
    test_name: str
    author: str = "qa"
    reason: str = ""


class VerdictBody(BaseModel):
    verdict: str                   # regression | no_regression
    author: str = "qa"
    note: str = ""


class NoteBody(BaseModel):
    target_type: str               # failure | cluster | run | test
    target_id: str
    author: str = "qa"
    text: str


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist — exactly 7 tools)
# --------------------------------------------------------------------------

@app.get("/runs")
def list_runs(status: Optional[str] = Query(default=None),
              branch: Optional[str] = Query(default=None)):
    """List CI runs, newest first, with failure counts per run."""
    sql = "SELECT * FROM runs WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if branch:
        sql += " AND branch = ?"
        params.append(branch)
    sql += " ORDER BY id DESC"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"runs": [_run_dict(conn, r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/failures")
def list_failures(run_id: Optional[int] = Query(default=None),
                  suite: Optional[str] = Query(default=None),
                  status: Optional[str] = Query(default=None),
                  signature: Optional[str] = Query(default=None),
                  test_name: Optional[str] = Query(default=None),
                  cluster_id: Optional[int] = Query(default=None)):
    """List failures, optionally filtered by run / suite / status /
    signature / test name / cluster."""
    sql = "SELECT * FROM failures WHERE 1=1"
    params: list = []
    if run_id is not None:
        sql += " AND run_id = ?"
        params.append(run_id)
    if suite:
        sql += " AND suite = ?"
        params.append(suite)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if signature:
        sql += " AND signature = ?"
        params.append(signature)
    if test_name:
        sql += " AND test_name = ?"
        params.append(test_name)
    if cluster_id is not None:
        sql += " AND cluster_id = ?"
        params.append(cluster_id)
    sql += " ORDER BY run_id, id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"failures": [_failure_dict(conn, r) for r in rows],
                "count": len(rows)}
    finally:
        conn.close()


@app.get("/failures/{failure_id}")
def get_failure_detail(failure_id: int):
    """Fetch one failure with its cluster, the full pass/fail history of
    its test across all runs, and stats for its error signature."""
    conn = _conn()
    try:
        row = _get_failure_or_404(conn, failure_id)
        d = _failure_dict(conn, row)
        cluster = None
        if row["cluster_id"] is not None:
            c = conn.execute("SELECT * FROM clusters WHERE id = ?",
                             (row["cluster_id"],)).fetchone()
            if c is not None:
                cluster = dict(c)
        history = [dict(r) for r in conn.execute(
            "SELECT run_id, outcome, duration_ms FROM test_results"
            " WHERE test_name = ? ORDER BY run_id", (row["test_name"],)).fetchall()]
        sig_total = conn.execute(
            "SELECT COUNT(*) FROM failures WHERE signature = ?",
            (row["signature"],)).fetchone()[0]
        sig_tests = conn.execute(
            "SELECT COUNT(DISTINCT test_name) FROM failures WHERE signature = ?",
            (row["signature"],)).fetchone()[0]
        quarantined = conn.execute(
            "SELECT * FROM quarantined_tests WHERE test_name = ?",
            (row["test_name"],)).fetchone()
        d["cluster"] = cluster
        d["test_history"] = history
        d["signature_stats"] = {
            "first_seen_run_id": _first_seen_run(conn, row["signature"]),
            "total_failures": sig_total,
            "distinct_tests": sig_tests,
        }
        d["test_quarantined"] = dict(quarantined) if quarantined else None
        d["triage_notes"] = [dict(r) for r in conn.execute(
            "SELECT * FROM triage_notes WHERE target_type = 'failure'"
            " AND target_id = ? ORDER BY id", (str(failure_id),)).fetchall()]
        return d
    finally:
        conn.close()


@app.post("/failures/cluster")
def cluster_failures(body: ClusterBody):
    """Group unclustered failures by error signature: find-or-create one
    cluster per signature and assign every matching failure to it.
    Idempotent — already-clustered failures are left untouched."""
    conn = _conn()
    try:
        if body.run_id is not None:
            _get_run_or_404(conn, body.run_id)
            rows = conn.execute(
                "SELECT * FROM failures WHERE run_id = ? AND cluster_id IS NULL"
                " ORDER BY id", (body.run_id,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM failures WHERE cluster_id IS NULL ORDER BY id"
            ).fetchall()
        now = seed_module._iso(_now())
        touched: dict[int, dict] = {}
        assigned = 0
        for row in rows:
            sig = row["signature"]
            c = conn.execute("SELECT * FROM clusters WHERE signature = ?",
                             (sig,)).fetchone()
            if c is None:
                cur = conn.execute(
                    "INSERT INTO clusters (signature, title, created_at, created_by)"
                    " VALUES (?,?,?,?)",
                    (sig, _cluster_title(sig), now, body.author))
                cluster_id = cur.lastrowid
            else:
                cluster_id = c["id"]
            conn.execute(
                "UPDATE failures SET cluster_id = ?,"
                " status = CASE WHEN status = 'quarantined' THEN status"
                " ELSE 'clustered' END WHERE id = ?",
                (cluster_id, row["id"]))
            entry = touched.setdefault(cluster_id, {
                "id": cluster_id, "signature": sig,
                "title": _cluster_title(sig), "failure_ids": []})
            entry["failure_ids"].append(row["id"])
            assigned += 1
        conn.commit()
        clusters = []
        for entry in touched.values():
            entry["count"] = len(entry["failure_ids"])
            clusters.append(entry)
        return {"clusters": clusters, "assigned": assigned, "run_id": body.run_id}
    finally:
        conn.close()


@app.post("/tests/quarantine")
def quarantine_test(body: QuarantineBody):
    """Mark a test as flaky and quarantine it: records the quarantine and
    moves all of the test's open failures to status 'quarantined'.
    Idempotent — re-quarantining returns the existing record."""
    conn = _conn()
    try:
        known = conn.execute(
            "SELECT COUNT(*) FROM test_results WHERE test_name = ?",
            (body.test_name,)).fetchone()[0]
        if known == 0:
            raise HTTPException(status_code=404,
                                detail=f"unknown test {body.test_name!r}")
        existing = conn.execute(
            "SELECT * FROM quarantined_tests WHERE test_name = ?",
            (body.test_name,)).fetchone()
        if existing is not None:
            return {"quarantined": dict(existing), "already": True}
        now = seed_module._iso(_now())
        conn.execute(
            "INSERT INTO quarantined_tests (test_name, author, reason,"
            " quarantined_at) VALUES (?,?,?,?)",
            (body.test_name, body.author, body.reason, now))
        cur = conn.execute(
            "UPDATE failures SET status = 'quarantined'"
            " WHERE test_name = ? AND status != 'quarantined'",
            (body.test_name,))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM quarantined_tests WHERE test_name = ?",
            (body.test_name,)).fetchone()
        return {"quarantined": dict(row), "already": False,
                "failures_quarantined": cur.rowcount}
    finally:
        conn.close()


@app.post("/runs/{run_id}/regression-verdict")
def set_regression_verdict(run_id: int, body: VerdictBody):
    """Record the regression verdict for a run (regression | no_regression)."""
    if body.verdict not in VERDICTS:
        raise HTTPException(status_code=422,
                            detail=f"invalid verdict {body.verdict!r}")
    conn = _conn()
    try:
        _get_run_or_404(conn, run_id)
        now = seed_module._iso(_now())
        conn.execute(
            "UPDATE runs SET regression_verdict = ?, verdict_by = ?,"
            " verdict_at = ? WHERE id = ?",
            (body.verdict, body.author, now, run_id))
        if body.note:
            conn.execute(
                "INSERT INTO triage_notes (target_type, target_id, author, text,"
                " created_at) VALUES ('run', ?, ?, ?, ?)",
                (str(run_id), body.author, body.note, now))
        conn.commit()
        return _run_dict(conn, _get_run_or_404(conn, run_id))
    finally:
        conn.close()


@app.post("/triage-notes")
def add_triage_note(body: NoteBody):
    """Attach a triage note to a failure, cluster, run, or test."""
    if body.target_type not in NOTE_TARGETS:
        raise HTTPException(status_code=422,
                            detail=f"invalid target_type {body.target_type!r}")
    conn = _conn()
    try:
        if body.target_type == "failure":
            _get_failure_or_404(conn, int(body.target_id))
        elif body.target_type == "run":
            _get_run_or_404(conn, int(body.target_id))
        elif body.target_type == "cluster":
            c = conn.execute("SELECT * FROM clusters WHERE id = ?",
                             (int(body.target_id),)).fetchone()
            if c is None:
                raise HTTPException(status_code=404,
                                    detail=f"cluster {body.target_id} not found")
        else:  # test
            known = conn.execute(
                "SELECT COUNT(*) FROM test_results WHERE test_name = ?",
                (body.target_id,)).fetchone()[0]
            if known == 0:
                raise HTTPException(status_code=404,
                                    detail=f"unknown test {body.target_id!r}")
        now = seed_module._iso(_now())
        cur = conn.execute(
            "INSERT INTO triage_notes (target_type, target_id, author, text,"
            " created_at) VALUES (?,?,?,?,?)",
            (body.target_type, body.target_id, body.author, body.text, now))
        conn.commit()
        note = conn.execute("SELECT * FROM triage_notes WHERE id = ?",
                            (cur.lastrowid,)).fetchone()
        return {"note": dict(note)}
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
    return {"reset": True, "runs": out["runs"], "failures": out["failures"]}
