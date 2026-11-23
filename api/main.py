"""THE FLOOR — API (FastAPI, :8000).

Serves the mission-control UI's data needs and the demo controls:

    GET  /health                  liveness + target-system reachability
    GET  /state/agents            roster (incl. fired) with balances
    GET  /state/jobs              jobs with bids + work orders embedded
    GET  /state/ledger            append-only ledger, newest first (?limit=)
    GET  /state/events            stored events (?after_seq=&limit=)
    GET  /events                  SSE: replay from ?from_seq=, then live
    POST /run/shift?cycles=2      run one full shift (background; &wait=true blocks)
    POST /reset                   reset floor.db + roster, reseed TicketDesk
    GET  /approvals               pending write confirmations (manual gate mode)
    POST /approvals/{confirmation_id}   {"approved": true, "by": "human"}
    POST /confirmations/{confirmation_id}  alias of the above

Static UI: if repo/ui/ contains an index.html it is served at / (mounted
last, so API routes win).

Run:
    cd repo && .venv/bin/python -m uvicorn api.main:app --port 8000
TicketDesk must be running on :8101 for a shift to do real work
(StockRoom on :8102 is only probed/reset best-effort by this API).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import engine as floor_engine  # noqa: E402
from orchestrator import tools as floor_tools  # noqa: E402

try:
    from economy import core as ECO
    from economy import db as EDB
except Exception:  # noqa: BLE001 — same fallback as the engine
    from orchestrator import shim as ECO  # type: ignore
    from orchestrator import shim as EDB  # type: ignore

TICKETDESK_URL = os.environ.get("TICKETDESK_URL", "http://localhost:8101").rstrip("/")
STOCKROOM_URL = os.environ.get("STOCKROOM_URL", "http://localhost:8102").rstrip("/")

app = FastAPI(title="THE FLOOR", version="1.0.0")

_shift_lock = threading.Lock()
_shift_state: dict = {"running": False, "last_summary": None, "last_error": None}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _conn():
    """Fresh connection with schema + roster guaranteed (read paths)."""
    conn = EDB.init_db()
    ECO.seed_roster(conn)
    return conn


def _rows(conn, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def _probe(url: str) -> bool:
    try:
        # trust_env=False: this VM's no_proxy contains bracketed IPv6 entries
        # that this httpx version cannot parse; target systems are local.
        return httpx.get(f"{url}/health", timeout=2.0, trust_env=False).status_code == 200
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# health + state snapshots
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    conn = _conn()
    try:
        agents = conn.execute("SELECT COUNT(*) AS n FROM agents").fetchone()["n"]
        last_seq = conn.execute("SELECT COALESCE(MAX(seq), 0) AS s FROM events").fetchone()["s"]
    finally:
        conn.close()
    return {
        "status": "ok",
        "agents": agents,
        "last_event_seq": last_seq,
        "ticketdesk": _probe(TICKETDESK_URL),
        "stockroom": _probe(STOCKROOM_URL),
        "shift_running": _shift_state["running"],
        "economy_source": floor_engine.ECONOMY_SOURCE,
    }


@app.get("/state/agents")
def state_agents() -> dict:
    conn = _conn()
    try:
        agents = _rows(conn, "SELECT * FROM agents ORDER BY id")
        for a in agents:
            row = conn.execute(
                "SELECT balance_after FROM ledger WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
                (a["id"],)).fetchone()
            a["balance_credits"] = row["balance_after"] if row else 0
        return {"agents": agents}
    finally:
        conn.close()


@app.get("/state/jobs")
def state_jobs() -> dict:
    conn = _conn()
    try:
        jobs = _rows(conn, "SELECT * FROM jobs ORDER BY id")
        for job in jobs:
            job["acceptance_criteria"] = json.loads(job["acceptance_criteria"] or "[]")
            job["bids"] = _rows(
                conn,
                "SELECT b.*, a.name AS agent_name FROM bids b JOIN agents a ON a.id = b.agent_id"
                " WHERE b.job_id = ? ORDER BY b.id", (job["id"],))
            job["work_orders"] = _rows(
                conn, "SELECT * FROM work_orders WHERE job_id = ? ORDER BY id", (job["id"],))
        return {"jobs": jobs}
    finally:
        conn.close()


@app.get("/state/ledger")
def state_ledger(limit: int = Query(100, ge=1, le=1000)) -> dict:
    conn = _conn()
    try:
        rows = _rows(
            conn,
            "SELECT l.*, a.name AS agent_name FROM ledger l JOIN agents a ON a.id = l.agent_id"
            " ORDER BY l.id DESC LIMIT ?", (limit,))
        return {"ledger": rows}
    finally:
        conn.close()


@app.get("/state/events")
def state_events(after_seq: int = Query(0, ge=0),
                 limit: int = Query(200, ge=1, le=2000)) -> dict:
    conn = _conn()
    try:
        rows = _rows(
            conn,
            "SELECT seq, type, payload_json, created_at FROM events WHERE seq > ?"
            " ORDER BY seq LIMIT ?", (after_seq, limit))
        return {"events": [_event_dict(r) for r in rows]}
    finally:
        conn.close()


def _event_dict(row: dict) -> dict:
    return {"seq": row["seq"], "type": row["type"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "created_at": row["created_at"]}


# ---------------------------------------------------------------------------
# SSE event stream: replay, then live
# ---------------------------------------------------------------------------

@app.get("/events")
def events_stream(from_seq: int = Query(0, ge=0)) -> StreamingResponse:
    def generate():
        last = from_seq
        idle = 0
        while True:
            conn = EDB.get_conn()
            try:
                rows = [dict(r) for r in conn.execute(
                    "SELECT seq, type, payload_json, created_at FROM events"
                    " WHERE seq > ? ORDER BY seq LIMIT 500", (last,)).fetchall()]
            finally:
                conn.close()
            if rows:
                idle = 0
                for row in rows:
                    last = row["seq"]
                    yield f"data: {json.dumps(_event_dict(row))}\n\n"
            else:
                idle += 1
                if idle % 30 == 0:
                    yield ": ping\n\n"
                time.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# controls: run a shift, reset, approvals
# ---------------------------------------------------------------------------

def _run_shift_thread(cycles: int) -> None:
    try:
        summary = floor_engine.run_shift(cycles=cycles)
        _shift_state["last_summary"] = summary
        _shift_state["last_error"] = None
    except Exception as exc:  # noqa: BLE001 — surfaced via /health + response state
        _shift_state["last_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _shift_state["running"] = False
        _shift_lock.release()


@app.post("/run/shift")
def run_shift_endpoint(cycles: int = Query(2, ge=1, le=6),
                       wait: bool = Query(False)) -> JSONResponse:
    if not _shift_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a shift is already running")
    _shift_state["running"] = True
    if wait:
        try:
            summary = floor_engine.run_shift(cycles=cycles)
            _shift_state.update(last_summary=summary, last_error=None)
            return JSONResponse({"started": False, "completed": True, "summary": summary})
        except Exception as exc:  # noqa: BLE001
            _shift_state["last_error"] = f"{type(exc).__name__}: {exc}"
            raise HTTPException(status_code=500, detail=_shift_state["last_error"]) from exc
        finally:
            _shift_state["running"] = False
            _shift_lock.release()
    thread = threading.Thread(target=_run_shift_thread, args=(cycles,), daemon=True)
    thread.start()
    return JSONResponse({"started": True, "cycles": cycles,
                         "note": "watch /events (SSE) or /state/* for progress"})


@app.get("/run/status")
def run_status() -> dict:
    return {"running": _shift_state["running"],
            "last_error": _shift_state["last_error"],
            "last_summary": _shift_state["last_summary"]}


@app.post("/reset")
def reset_endpoint() -> dict:
    if _shift_state["running"]:
        raise HTTPException(status_code=409, detail="cannot reset while a shift is running")
    floor = floor_engine.reset_floor()
    ticketdesk = _reset_target(TICKETDESK_URL, REPO_ROOT / "targets" / "ticketdesk")
    stockroom = None
    try:
        resp = httpx.post(f"{STOCKROOM_URL}/admin/reset", timeout=5.0, trust_env=False)
        stockroom = resp.json() if resp.status_code == 200 else {"error": resp.status_code}
    except Exception as exc:  # noqa: BLE001 — StockRoom is best-effort for this API
        stockroom = {"error": str(exc)[:200]}
    return {"floor": floor, "ticketdesk": ticketdesk, "stockroom": stockroom}


def _reset_target(base_url: str, target_dir: Path) -> dict:
    """Prefer the running app's /admin/reset; fall back to its seed script."""
    try:
        resp = httpx.post(f"{base_url}/admin/reset", timeout=5.0, trust_env=False)
        if resp.status_code == 200:
            return resp.json()
    except Exception:  # noqa: BLE001
        pass
    try:
        proc = subprocess.run([sys.executable, "reset.py"], cwd=str(target_dir),
                              capture_output=True, text=True, timeout=30)
        return {"reset_via": "reset.py", "stdout": proc.stdout.strip(),
                "returncode": proc.returncode}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}


@app.get("/approvals")
def approvals_list() -> dict:
    return {"pending": floor_tools.pending_approvals(),
            "auto_approve": floor_tools.auto_approve_writes()}


@app.post("/approvals/{confirmation_id}")
@app.post("/confirmations/{confirmation_id}")
async def approval_resolve(confirmation_id: str, request: Request) -> dict:
    body = await request.json()
    approved = bool(body.get("approved", False))
    by = str(body.get("by", "human"))
    if not floor_tools.resolve_approval(confirmation_id, approved, by):
        raise HTTPException(status_code=404, detail="unknown or already-resolved confirmation_id")
    return {"confirmation_id": confirmation_id, "approved": approved, "by": by}


# ---------------------------------------------------------------------------
# static UI (mounted last so API routes win)
# ---------------------------------------------------------------------------

_ui_dir = REPO_ROOT / "ui"
if (_ui_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_ui_dir), html=True), name="ui")
