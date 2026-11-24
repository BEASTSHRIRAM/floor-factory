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
    GET  /mode                    floor mode (manual|auto) + gate + auto-run state
    POST /mode                    {"mode": "auto", "by": "human"} — emits mode.changed
    POST /auto/start              {"budget_cap_credits": 1000, "by": "human"} (idempotent)
    POST /auto/pause              pause auto-run at the next cycle boundary
    POST /auto/stop               stop auto-run at the next cycle boundary
    GET  /auto/status             auto-run state only

Floor modes are documented in docs/MODES.md: manual = writes wait for a
human at the confirmation gate; auto = the floor runs itself inside a
human-set budget cap, every auto-approval audited. The mode changes the
approval flow only — never tool allowlists or the deterministic checks.

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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import departments as floor_departments  # noqa: E402
from orchestrator import engine as floor_engine  # noqa: E402
from orchestrator import mode as floor_mode  # noqa: E402
from orchestrator import tools as floor_tools  # noqa: E402

try:
    from economy import core as ECO
    from economy import db as EDB
except Exception:  # noqa: BLE001 — same fallback as the engine
    from orchestrator import shim as ECO  # type: ignore
    from orchestrator import shim as EDB  # type: ignore

TICKETDESK_URL = os.environ.get("TICKETDESK_URL", "http://localhost:8101").rstrip("/")
STOCKROOM_URL = os.environ.get("STOCKROOM_URL", "http://localhost:8102").rstrip("/")

# All department workplaces, for /reset and /health. kind -> (url, dir)
TARGETS = {
    "ticketdesk": (TICKETDESK_URL, REPO_ROOT / "targets" / "ticketdesk"),
    "stockroom": (STOCKROOM_URL, REPO_ROOT / "targets" / "stockroom"),
    "qa": (os.environ.get("QA_URL", "http://localhost:8103").rstrip("/"), REPO_ROOT / "targets" / "qa"),
    "bookkeeping": (os.environ.get("BOOKKEEPING_URL", "http://localhost:8104").rstrip("/"), REPO_ROOT / "targets" / "bookkeeping"),
    "sdr": (os.environ.get("SDR_URL", "http://localhost:8105").rstrip("/"), REPO_ROOT / "targets" / "sdr"),
    "engineering": (os.environ.get("ENGINEERING_URL", "http://localhost:8106").rstrip("/"), REPO_ROOT / "targets" / "engineering"),
    "hrdesk": (os.environ.get("HRDESK_URL", "http://localhost:8107").rstrip("/"), REPO_ROOT / "targets" / "hrdesk"),
}

# Job title -> (department, department_label) from the registered
# families. Audit jobs share their family's title once the "Audit: "
# prefix is stripped (see /state/jobs).
_TITLE_DEPT = {
    f.title: (f.department, floor_departments.DEPT_LABELS.get(f.department, f.department))
    for f in floor_engine.JOB_FAMILIES
}

app = FastAPI(title="THE FLOOR", version="1.0.0")

# The Next.js mission control (ui-next) runs on :3000 and talks to this API
# cross-origin; the vanilla UI is served from this same origin. Local demo
# stack, so permissive CORS is deliberate here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_shift_lock = threading.Lock()
_shift_state: dict = {"running": False, "last_summary": None, "last_error": None}

# Auto-run state (docs/MODES.md). The loop thread is the only writer of the
# progress fields; the endpoints set the request flags. All access is via
# _auto_lock. Status: stopped | running | paused.
_auto_lock = threading.Lock()
_auto_state: dict = {
    "status": "stopped",
    "budget_cap_credits": None,
    "spent_credits": 0,
    "cycles_completed": 0,
    "current_cycle": None,
    "last_cycle_spend_credits": None,
    "stop_reason": None,
    "started_by": None,
    "last_error": None,
    "pause_requested": False,
    "stop_requested": False,
    "pending_stop_reason": None,
}
_auto_thread: Optional[threading.Thread] = None


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


def _emit_api_event(type_: str, payload: dict) -> None:
    """Append an event to the floor event log from the API layer."""
    conn = _conn()
    try:
        with conn:
            EDB.emit_event(conn, type_, payload)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# floor mode + auto-run helpers (docs/MODES.md)
# ---------------------------------------------------------------------------

def _auto_public() -> dict:
    with _auto_lock:
        return {k: _auto_state[k] for k in (
            "status", "budget_cap_credits", "spent_credits", "cycles_completed",
            "current_cycle", "last_cycle_spend_credits", "stop_reason",
            "started_by", "last_error")}


def _mode_public() -> dict:
    mode = floor_mode.get_mode()
    return {
        "mode": mode,
        "changed_by": floor_mode.changed_by(),
        "gate": {
            "writes_require_human_confirmation": mode == "manual",
            "auto_approve": mode == "auto",
        },
        "auto_run": _auto_public(),
        "recent_auto_approvals": floor_tools.recent_auto_approvals(10),
    }


def _next_cycle_no() -> int:
    conn = _conn()
    try:
        return conn.execute(
            "SELECT COALESCE(MAX(cycle_no), 0) + 1 AS n FROM payroll_cycles").fetchone()["n"]
    finally:
        conn.close()


def _cycle_spend_credits(cycle_no: int) -> int:
    """Credits the floor PAID OUT in a cycle: sum of positive ledger rows
    (earnings + review fees). Salaries and appeal fees are charged against
    agent balances, not paid out, so they do not consume the auto budget."""
    conn = _conn()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(amount_credits), 0) AS s FROM ledger"
            " WHERE cycle_no = ? AND amount_credits > 0", (cycle_no,)).fetchone()["s"]
    finally:
        conn.close()


def _projected_cycle_spend(cycle_no: int, last_actual: Optional[int]) -> int:
    """Deterministic projection of the next cycle's payout (code, not LLM).

    With a completed cycle on record, the projection is that cycle's actual
    payout. For the first cycle there is no history, so the projection is
    the worst case: the sum of the budgets of the job families the engine
    will post (bids can never exceed a job's budget) plus the maximum
    review fees (primary + appeal review per job).
    """
    if last_actual is not None:
        return int(last_actual)
    total = 0
    n_jobs = 0
    for fam in floor_engine.JOB_FAMILIES:
        if fam.key == "vip_save" and cycle_no < 2:
            continue  # engine posts VIP save from cycle 2 (mirrors run_shift)
        total += round(fam.budget * (0.6 if cycle_no >= 2 else 1.0))
        n_jobs += 1
    return total + 2 * int(getattr(ECO, "REVIEW_FEE", 10)) * n_jobs


def _auto_finish(status: str, event_type: str, payload: dict) -> None:
    """Terminal transition for the auto-run loop (called by the loop only)."""
    with _auto_lock:
        _auto_state["status"] = status
        _auto_state["current_cycle"] = None
        _auto_state["pause_requested"] = False
        _auto_state["stop_requested"] = False
        _auto_state["pending_stop_reason"] = None
        if event_type == "auto.stopped":
            _auto_state["stop_reason"] = payload.get("reason")
    _emit_api_event(event_type, payload)


def _auto_loop() -> None:
    """Run cycles back-to-back until a boundary stop condition fires.

    Every stop condition is evaluated at a cycle boundary, never mid-cycle:
    an in-flight cycle always completes (jobs, review, appeal window,
    payroll, firing/hiring) — that completion IS the safe boundary. The
    budget check is deterministic: the next cycle starts only if
    spent + projected <= cap.
    """
    while True:
        with _auto_lock:
            stop_requested = _auto_state["stop_requested"]
            pending_reason = _auto_state["pending_stop_reason"]
            pause_requested = _auto_state["pause_requested"]
            spent = _auto_state["spent_credits"]
            cap = _auto_state["budget_cap_credits"]
            last_actual = _auto_state["last_cycle_spend_credits"]
            cycles_done = _auto_state["cycles_completed"]
        if stop_requested or floor_mode.get_mode() != "auto":
            reason = pending_reason or (
                "switched_to_manual" if floor_mode.get_mode() != "auto" else "human_stop")
            _auto_finish("stopped", "auto.stopped", {
                "reason": reason, "cycles_completed": cycles_done,
                "spent_credits": spent, "budget_cap_credits": cap})
            return
        if pause_requested:
            _auto_finish("paused", "auto.paused", {
                "cycles_completed": cycles_done, "spent_credits": spent,
                "budget_cap_credits": cap,
                "note": "takes effect at a cycle boundary; the in-flight cycle completed"})
            return
        cycle_no = _next_cycle_no()
        projected = _projected_cycle_spend(cycle_no, last_actual)
        if cap is not None and spent + projected > cap:
            _auto_finish("stopped", "auto.stopped", {
                "reason": "budget_cap_reached", "cycles_completed": cycles_done,
                "spent_credits": spent, "budget_cap_credits": cap,
                "next_cycle": cycle_no, "projected_next_cycle_credits": projected})
            return
        with _auto_lock:
            _auto_state["current_cycle"] = cycle_no
        _emit_api_event("auto.cycle_started", {
            "cycle_no": cycle_no, "projected_spend_credits": projected,
            "spent_credits": spent, "budget_cap_credits": cap})
        _shift_lock.acquire()
        _shift_state["running"] = True
        try:
            summary = floor_engine.run_shift(cycles=1)
            _shift_state["last_summary"] = summary
            _shift_state["last_error"] = None
        except Exception as exc:  # noqa: BLE001 — surfaced via state + event
            _shift_state["last_error"] = f"{type(exc).__name__}: {exc}"
            with _auto_lock:
                _auto_state["last_error"] = _shift_state["last_error"]
                spent = _auto_state["spent_credits"]
                cycles_done = _auto_state["cycles_completed"]
            reason = ("switched_to_manual" if floor_mode.get_mode() != "auto"
                      else "error")
            _auto_finish("stopped", "auto.stopped", {
                "reason": reason, "error": _shift_state["last_error"],
                "cycles_completed": cycles_done, "spent_credits": spent,
                "budget_cap_credits": cap})
            return
        finally:
            _shift_state["running"] = False
            _shift_lock.release()
        actual = _cycle_spend_credits(cycle_no)
        with _auto_lock:
            _auto_state["spent_credits"] += actual
            _auto_state["last_cycle_spend_credits"] = actual
            _auto_state["cycles_completed"] += 1
            _auto_state["current_cycle"] = None


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
        "targets": {kind: _probe(url) for kind, (url, _d) in TARGETS.items()},
        "shift_running": _shift_state["running"],
        "economy_source": floor_engine.ECONOMY_SOURCE,
        "mode": floor_mode.get_mode(),
        "auto_run": _auto_public(),
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
            dept_title = job["title"]
            if dept_title.startswith("Audit: "):
                dept_title = dept_title[len("Audit: "):]
            dept, dept_label = _TITLE_DEPT.get(dept_title, ("support", "Support"))
            job["department"] = dept
            job["department_label"] = dept_label
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
    if _auto_public()["status"] == "running":
        raise HTTPException(status_code=409,
                            detail="auto-run is active; pause or stop it first")
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
    if _shift_state["running"] or _auto_public()["status"] == "running":
        raise HTTPException(status_code=409, detail="cannot reset while a shift is running")
    floor = floor_engine.reset_floor()
    # Reset every department workplace (each is its own system of record).
    resets = {kind: _reset_target(url, d) for kind, (url, d) in TARGETS.items()}
    return {"floor": floor, "ticketdesk": resets["ticketdesk"],
            "stockroom": resets["stockroom"], "targets": resets}


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
# floor mode + auto-run controls (docs/MODES.md)
# ---------------------------------------------------------------------------

async def _json_body(request: Request) -> dict:
    try:
        body = await request.json()
        return body if isinstance(body, dict) else {}
    except Exception:  # noqa: BLE001 — empty body is fine for pause/stop
        return {}


@app.get("/mode")
def mode_get() -> dict:
    return _mode_public()


@app.post("/mode")
async def mode_set(request: Request) -> dict:
    body = await _json_body(request)
    by = str(body.get("by", "human"))
    try:
        previous, new = floor_mode.set_mode(str(body.get("mode", "")), by=by)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if new != previous:
        _emit_api_event("mode.changed", {"mode": new, "previous_mode": previous, "by": by})
        if new == "manual":
            # Stop auto-approvals immediately (the gate reads the mode per
            # call) and ask the loop to stop at the next cycle boundary.
            with _auto_lock:
                if _auto_state["status"] == "running":
                    _auto_state["stop_requested"] = True
                    _auto_state["pending_stop_reason"] = "switched_to_manual"
    return _mode_public()


@app.get("/auto/status")
def auto_status() -> dict:
    return _auto_public()


@app.post("/auto/start")
async def auto_start(request: Request) -> dict:
    """Start (or resume) the auto-run loop. Idempotent while running.

    Starting implies the human trusts the floor: it switches the mode to
    'auto' (emitting mode.changed) if it isn't already. A fresh run needs
    budget_cap_credits > 0; resuming a paused run keeps its spend and may
    replace the cap.
    """
    global _auto_thread
    body = await _json_body(request)
    by = str(body.get("by", "human"))
    cap = body.get("budget_cap_credits")
    with _auto_lock:
        status = _auto_state["status"]
        if status == "running":
            return _auto_public()  # idempotent: already running, no-op
        if status == "paused":
            if cap is not None:
                if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                    raise HTTPException(status_code=422,
                                        detail="budget_cap_credits must be a positive int")
                _auto_state["budget_cap_credits"] = cap
            _auto_state["status"] = "running"
            _auto_state["pause_requested"] = False
            _auto_state["stop_requested"] = False
            _auto_state["pending_stop_reason"] = None
            _auto_state["stop_reason"] = None
            resumed = True
        else:  # stopped -> fresh run
            if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
                raise HTTPException(
                    status_code=422,
                    detail="budget_cap_credits (positive int) is required to start auto-run")
            _auto_state.update(status="running", budget_cap_credits=cap,
                               spent_credits=0, cycles_completed=0, current_cycle=None,
                               last_cycle_spend_credits=None, stop_reason=None,
                               started_by=by, last_error=None, pause_requested=False,
                               stop_requested=False, pending_stop_reason=None)
            resumed = False
    if floor_mode.get_mode() != "auto":
        previous, _ = floor_mode.set_mode("auto", by=by)
        _emit_api_event("mode.changed", {"mode": "auto", "previous_mode": previous, "by": by})
    _emit_api_event("auto.started", {"budget_cap_credits": _auto_public()["budget_cap_credits"],
                                     "by": by, "resumed": resumed})
    _auto_thread = threading.Thread(target=_auto_loop, daemon=True)
    _auto_thread.start()
    return _auto_public()


@app.post("/auto/pause")
async def auto_pause(request: Request) -> dict:
    """Request a pause: the loop stops starting new cycles at the next
    cycle boundary (an in-flight cycle completes — the safe boundary)."""
    body = await _json_body(request)
    with _auto_lock:
        if _auto_state["status"] == "running":
            _auto_state["pause_requested"] = True
            _auto_state["paused_by"] = str(body.get("by", "human"))
    return _auto_public()


@app.post("/auto/stop")
async def auto_stop(request: Request) -> dict:
    """Request a stop: takes effect at the next cycle boundary (or
    immediately if the loop is paused and no cycle is in flight)."""
    body = await _json_body(request)
    by = str(body.get("by", "human"))
    finalize_now = False
    with _auto_lock:
        if _auto_state["status"] == "running":
            _auto_state["stop_requested"] = True
            _auto_state["pending_stop_reason"] = "human_stop"
        elif _auto_state["status"] == "paused":
            finalize_now = True
    if finalize_now:
        _auto_finish("stopped", "auto.stopped", {
            "reason": "human_stop", "by": by,
            "cycles_completed": _auto_public()["cycles_completed"],
            "spent_credits": _auto_public()["spent_credits"],
            "budget_cap_credits": _auto_public()["budget_cap_credits"]})
    return _auto_public()


# ---------------------------------------------------------------------------
# static UI (mounted last so API routes win)
# ---------------------------------------------------------------------------

_ui_dir = REPO_ROOT / "ui"
if (_ui_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(_ui_dir), html=True), name="ui")
