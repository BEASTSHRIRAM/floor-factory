"""FALLBACK SHIM — only used if the real ``economy`` package cannot be imported.

The engine codes against the economy contract (economy.db + economy.core).
If that package is missing/broken at integration time, this module provides
a compact, self-contained implementation of the same subset of functions
the engine calls, with the same semantics where it matters:

* append-only ledger with a balance_after chain,
* award formula  score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence,
* payment ONLY through settle (primary accept or appeal uphold),
* reputation deltas: accept +4, reject -6, appeal upheld: worker +3 / Reviewer A -8,
* cycle_close: salary running costs, firing after 2 consecutive negative
  cycles with >= 1 completed job in the window (2-cycle grace), mutated
  replacement hire (single-dimension mutation).

It is deliberately thinner than economy.core (no ledger triggers, no
verify_ledger_chain helper, simplified roster). If you are reading this in
production, the real economy package failed to import — check there first.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REVIEW_FEE = 10
APPEAL_FEE = 15
REP_ACCEPT = 4.0
REP_REJECT = -6.0
REP_APPEAL_WORKER = 3.0
REP_APPEAL_REVIEWER_A = -8.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'worker', persona_prompt TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT 'openai/gpt-oss-120b', tier TEXT NOT NULL DEFAULT 'junior',
    base_salary_credits INTEGER NOT NULL DEFAULT 0, risk_appetite REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'active', parent_agent_id INTEGER, generation INTEGER NOT NULL DEFAULT 1,
    mutation_note TEXT, reputation REAL NOT NULL DEFAULT 50.0, hired_cycle INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, fired_at TEXT, fire_reason TEXT);
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, system_id INTEGER, source TEXT NOT NULL DEFAULT 'seeded',
    title TEXT NOT NULL, brief TEXT NOT NULL DEFAULT '', acceptance_criteria TEXT NOT NULL DEFAULT '[]',
    budget_credits INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    requires_human_merge INTEGER NOT NULL DEFAULT 0, created_cycle INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bids (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, agent_id INTEGER NOT NULL,
    price_credits INTEGER NOT NULL, confidence REAL NOT NULL, rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, UNIQUE (job_id, agent_id));
CREATE TABLE IF NOT EXISTS work_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, agent_id INTEGER NOT NULL,
    agreed_price_credits INTEGER NOT NULL, plan TEXT, status TEXT NOT NULL DEFAULT 'working',
    cycle_no INTEGER NOT NULL DEFAULT 0, started_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id INTEGER NOT NULL, tool_name TEXT NOT NULL,
    args_json TEXT NOT NULL DEFAULT '{}', effect TEXT NOT NULL DEFAULT 'read', confirmation_id TEXT,
    confirmed_by TEXT, confirmed_at TEXT, status TEXT NOT NULL DEFAULT 'proposed',
    result_summary TEXT, error TEXT, created_at TEXT NOT NULL,
    CHECK (NOT (effect = 'write' AND status = 'executed') OR confirmation_id IS NOT NULL));
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id INTEGER NOT NULL, reviewer_agent_id INTEGER NOT NULL,
    kind TEXT NOT NULL DEFAULT 'primary', severity TEXT NOT NULL DEFAULT 'none',
    verdict TEXT NOT NULL, rationale TEXT NOT NULL DEFAULT '', findings_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS appeals (
    id INTEGER PRIMARY KEY AUTOINCREMENT, work_order_id INTEGER NOT NULL UNIQUE, agent_id INTEGER NOT NULL,
    fee_credits INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', appeal_review_id INTEGER,
    created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL, kind TEXT NOT NULL,
    amount_credits INTEGER NOT NULL, balance_after INTEGER NOT NULL, ref_type TEXT, ref_id INTEGER,
    cycle_no INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payroll_cycles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_no INTEGER NOT NULL UNIQUE,
    opened_at TEXT NOT NULL, closed_at TEXT, summary_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS reputation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id INTEGER NOT NULL, delta REAL NOT NULL,
    reason TEXT NOT NULL, ref_type TEXT, ref_id INTEGER, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id INTEGER, type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_db_path() -> Path:
    env = os.environ.get("FLOOR_DB")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "floor.db"


def get_conn(db_path=None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db(db_path=None, reset: bool = False) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    if reset and str(path) != ":memory:" and path.exists():
        path.unlink()
        for suffix in ("-wal", "-shm"):
            side = Path(str(path) + suffix)
            if side.exists():
                side.unlink()
    conn = get_conn(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def emit_event(conn, type, payload=None) -> int:  # noqa: A002 — matches economy.db
    cur = conn.execute(
        "INSERT INTO events (type, payload_json, created_at) VALUES (?, ?, ?)",
        (type, json.dumps(payload or {}), now_iso()),
    )
    seq = cur.lastrowid
    conn.execute("UPDATE events SET id = ? WHERE seq = ?", (seq, seq))
    return seq


# --- roster -----------------------------------------------------------------

_ROSTER = [
    ("Maya", "worker", "senior", "openai/gpt-oss-120b", 30, 0.40, 82.0,
     "Careful senior. Verifies every ticket after acting, always leaves a comment."),
    ("Ravi", "worker", "senior", "openai/gpt-oss-120b", 28, 0.50, 74.0,
     "Steady senior. Methodical triage, double-checks duplicates before merging."),
    ("Pixel", "worker", "junior", "openai/gpt-oss-20b", 14, 0.65, 61.0,
     "Fast, cheap junior. High volume, occasionally shallow verification."),
    ("Chotu", "worker", "junior", "openai/gpt-oss-20b", 12, 0.90, 45.0,
     "SLOPPY. Trait: skips_comments — rushes jobs, skips comments and skips verification steps."),
    ("Baron", "worker", "veteran", "openai/gpt-oss-120b", 90, 0.20, 70.0,
     "Expensive veteran prima donna. Bids near the cap, takes few jobs, high running cost."),
    ("Iris", "reviewer", "senior", "openai/gpt-oss-120b", 20, 0.30, 88.0,
     "Strict reviewer. Grades work against acceptance criteria, P0-P3 severity."),
    ("Omar", "reviewer", "senior", "openai/gpt-oss-120b", 18, 0.45, 76.0,
     "Independent reviewer. Used as the blind second reviewer on appeals."),
]


def create_agent(conn, name, *, role="worker", persona_prompt="", model="openai/gpt-oss-120b",
                 tier="junior", base_salary_credits=0, risk_appetite=0.5, reputation=50.0,
                 parent_agent_id=None, generation=1, mutation_note=None, hired_cycle=0) -> int:
    reputation = max(0.0, min(100.0, float(reputation)))
    with conn:
        cur = conn.execute(
            """INSERT INTO agents (name, role, persona_prompt, model, tier, base_salary_credits,
                   risk_appetite, status, parent_agent_id, generation, mutation_note, reputation,
                   hired_cycle, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)""",
            (name, role, persona_prompt, model, tier, int(base_salary_credits),
             float(risk_appetite), parent_agent_id, int(generation), mutation_note,
             reputation, int(hired_cycle), now_iso()),
        )
        agent_id = cur.lastrowid
        if reputation != 0.0:
            conn.execute(
                "INSERT INTO reputation_events (agent_id, delta, reason, ref_type, ref_id, created_at)"
                " VALUES (?, ?, 'initial_seed', 'agent', ?, ?)",
                (agent_id, reputation, agent_id, now_iso()),
            )
    return agent_id


def seed_roster(conn, cycle_no: int = 0) -> list[dict]:
    existing = list_agents(conn)
    if existing:
        return existing
    for (name, role, tier, model, salary, risk, rep, persona) in _ROSTER:
        create_agent(conn, name, role=role, persona_prompt=persona, model=model, tier=tier,
                     base_salary_credits=salary, risk_appetite=risk, reputation=rep,
                     hired_cycle=cycle_no)
    agents = list_agents(conn)
    with conn:
        emit_event(conn, "roster.seeded", {"agents": [a["name"] for a in agents]})
    conn.commit()
    return agents


def get_agent(conn, agent_id):
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return dict(row) if row else None


def list_agents(conn, status=None) -> list[dict]:
    if status:
        rows = conn.execute("SELECT * FROM agents WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT * FROM agents ORDER BY id")
    return [dict(r) for r in rows]


# --- ledger / reputation ------------------------------------------------------

def ledger_write(conn, agent_id, kind, amount_credits, *, ref_type=None, ref_id=None,
                 cycle_no=0, note="") -> int:
    if not isinstance(amount_credits, int) or isinstance(amount_credits, bool):
        raise TypeError("amount_credits must be int credits")
    with conn:
        row = conn.execute(
            "SELECT balance_after FROM ledger WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
            (agent_id,)).fetchone()
        prev = row["balance_after"] if row else 0
        cur = conn.execute(
            """INSERT INTO ledger (agent_id, kind, amount_credits, balance_after, ref_type,
                   ref_id, cycle_no, note, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, kind, amount_credits, prev + amount_credits, ref_type, ref_id,
             int(cycle_no), note, now_iso()),
        )
        return cur.lastrowid


def apply_reputation(conn, agent_id, delta, reason, *, ref_type=None, ref_id=None) -> float:
    with conn:
        row = conn.execute("SELECT reputation FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            raise ValueError(f"no agent {agent_id}")
        new_rep = max(0.0, min(100.0, row["reputation"] + float(delta)))
        conn.execute(
            "INSERT INTO reputation_events (agent_id, delta, reason, ref_type, ref_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, float(delta), reason, ref_type, ref_id, now_iso()),
        )
        conn.execute("UPDATE agents SET reputation = ? WHERE id = ?", (new_rep, agent_id))
    return new_rep


# --- jobs / bids / award ------------------------------------------------------

def create_job(conn, title, brief, budget_credits, *, acceptance_criteria=None, system_id=None,
               source="seeded", requires_human_merge=False, created_cycle=0) -> int:
    with conn:
        cur = conn.execute(
            """INSERT INTO jobs (system_id, source, title, brief, acceptance_criteria, budget_credits,
                   status, requires_human_merge, created_cycle, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            (system_id, source, title, brief, json.dumps(acceptance_criteria or []),
             int(budget_credits), 1 if requires_human_merge else 0, int(created_cycle), now_iso()),
        )
        job_id = cur.lastrowid
        emit_event(conn, "job.posted", {"job_id": job_id, "title": title,
                                        "budget_credits": int(budget_credits)})
    conn.commit()
    return job_id


def get_job(conn, job_id):
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    job = dict(row)
    job["acceptance_criteria"] = json.loads(job["acceptance_criteria"] or "[]")
    return job


def suggest_bid(conn, agent_id, job_id):
    agent, job = get_agent(conn, agent_id), get_job(conn, job_id)
    if agent is None or job is None:
        raise ValueError("agent or job not found")
    cap = job["budget_credits"]
    salary_pressure = min(agent["base_salary_credits"] / max(cap, 1), 0.45)
    fraction = 0.55 + 0.25 * agent["risk_appetite"] + salary_pressure
    price = max(1, min(cap, round(cap * fraction)))
    confidence = round(max(0.05, min(0.99, agent["reputation"] / 100.0
                                     + 0.1 * (agent["risk_appetite"] - 0.5))), 2)
    rationale = (f"{agent['name']}: price {price}/{cap} from salary pressure "
                 f"{salary_pressure:.2f} + risk {agent['risk_appetite']:.2f}")
    return price, confidence, rationale


def place_bid(conn, job_id, agent_id, price_credits, confidence, rationale="") -> int:
    agent = get_agent(conn, agent_id)
    if agent is None or agent["status"] != "active" or agent["role"] != "worker":
        raise ValueError("only active workers may bid")
    job = get_job(conn, job_id)
    if job is None or job["status"] not in ("open", "bidding"):
        raise ValueError("job not open for bids")
    with conn:
        cur = conn.execute(
            "INSERT INTO bids (job_id, agent_id, price_credits, confidence, rationale, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, agent_id, int(price_credits), float(confidence), rationale, now_iso()),
        )
        bid_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'bidding' WHERE id = ? AND status = 'open'", (job_id,))
        emit_event(conn, "bid.placed", {"job_id": job_id, "agent_id": agent_id,
                                        "price_credits": int(price_credits),
                                        "confidence": float(confidence)})
    conn.commit()
    return bid_id


def bid_score(price_credits, cap_credits, reputation, confidence) -> float:
    return (0.5 * (1 - price_credits / cap_credits)
            + 0.3 * (reputation / 100.0) + 0.2 * float(confidence))


def award_job(conn, job_id) -> int:
    job = get_job(conn, job_id)
    if job is None or job["status"] not in ("open", "bidding"):
        raise ValueError("job cannot be awarded")
    bids = conn.execute(
        "SELECT b.*, a.reputation, a.status AS agent_status FROM bids b"
        " JOIN agents a ON a.id = b.agent_id WHERE b.job_id = ?", (job_id,)).fetchall()
    scored = []
    for b in bids:
        if b["agent_status"] != "active":
            continue
        s = bid_score(b["price_credits"], job["budget_credits"], b["reputation"], b["confidence"])
        scored.append((s, -b["price_credits"], -b["id"], b))
    if not scored:
        raise ValueError("no bids from active agents")
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    score, _, _, winner = scored[0]
    with conn:
        cur = conn.execute(
            "INSERT INTO work_orders (job_id, agent_id, agreed_price_credits, status, cycle_no, started_at)"
            " VALUES (?, ?, ?, 'working', ?, ?)",
            (job_id, winner["agent_id"], winner["price_credits"], job["created_cycle"], now_iso()),
        )
        wo_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'awarded' WHERE id = ?", (job_id,))
        emit_event(conn, "job.awarded", {"job_id": job_id, "work_order_id": wo_id,
                                         "agent_id": winner["agent_id"],
                                         "price_credits": winner["price_credits"],
                                         "score": round(score, 4)})
    conn.commit()
    return wo_id


# --- execution transcript / review / settle / appeal -------------------------

def record_tool_call(conn, work_order_id, tool_name, *, args=None, effect="read",
                     confirmation_id=None, confirmed_by=None, status="executed",
                     result_summary="", error=None) -> int:
    if effect == "write" and status == "executed" and not confirmation_id:
        raise ValueError("write tool calls require a confirmation_id to be executed")
    with conn:
        cur = conn.execute(
            """INSERT INTO tool_calls (work_order_id, tool_name, args_json, effect, confirmation_id,
                   confirmed_by, confirmed_at, status, result_summary, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (work_order_id, tool_name, json.dumps(args or {}), effect, confirmation_id,
             confirmed_by, now_iso() if confirmation_id else None, status,
             result_summary, error, now_iso()),
        )
        return cur.lastrowid


def _get_wo(conn, work_order_id) -> dict:
    row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
    if row is None:
        raise ValueError(f"no work_order {work_order_id}")
    return dict(row)


def submit_work(conn, work_order_id) -> None:
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "working":
        raise ValueError(f"work_order {work_order_id} is {wo['status']}, cannot submit")
    with conn:
        conn.execute("UPDATE work_orders SET status = 'submitted' WHERE id = ?", (work_order_id,))
        conn.execute("UPDATE jobs SET status = 'in_review' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "work.submitted", {"work_order_id": work_order_id, "job_id": wo["job_id"]})
    conn.commit()


def settle(conn, work_order_id, *, via="primary") -> int:
    wo = _get_wo(conn, work_order_id)
    if wo["status"] in ("accepted", "appeal_accepted"):
        raise ValueError("already settled")
    if via == "primary" and wo["status"] != "submitted":
        raise ValueError("primary settle requires a submitted work_order")
    if via == "appeal" and wo["status"] != "rejected":
        raise ValueError("appeal settle requires a rejected work_order")
    ledger_id = ledger_write(conn, wo["agent_id"], "earning", wo["agreed_price_credits"],
                             ref_type="work_order", ref_id=work_order_id, cycle_no=wo["cycle_no"],
                             note=f"payment for job {wo['job_id']} via {via} accept")
    apply_reputation(conn, wo["agent_id"], REP_ACCEPT if via == "primary" else REP_APPEAL_WORKER,
                     "accept" if via == "primary" else "appeal_upheld",
                     ref_type="work_order", ref_id=work_order_id)
    with conn:
        conn.execute("UPDATE work_orders SET status = ?, finished_at = ? WHERE id = ?",
                     ("accepted" if via == "primary" else "appeal_accepted", now_iso(), work_order_id))
        conn.execute("UPDATE jobs SET status = 'paid' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "payment.made", {"work_order_id": work_order_id, "agent_id": wo["agent_id"],
                                          "amount_credits": wo["agreed_price_credits"], "via": via})
    conn.commit()
    return ledger_id


def review_work(conn, work_order_id, reviewer_agent_id, verdict, *, severity="none",
                rationale="", findings=None) -> int:
    reviewer = get_agent(conn, reviewer_agent_id)
    if reviewer is None or reviewer["role"] != "reviewer" or reviewer["status"] != "active":
        raise ValueError("reviewer must be an active reviewer agent")
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "submitted":
        raise ValueError("work_order not submitted")
    with conn:
        cur = conn.execute(
            "INSERT INTO reviews (work_order_id, reviewer_agent_id, kind, severity, verdict,"
            " rationale, findings_json, created_at) VALUES (?, ?, 'primary', ?, ?, ?, ?, ?)",
            (work_order_id, reviewer_agent_id, severity, verdict, rationale,
             json.dumps(findings or []), now_iso()),
        )
        review_id = cur.lastrowid
        emit_event(conn, "review.completed", {"work_order_id": work_order_id, "review_id": review_id,
                                              "verdict": verdict, "severity": severity, "kind": "primary"})
    conn.commit()
    ledger_write(conn, reviewer_agent_id, "review_fee", REVIEW_FEE, ref_type="review",
                 ref_id=review_id, cycle_no=wo["cycle_no"], note="primary review fee")
    if verdict == "accept":
        settle(conn, work_order_id, via="primary")
    else:
        apply_reputation(conn, wo["agent_id"], REP_REJECT, "reject",
                         ref_type="review", ref_id=review_id)
        with conn:
            conn.execute("UPDATE work_orders SET status = 'rejected', finished_at = ? WHERE id = ?",
                         (now_iso(), work_order_id))
            conn.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (wo["job_id"],))
        conn.commit()
    return review_id


def file_appeal(conn, work_order_id, fee_credits=APPEAL_FEE) -> int:
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "rejected":
        raise ValueError("only rejected work can be appealed")
    with conn:
        cur = conn.execute(
            "INSERT INTO appeals (work_order_id, agent_id, fee_credits, status, created_at)"
            " VALUES (?, ?, ?, 'pending', ?)",
            (work_order_id, wo["agent_id"], int(fee_credits), now_iso()),
        )
        appeal_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'appealed' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "appeal.filed", {"work_order_id": work_order_id, "appeal_id": appeal_id,
                                          "fee_credits": int(fee_credits)})
    conn.commit()
    ledger_write(conn, wo["agent_id"], "appeal_fee", -int(fee_credits), ref_type="appeal",
                 ref_id=appeal_id, cycle_no=wo["cycle_no"], note="appeal fee (charged win or lose)")
    return appeal_id


def appeal_review(conn, work_order_id, reviewer_agent_id, verdict, *, severity="none",
                  rationale="", findings=None) -> int:
    reviewer = get_agent(conn, reviewer_agent_id)
    if reviewer is None or reviewer["role"] != "reviewer" or reviewer["status"] != "active":
        raise ValueError("appeal reviewer must be an active reviewer agent")
    appeal = conn.execute("SELECT * FROM appeals WHERE work_order_id = ?",
                          (work_order_id,)).fetchone()
    if appeal is None or appeal["status"] != "pending":
        raise ValueError("no pending appeal")
    primary = conn.execute(
        "SELECT * FROM reviews WHERE work_order_id = ? AND kind = 'primary' ORDER BY id DESC LIMIT 1",
        (work_order_id,)).fetchone()
    if primary is None:
        raise ValueError("no primary review found")
    if primary["reviewer_agent_id"] == reviewer_agent_id:
        raise ValueError("appeal reviewer must differ from the primary reviewer (blind review)")
    wo = _get_wo(conn, work_order_id)
    with conn:
        cur = conn.execute(
            "INSERT INTO reviews (work_order_id, reviewer_agent_id, kind, severity, verdict,"
            " rationale, findings_json, created_at) VALUES (?, ?, 'appeal', ?, ?, ?, ?, ?)",
            (work_order_id, reviewer_agent_id, severity, verdict, rationale,
             json.dumps(findings or []), now_iso()),
        )
        review_id = cur.lastrowid
        conn.execute("UPDATE appeals SET status = ?, appeal_review_id = ? WHERE id = ?",
                     ("upheld" if verdict == "accept" else "denied", review_id, appeal["id"]))
        emit_event(conn, "appeal.decided", {"work_order_id": work_order_id,
                                            "review_id": review_id, "verdict": verdict})
        emit_event(conn, "review.completed", {"work_order_id": work_order_id, "review_id": review_id,
                                              "verdict": verdict, "severity": severity, "kind": "appeal"})
    conn.commit()
    ledger_write(conn, reviewer_agent_id, "review_fee", REVIEW_FEE, ref_type="review",
                 ref_id=review_id, cycle_no=wo["cycle_no"], note="appeal review fee")
    if verdict == "accept":
        apply_reputation(conn, primary["reviewer_agent_id"], REP_APPEAL_REVIEWER_A,
                         "appeal_overturned", ref_type="review", ref_id=review_id)
        settle(conn, work_order_id, via="appeal")
    else:
        with conn:
            conn.execute("UPDATE work_orders SET status = 'appeal_rejected' WHERE id = ?",
                         (work_order_id,))
            conn.execute("UPDATE jobs SET status = 'failed' WHERE id = ?", (wo["job_id"],))
        conn.commit()
    return review_id


# --- payroll ------------------------------------------------------------------

_MUTATION_TRAITS = ["verify-before-acting", "comment-every-action",
                    "double-check-duplicates", "escalate-early"]


def _base_name(name: str) -> str:
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].endswith(".0"):
        try:
            float(parts[1])
            return parts[0]
        except ValueError:
            pass
    return name


def hire_mutated_replacement(conn, parent_agent_id, cycle_no) -> int:
    parent = get_agent(conn, parent_agent_id)
    if parent is None:
        raise ValueError(f"no agent {parent_agent_id}")
    generation = parent["generation"] + 1
    name = f"{_base_name(parent['name'])} {generation}.0"
    persona, model, risk = parent["persona_prompt"], parent["model"], parent["risk_appetite"]
    dimension = (parent["id"] + parent["generation"]) % 3
    if dimension == 0:
        trait = _MUTATION_TRAITS[(parent["generation"] - 1) % len(_MUTATION_TRAITS)]
        persona = f"{persona} Mutation: {trait}."
        note = f"mutation: persona trait — {trait}"
    elif dimension == 1:
        model = "openai/gpt-oss-120b" if model == "openai/gpt-oss-20b" else "openai/gpt-oss-20b"
        note = f"mutation: model — {parent['model']} -> {model}"
    else:
        risk = round(max(0.05, min(0.95, parent["risk_appetite"]
                                   + (0.15 if parent["risk_appetite"] < 0.5 else -0.15))), 2)
        note = f"mutation: risk_appetite — {parent['risk_appetite']:.2f} -> {risk:.2f}"
    new_id = create_agent(conn, name, role=parent["role"], persona_prompt=persona, model=model,
                          tier=parent["tier"], base_salary_credits=parent["base_salary_credits"],
                          risk_appetite=risk, reputation=50.0, parent_agent_id=parent_agent_id,
                          generation=generation, mutation_note=note, hired_cycle=cycle_no)
    with conn:
        emit_event(conn, "agent.hired", {"agent_id": new_id, "name": name,
                                         "parent_agent_id": parent_agent_id,
                                         "generation": generation, "mutation_note": note})
    conn.commit()
    return new_id


def cycle_close(conn, cycle_no=None, *, hire_replacements=True) -> dict:
    if cycle_no is None:
        row = conn.execute("SELECT COALESCE(MAX(cycle_no), 0) + 1 AS n FROM payroll_cycles").fetchone()
        cycle_no = row["n"]
    cycle_no = int(cycle_no)
    if conn.execute("SELECT 1 FROM payroll_cycles WHERE cycle_no = ?", (cycle_no,)).fetchone():
        raise ValueError(f"cycle {cycle_no} already exists")
    with conn:
        conn.execute("INSERT INTO payroll_cycles (cycle_no, opened_at) VALUES (?, ?)",
                     (cycle_no, now_iso()))
    conn.commit()
    per_agent: dict[int, dict] = {}
    for agent in list_agents(conn, status="active"):
        charged = 0
        if agent["base_salary_credits"] > 0:
            ledger_write(conn, agent["id"], "running_cost", -agent["base_salary_credits"],
                         ref_type="payroll_cycle", ref_id=cycle_no, cycle_no=cycle_no,
                         note=f"running cost cycle {cycle_no}")
            charged = agent["base_salary_credits"]
        net = conn.execute(
            "SELECT COALESCE(SUM(amount_credits), 0) AS net FROM ledger WHERE agent_id = ? AND cycle_no = ?",
            (agent["id"], cycle_no)).fetchone()["net"]
        completed = conn.execute(
            "SELECT COUNT(*) AS n FROM work_orders WHERE agent_id = ? AND cycle_no = ?"
            " AND status IN ('accepted', 'appeal_accepted')", (agent["id"], cycle_no)).fetchone()["n"]
        per_agent[agent["id"]] = {"net": net, "completed": completed, "charged": charged}
    prev = conn.execute(
        "SELECT summary_json FROM payroll_cycles WHERE cycle_no = ? AND closed_at IS NOT NULL",
        (cycle_no - 1,)).fetchone()
    prev_agents = json.loads(prev["summary_json"] or "{}").get("agents", {}) if prev else {}
    fired, hired = [], []
    for agent in list_agents(conn, status="active"):
        if agent["role"] != "worker":
            continue
        cur = per_agent.get(agent["id"])
        prv = prev_agents.get(str(agent["id"])) or prev_agents.get(agent["id"])
        if cur is None or prv is None:
            continue
        if cycle_no - agent["hired_cycle"] < 2:
            continue
        if cur["net"] < 0 and prv["net"] < 0 and cur["completed"] + prv["completed"] >= 1:
            reason = (f"PinkSlip: negative net in cycles {cycle_no - 1} and {cycle_no} "
                      f"({prv['net']} + {cur['net']} credits) with "
                      f"{cur['completed'] + prv['completed']} completed job(s) in window")
            with conn:
                conn.execute("UPDATE agents SET status = 'fired', fired_at = ?, fire_reason = ? WHERE id = ?",
                             (now_iso(), reason, agent["id"]))
                emit_event(conn, "agent.fired", {"agent_id": agent["id"], "name": agent["name"],
                                                 "reason": reason, "cycle_no": cycle_no,
                                                 "event": "PinkSlip"})
            conn.commit()
            fired.append(agent["id"])
            if hire_replacements:
                hired.append(hire_mutated_replacement(conn, agent["id"], cycle_no))
    summary = {"cycle_no": cycle_no, "agents": {str(k): v for k, v in per_agent.items()},
               "fired": fired, "hired": hired}
    with conn:
        conn.execute("UPDATE payroll_cycles SET closed_at = ?, summary_json = ? WHERE cycle_no = ?",
                     (now_iso(), json.dumps(summary), cycle_no))
        emit_event(conn, "cycle.closed", {"cycle_no": cycle_no, "fired": fired, "hired": hired})
    conn.commit()
    return summary
