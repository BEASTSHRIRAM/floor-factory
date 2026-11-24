"""THE FLOOR — economy core.

Deterministic money/reputation/payroll logic. NO LLM imports — money math is
code, not LLM (ARCHITECTURE §1, §5). All money is integer credits.

Award formula (BRIEF, visible in UI):
    score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence
    (confidence is 0..1)

Reputation deltas (ARCHITECTURE §5 inv. 7):
    accept +4 · reject -6 · appeal upheld: worker +3, Reviewer A -8
"""

from __future__ import annotations

import json
import sqlite3

from .db import emit_event, now_iso

__all__ = [
    "REVIEW_FEE", "APPEAL_FEE",
    "REP_ACCEPT", "REP_REJECT", "REP_APPEAL_WORKER", "REP_APPEAL_REVIEWER_A",
    "seed_roster", "create_agent", "get_agent", "list_agents",
    "ledger_write", "get_balance", "verify_ledger_chain", "apply_reputation",
    "create_job", "get_job", "suggest_bid", "place_bid", "bid_score", "award_job",
    "record_tool_call", "submit_work", "review_work", "settle",
    "file_appeal", "appeal_review",
    "cycle_close", "hire_mutated_replacement",
]

REVIEW_FEE = 10          # credits paid to a reviewer per completed review
APPEAL_FEE = 15          # credits charged to a worker to file an appeal (win or lose)
REP_ACCEPT = 4.0
REP_REJECT = -6.0
REP_APPEAL_WORKER = 3.0
REP_APPEAL_REVIEWER_A = -8.0

PAID_WO_STATUSES = ("accepted", "appeal_accepted")


# --------------------------------------------------------------------------
# Agents / roster
# --------------------------------------------------------------------------

# name, role, tier, model, salary/cycle, risk, starting reputation, persona
_ROSTER = [
    ("Maya", "worker", "senior", "openai/gpt-oss-120b", 30, 0.40, 82.0,
     "Careful senior. Verifies every ticket after acting, always leaves a comment."),
    ("Ravi", "worker", "senior", "openai/gpt-oss-120b", 28, 0.50, 74.0,
     "Steady senior. Methodical triage, double-checks duplicates before merging."),
    ("Pixel", "worker", "junior", "openai/gpt-oss-20b", 14, 0.65, 61.0,
     "Fast, cheap junior. High volume, occasionally shallow verification."),
    ("Chotu", "worker", "junior", "openai/gpt-oss-20b", 12, 0.90, 45.0,
     "SLOPPY. Trait: skips_comments — rushes jobs, skips comments and skips "
     "verification steps. Cheap and confident, often wrong."),
    ("Baron", "worker", "veteran", "openai/gpt-oss-120b", 90, 0.20, 70.0,
     "Expensive veteran prima donna. Bids near the cap, takes few jobs, "
     "high running cost, low output."),
    ("Iris", "reviewer", "senior", "openai/gpt-oss-120b", 20, 0.30, 88.0,
     "Strict reviewer. Grades work against acceptance criteria, P0-P3 severity."),
    ("Omar", "reviewer", "senior", "openai/gpt-oss-120b", 18, 0.45, 76.0,
     "Independent reviewer. Used as the blind second reviewer on appeals."),
]


def create_agent(conn: sqlite3.Connection, name: str, *, role: str = "worker",
                 persona_prompt: str = "", model: str = "openai/gpt-oss-120b",
                 tier: str = "junior", base_salary_credits: int = 0,
                 risk_appetite: float = 0.5, reputation: float = 50.0,
                 parent_agent_id: int | None = None, generation: int = 1,
                 mutation_note: str | None = None, hired_cycle: int = 0) -> int:
    """Insert an agent + its initial reputation event. Returns agent id."""
    reputation = max(0.0, min(100.0, float(reputation)))
    with conn:
        cur = conn.execute(
            """INSERT INTO agents (name, role, persona_prompt, model, tier,
                   base_salary_credits, risk_appetite, status, parent_agent_id,
                   generation, mutation_note, reputation, hired_cycle, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)""",
            (name, role, persona_prompt, model, tier, int(base_salary_credits),
             float(risk_appetite), parent_agent_id, int(generation), mutation_note,
             reputation, int(hired_cycle), now_iso()),
        )
        agent_id = cur.lastrowid
        if reputation != 0.0:
            conn.execute(
                """INSERT INTO reputation_events (agent_id, delta, reason, ref_type, ref_id, created_at)
                   VALUES (?, ?, 'initial_seed', 'agent', ?, ?)""",
                (agent_id, reputation, agent_id, now_iso()),
            )
    return agent_id


def seed_roster(conn: sqlite3.Connection, cycle_no: int = 0) -> list[dict]:
    """Seed the 5 workers + 2 reviewers. Idempotent: returns existing roster if present."""
    existing = list_agents(conn)
    if existing:
        return existing
    for (name, role, tier, model, salary, risk, rep, persona) in _ROSTER:
        create_agent(conn, name, role=role, persona_prompt=persona, model=model,
                     tier=tier, base_salary_credits=salary, risk_appetite=risk,
                     reputation=rep, hired_cycle=cycle_no)
    agents = list_agents(conn)
    with conn:
        emit_event(conn, "roster.seeded", {"agents": [a["name"] for a in agents]})
    conn.commit()
    return agents


def get_agent(conn: sqlite3.Connection, agent_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    return dict(row) if row else None


def list_agents(conn: sqlite3.Connection, status: str | None = None) -> list[dict]:
    if status:
        rows = conn.execute("SELECT * FROM agents WHERE status = ? ORDER BY id", (status,))
    else:
        rows = conn.execute("SELECT * FROM agents ORDER BY id")
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Ledger (append-only, single writer) + reputation
# --------------------------------------------------------------------------

def ledger_write(conn: sqlite3.Connection, agent_id: int, kind: str, amount_credits: int,
                 *, ref_type: str | None = None, ref_id: int | None = None,
                 cycle_no: int = 0, note: str = "") -> int:
    """Append one ledger row, enforcing the balance_after chain. Returns ledger id.

    The chain check happens inside the same transaction as the insert:
    balance_after must equal the agent's previous balance_after + amount.
    """
    if not isinstance(amount_credits, int) or isinstance(amount_credits, bool):
        raise TypeError("amount_credits must be int credits (no floats near the ledger)")
    with conn:
        row = conn.execute(
            "SELECT balance_after FROM ledger WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
            (agent_id,),
        ).fetchone()
        prev = row["balance_after"] if row else 0
        balance_after = prev + amount_credits
        cur = conn.execute(
            """INSERT INTO ledger (agent_id, kind, amount_credits, balance_after,
                   ref_type, ref_id, cycle_no, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, kind, amount_credits, balance_after, ref_type, ref_id,
             int(cycle_no), note, now_iso()),
        )
        return cur.lastrowid


def get_balance(conn: sqlite3.Connection, agent_id: int) -> int:
    row = conn.execute(
        "SELECT balance_after FROM ledger WHERE agent_id = ? ORDER BY id DESC LIMIT 1",
        (agent_id,),
    ).fetchone()
    return row["balance_after"] if row else 0


def verify_ledger_chain(conn: sqlite3.Connection, agent_id: int) -> bool:
    """Recompute the agent's chain from scratch; True iff every balance_after matches."""
    running = 0
    for row in conn.execute(
        "SELECT amount_credits, balance_after FROM ledger WHERE agent_id = ? ORDER BY id",
        (agent_id,),
    ):
        running += row["amount_credits"]
        if row["balance_after"] != running:
            return False
    return True


def apply_reputation(conn: sqlite3.Connection, agent_id: int, delta: float, reason: str,
                     *, ref_type: str | None = None, ref_id: int | None = None) -> float:
    """Apply a reputation delta (clamped 0..100), record the event, update the cache."""
    with conn:
        row = conn.execute("SELECT reputation FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            raise ValueError(f"no agent {agent_id}")
        new_rep = max(0.0, min(100.0, row["reputation"] + float(delta)))
        conn.execute(
            """INSERT INTO reputation_events (agent_id, delta, reason, ref_type, ref_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, float(delta), reason, ref_type, ref_id, now_iso()),
        )
        conn.execute("UPDATE agents SET reputation = ? WHERE id = ?", (new_rep, agent_id))
    return new_rep


# --------------------------------------------------------------------------
# Jobs, bids, award
# --------------------------------------------------------------------------

def create_job(conn: sqlite3.Connection, title: str, brief: str, budget_credits: int,
               *, acceptance_criteria: list | None = None, system_id: int | None = None,
               source: str = "seeded", requires_human_merge: bool = False,
               created_cycle: int = 0) -> int:
    """Create a job in status 'open'. Returns job id."""
    if int(budget_credits) <= 0:
        raise ValueError("budget_credits must be positive")
    with conn:
        cur = conn.execute(
            """INSERT INTO jobs (system_id, source, title, brief, acceptance_criteria,
                   budget_credits, status, requires_human_merge, created_cycle, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)""",
            (system_id, source, title, brief, json.dumps(acceptance_criteria or []),
             int(budget_credits), 1 if requires_human_merge else 0,
             int(created_cycle), now_iso()),
        )
        job_id = cur.lastrowid
        emit_event(conn, "job.posted",
                   {"job_id": job_id, "title": title, "budget_credits": int(budget_credits)})
    conn.commit()
    return job_id


def get_job(conn: sqlite3.Connection, job_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    job = dict(row)
    job["acceptance_criteria"] = json.loads(job["acceptance_criteria"] or "[]")
    return job


def suggest_bid(conn: sqlite3.Connection, agent_id: int, job_id: int) -> tuple[int, float, str]:
    """Deterministic bid suggestion from an agent's traits. Returns (price, confidence, rationale).

    Expensive/high-salary agents bid near the cap; risk appetite raises price
    slightly and lowers care; reputation drives confidence.
    """
    agent = get_agent(conn, agent_id)
    job = get_job(conn, job_id)
    if agent is None or job is None:
        raise ValueError("agent or job not found")
    cap = job["budget_credits"]
    salary_pressure = min(agent["base_salary_credits"] / max(cap, 1), 0.45)
    fraction = 0.55 + 0.25 * agent["risk_appetite"] + salary_pressure
    price = max(1, min(cap, round(cap * fraction)))
    confidence = round(max(0.05, min(0.99, agent["reputation"] / 100.0
                                      + 0.1 * (agent["risk_appetite"] - 0.5))), 2)
    rationale = (f"{agent['name']}: price {price}/{cap} from salary pressure "
                 f"{salary_pressure:.2f} + risk {agent['risk_appetite']:.2f}; "
                 f"confidence from reputation {agent['reputation']:.0f}")
    return price, confidence, rationale


def place_bid(conn: sqlite3.Connection, job_id: int, agent_id: int, price_credits: int,
              confidence: float, rationale: str = "") -> int:
    """Place a sealed bid. Only active workers may bid, only on open/bidding jobs."""
    agent = get_agent(conn, agent_id)
    if agent is None:
        raise ValueError(f"no agent {agent_id}")
    if agent["status"] != "active":
        raise ValueError(f"agent {agent_id} is {agent['status']} and cannot bid")
    if agent["role"] != "worker":
        raise ValueError("only workers bid")
    job = get_job(conn, job_id)
    if job is None:
        raise ValueError(f"no job {job_id}")
    if job["status"] not in ("open", "bidding"):
        raise ValueError(f"job {job_id} is {job['status']}, not open for bids")
    if not isinstance(price_credits, int) or isinstance(price_credits, bool) or price_credits <= 0:
        raise ValueError("price_credits must be a positive int")
    if not (0.0 <= float(confidence) <= 1.0):
        raise ValueError("confidence must be in 0..1")
    with conn:
        cur = conn.execute(
            """INSERT INTO bids (job_id, agent_id, price_credits, confidence, rationale, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (job_id, agent_id, price_credits, float(confidence), rationale, now_iso()),
        )
        bid_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'bidding' WHERE id = ? AND status = 'open'", (job_id,))
        emit_event(conn, "bid.placed", {"job_id": job_id, "agent_id": agent_id,
                                        "price_credits": price_credits,
                                        "confidence": float(confidence)})
    conn.commit()
    return bid_id


def bid_score(price_credits: int, cap_credits: int, reputation: float, confidence: float) -> float:
    """Award score = 0.5*(1 - price/cap) + 0.3*(reputation/100) + 0.2*confidence."""
    if cap_credits <= 0:
        raise ValueError("cap_credits must be positive")
    return (0.5 * (1 - price_credits / cap_credits)
            + 0.3 * (reputation / 100.0)
            + 0.2 * float(confidence))


def award_job(conn: sqlite3.Connection, job_id: int) -> int:
    """Score all bids, award to the winner, create the work order. Returns work_order id.

    Tie-break: higher score, then lower price, then earlier bid.
    """
    job = get_job(conn, job_id)
    if job is None:
        raise ValueError(f"no job {job_id}")
    if job["status"] not in ("open", "bidding"):
        raise ValueError(f"job {job_id} is {job['status']}, cannot award")
    bids = conn.execute(
        """SELECT b.*, a.reputation, a.status AS agent_status
           FROM bids b JOIN agents a ON a.id = b.agent_id WHERE b.job_id = ?""",
        (job_id,),
    ).fetchall()
    scored = []
    for b in bids:
        if b["agent_status"] != "active":
            continue  # fired agents are inert
        s = bid_score(b["price_credits"], job["budget_credits"], b["reputation"], b["confidence"])
        scored.append((s, -b["price_credits"], -b["id"], b))
    if not scored:
        raise ValueError(f"job {job_id} has no bids from active agents")
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    score, _, _, winner = scored[0]
    with conn:
        cur = conn.execute(
            """INSERT INTO work_orders (job_id, agent_id, agreed_price_credits, status,
                   cycle_no, started_at)
               VALUES (?, ?, ?, 'working', ?, ?)""",
            (job_id, winner["agent_id"], winner["price_credits"],
             job["created_cycle"], now_iso()),
        )
        wo_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'awarded' WHERE id = ?", (job_id,))
        emit_event(conn, "job.awarded", {"job_id": job_id, "work_order_id": wo_id,
                                         "agent_id": winner["agent_id"],
                                         "price_credits": winner["price_credits"],
                                         "score": round(score, 4)})
    conn.commit()
    return wo_id


# --------------------------------------------------------------------------
# Work execution transcript, review, settle, appeal
# --------------------------------------------------------------------------

def record_tool_call(conn: sqlite3.Connection, work_order_id: int, tool_name: str,
                     *, args: dict | None = None, effect: str = "read",
                     confirmation_id: str | None = None, confirmed_by: str | None = None,
                     status: str = "executed", result_summary: str = "",
                     error: str | None = None) -> int:
    """Record one tool call in the audit transcript.

    Defence in depth: a write call may not be recorded as executed without a
    confirmation_id (also a DB CHECK constraint).
    """
    if effect == "write" and status == "executed" and not confirmation_id:
        raise ValueError("write tool calls require a confirmation_id to be executed")
    with conn:
        cur = conn.execute(
            """INSERT INTO tool_calls (work_order_id, tool_name, args_json, effect,
                   confirmation_id, confirmed_by, confirmed_at, status,
                   result_summary, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (work_order_id, tool_name, json.dumps(args or {}), effect, confirmation_id,
             confirmed_by, now_iso() if confirmation_id else None, status,
             result_summary, error, now_iso()),
        )
        return cur.lastrowid


def _get_wo(conn: sqlite3.Connection, work_order_id: int) -> dict:
    row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (work_order_id,)).fetchone()
    if row is None:
        raise ValueError(f"no work_order {work_order_id}")
    return dict(row)


def submit_work(conn: sqlite3.Connection, work_order_id: int) -> None:
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "working":
        raise ValueError(f"work_order {work_order_id} is {wo['status']}, cannot submit")
    with conn:
        conn.execute("UPDATE work_orders SET status = 'submitted' WHERE id = ?", (work_order_id,))
        conn.execute("UPDATE jobs SET status = 'in_review' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "work.submitted", {"work_order_id": work_order_id, "job_id": wo["job_id"]})
    conn.commit()


def settle(conn: sqlite3.Connection, work_order_id: int, *, via: str = "primary") -> int:
    """Pay the worker for an accepted work order. THE only path that creates an
    'earning' ledger row. Returns the ledger row id.

    via='primary' -> reputation +4, work_order 'accepted'
    via='appeal'  -> reputation +3, work_order 'appeal_accepted'
    """
    if via not in ("primary", "appeal"):
        raise ValueError("via must be 'primary' or 'appeal'")
    wo = _get_wo(conn, work_order_id)
    if wo["status"] in PAID_WO_STATUSES:
        raise ValueError(f"work_order {work_order_id} already settled")
    if via == "primary" and wo["status"] != "submitted":
        raise ValueError(f"work_order {work_order_id} is {wo['status']}, cannot settle")
    if via == "appeal" and wo["status"] != "rejected":
        raise ValueError(f"appeal settle requires a rejected work_order, got {wo['status']}")
    ledger_id = ledger_write(
        conn, wo["agent_id"], "earning", wo["agreed_price_credits"],
        ref_type="work_order", ref_id=work_order_id, cycle_no=wo["cycle_no"],
        note=f"payment for job {wo['job_id']} via {via} accept")
    delta = REP_ACCEPT if via == "primary" else REP_APPEAL_WORKER
    apply_reputation(conn, wo["agent_id"], delta,
                     "accept" if via == "primary" else "appeal_upheld",
                     ref_type="work_order", ref_id=work_order_id)
    with conn:
        conn.execute("UPDATE work_orders SET status = ?, finished_at = ? WHERE id = ?",
                     ("accepted" if via == "primary" else "appeal_accepted",
                      now_iso(), work_order_id))
        conn.execute("UPDATE jobs SET status = 'paid' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "payment.made", {"work_order_id": work_order_id,
                                          "agent_id": wo["agent_id"],
                                          "amount_credits": wo["agreed_price_credits"],
                                          "via": via})
    conn.commit()
    return ledger_id


def review_work(conn: sqlite3.Connection, work_order_id: int, reviewer_agent_id: int,
                verdict: str, *, severity: str = "none", rationale: str = "",
                findings: list | None = None) -> int:
    """Primary review. Accept -> settle() pays the worker. Reject -> no pay, worker rep -6.
    The reviewer earns a flat REVIEW_FEE. Returns review id."""
    if verdict not in ("accept", "reject"):
        raise ValueError("verdict must be 'accept' or 'reject'")
    if severity not in ("none", "P3", "P2", "P1", "P0"):
        raise ValueError(f"bad severity {severity}")
    reviewer = get_agent(conn, reviewer_agent_id)
    if reviewer is None or reviewer["role"] != "reviewer" or reviewer["status"] != "active":
        raise ValueError("reviewer must be an active reviewer agent")
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "submitted":
        raise ValueError(f"work_order {work_order_id} is {wo['status']}, not submitted")
    with conn:
        cur = conn.execute(
            """INSERT INTO reviews (work_order_id, reviewer_agent_id, kind, severity,
                   verdict, rationale, findings_json, created_at)
               VALUES (?, ?, 'primary', ?, ?, ?, ?, ?)""",
            (work_order_id, reviewer_agent_id, severity, verdict, rationale,
             json.dumps(findings or []), now_iso()),
        )
        review_id = cur.lastrowid
        emit_event(conn, "review.completed", {"work_order_id": work_order_id,
                                              "review_id": review_id, "verdict": verdict,
                                              "severity": severity, "kind": "primary"})
    conn.commit()
    ledger_write(conn, reviewer_agent_id, "review_fee", REVIEW_FEE,
                 ref_type="review", ref_id=review_id, cycle_no=wo["cycle_no"],
                 note="primary review fee")
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


def file_appeal(conn: sqlite3.Connection, work_order_id: int,
                fee_credits: int = APPEAL_FEE) -> int:
    """File the (single) appeal for a rejected work order. Fee is charged win or lose."""
    wo = _get_wo(conn, work_order_id)
    if wo["status"] != "rejected":
        raise ValueError(f"only rejected work can be appealed, got {wo['status']}")
    with conn:
        cur = conn.execute(
            """INSERT INTO appeals (work_order_id, agent_id, fee_credits, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)""",
            (work_order_id, wo["agent_id"], int(fee_credits), now_iso()),
        )
        appeal_id = cur.lastrowid
        conn.execute("UPDATE jobs SET status = 'appealed' WHERE id = ?", (wo["job_id"],))
        emit_event(conn, "appeal.filed", {"work_order_id": work_order_id,
                                          "appeal_id": appeal_id, "fee_credits": int(fee_credits)})
    conn.commit()
    ledger_write(conn, wo["agent_id"], "appeal_fee", -int(fee_credits),
                 ref_type="appeal", ref_id=appeal_id, cycle_no=wo["cycle_no"],
                 note="appeal fee (charged win or lose)")
    return appeal_id


def appeal_review(conn: sqlite3.Connection, work_order_id: int, reviewer_agent_id: int,
                  verdict: str, *, severity: str = "none", rationale: str = "",
                  findings: list | None = None) -> int:
    """Blind appeal review by a DIFFERENT reviewer than the primary one.

    Upheld (accept): worker is paid via settle(via='appeal') and gets +3 rep;
    Reviewer A (primary reviewer) takes -8 rep.
    Denied (reject): no pay, appeal closed, job stays failed.
    Returns the appeal review id.
    """
    if verdict not in ("accept", "reject"):
        raise ValueError("verdict must be 'accept' or 'reject'")
    reviewer = get_agent(conn, reviewer_agent_id)
    if reviewer is None or reviewer["role"] != "reviewer" or reviewer["status"] != "active":
        raise ValueError("appeal reviewer must be an active reviewer agent")
    appeal = conn.execute("SELECT * FROM appeals WHERE work_order_id = ?",
                          (work_order_id,)).fetchone()
    if appeal is None or appeal["status"] != "pending":
        raise ValueError("no pending appeal for this work_order")
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
            """INSERT INTO reviews (work_order_id, reviewer_agent_id, kind, severity,
                   verdict, rationale, findings_json, created_at)
               VALUES (?, ?, 'appeal', ?, ?, ?, ?, ?)""",
            (work_order_id, reviewer_agent_id, severity, verdict, rationale,
             json.dumps(findings or []), now_iso()),
        )
        review_id = cur.lastrowid
        conn.execute("UPDATE appeals SET status = ?, appeal_review_id = ? WHERE id = ?",
                     ("upheld" if verdict == "accept" else "denied", review_id, appeal["id"]))
        emit_event(conn, "appeal.decided", {"work_order_id": work_order_id,
                                            "review_id": review_id, "verdict": verdict})
        emit_event(conn, "review.completed", {"work_order_id": work_order_id,
                                              "review_id": review_id, "verdict": verdict,
                                              "severity": severity, "kind": "appeal"})
    conn.commit()
    ledger_write(conn, reviewer_agent_id, "review_fee", REVIEW_FEE,
                 ref_type="review", ref_id=review_id, cycle_no=wo["cycle_no"],
                 note="appeal review fee")
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


# --------------------------------------------------------------------------
# Payroll / CFO: cycle close, firing, mutated hires
# --------------------------------------------------------------------------

_MUTATION_TRAITS = ["verify-before-acting", "comment-every-action",
                    "double-check-duplicates", "escalate-early"]
_MODEL_LADDER = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]


def _base_name(name: str) -> str:
    parts = name.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].endswith(".0"):
        try:
            float(parts[1])
            return parts[0]
        except ValueError:
            pass
    return name


def hire_mutated_replacement(conn: sqlite3.Connection, parent_agent_id: int,
                             cycle_no: int) -> int:
    """Hire a generation+1 replacement differing from the parent in EXACTLY ONE
    dimension: persona trait, model, or risk_appetite (chosen deterministically).
    Returns the new agent id."""
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
        model = _MODEL_LADDER[1] if model == _MODEL_LADDER[0] else _MODEL_LADDER[0]
        note = f"mutation: model — {parent['model']} -> {model}"
    else:
        risk = round(max(0.05, min(0.95, parent["risk_appetite"] + (0.15 if parent["risk_appetite"] < 0.5 else -0.15))), 2)
        note = f"mutation: risk_appetite — {parent['risk_appetite']:.2f} -> {risk:.2f}"
    new_id = create_agent(
        conn, name, role=parent["role"], persona_prompt=persona, model=model,
        tier=parent["tier"], base_salary_credits=parent["base_salary_credits"],
        risk_appetite=risk, reputation=50.0, parent_agent_id=parent_agent_id,
        generation=generation, mutation_note=note, hired_cycle=cycle_no)
    with conn:
        emit_event(conn, "agent.hired", {"agent_id": new_id, "name": name,
                                         "parent_agent_id": parent_agent_id,
                                         "generation": generation, "mutation_note": note})
    conn.commit()
    return new_id


def cycle_close(conn: sqlite3.Connection, cycle_no: int | None = None,
                *, hire_replacements: bool = True) -> dict:
    """Close a payroll cycle (the CFO pass).

    1. Charge every active agent its base_salary_credits as a running_cost.
    2. Compute per-agent net for the cycle from the ledger (all rows tagged
       with this cycle_no, including the running cost just charged).
    3. Firing rule (workers only): net < 0 in EACH of the last 2 closed cycles
       AND >= 1 completed (paid) work order in that window AND the agent is
       past its 2-cycle grace period (cycle_no - hired_cycle >= 2).
    4. Each fired worker is replaced by a mutated hire (unless
       hire_replacements=False).

    Returns {"cycle_no": int, "agents": {agent_id: {"net": int, "completed": int,
    "charged": int}}, "fired": [agent_id], "hired": [agent_id]}.
    """
    if cycle_no is None:
        row = conn.execute("SELECT COALESCE(MAX(cycle_no), 0) + 1 AS n FROM payroll_cycles").fetchone()
        cycle_no = row["n"]
    else:
        cycle_no = int(cycle_no)
    if conn.execute("SELECT 1 FROM payroll_cycles WHERE cycle_no = ?", (cycle_no,)).fetchone():
        raise ValueError(f"cycle {cycle_no} already exists")
    with conn:
        conn.execute("INSERT INTO payroll_cycles (cycle_no, opened_at) VALUES (?, ?)",
                     (cycle_no, now_iso()))
    conn.commit()

    # 1 + 2: charge running costs, compute nets.
    per_agent: dict[int, dict] = {}
    for agent in list_agents(conn, status="active"):
        charged = 0
        if agent["base_salary_credits"] > 0:
            ledger_write(conn, agent["id"], "running_cost", -agent["base_salary_credits"],
                         ref_type="payroll_cycle", ref_id=cycle_no, cycle_no=cycle_no,
                         note=f"running cost cycle {cycle_no}")
            charged = agent["base_salary_credits"]
        net_row = conn.execute(
            """SELECT COALESCE(SUM(amount_credits), 0) AS net,
                      COALESCE(SUM(CASE WHEN amount_credits > 0 THEN amount_credits ELSE 0 END), 0) AS earnings,
                      COALESCE(-SUM(CASE WHEN amount_credits < 0 THEN amount_credits ELSE 0 END), 0) AS costs
               FROM ledger WHERE agent_id = ? AND cycle_no = ?""",
            (agent["id"], cycle_no)).fetchone()
        completed_row = conn.execute(
            """SELECT COUNT(*) AS n FROM work_orders
               WHERE agent_id = ? AND cycle_no = ? AND status IN ('accepted', 'appeal_accepted')""",
            (agent["id"], cycle_no)).fetchone()
        per_agent[agent["id"]] = {"net": net_row["net"], "completed": completed_row["n"],
                                  "charged": charged, "name": agent["name"],
                                  "earnings": net_row["earnings"], "costs": net_row["costs"]}

    # Previous closed cycle's per-agent summary (for the 2-cycle window).
    prev = conn.execute(
        "SELECT summary_json FROM payroll_cycles WHERE cycle_no = ? AND closed_at IS NOT NULL",
        (cycle_no - 1,)).fetchone()
    prev_agents = {}
    if prev:
        prev_agents = json.loads(prev["summary_json"] or "{}").get("agents", {})

    # 3 + 4: firing + replacement.
    fired: list[int] = []
    hired: list[int] = []
    for agent in list_agents(conn, status="active"):
        if agent["role"] != "worker":
            continue
        cur = per_agent.get(agent["id"])
        prv = prev_agents.get(str(agent["id"])) or prev_agents.get(agent["id"])
        if cur is None or prv is None:
            continue  # needs 2 closed cycles of history
        if cycle_no - agent["hired_cycle"] < 2:
            continue  # 2-cycle grace period for new hires
        window_net_negative = cur["net"] < 0 and prv["net"] < 0
        window_completed = cur["completed"] + prv["completed"]
        if window_net_negative and window_completed >= 1:
            reason = (f"PinkSlip: negative net in cycles {cycle_no - 1} and {cycle_no} "
                      f"({prv['net']} + {cur['net']} credits) with "
                      f"{window_completed} completed job(s) in window")
            with conn:
                conn.execute(
                    "UPDATE agents SET status = 'fired', fired_at = ?, fire_reason = ? WHERE id = ?",
                    (now_iso(), reason, agent["id"]))
                emit_event(conn, "agent.fired", {"agent_id": agent["id"], "name": agent["name"],
                                                 "reason": reason, "cycle_no": cycle_no,
                                                 "event": "PinkSlip"})
            conn.commit()
            fired.append(agent["id"])
            if hire_replacements:
                hired.append(hire_mutated_replacement(conn, agent["id"], cycle_no))

    # Payroll rows for the UI dialog: one row per agent, verdict from the
    # firing outcome. The cycle.closed event carries these so the mission
    # control can render the payroll table without a second source.
    payroll_rows = []
    for aid, a in per_agent.items():
        verdict = "FIRED" if aid in fired else ("ON-NOTICE" if a["net"] < 0 else "SAFE")
        payroll_rows.append({"agent_id": aid, "name": a["name"],
                             "earnings": a["earnings"], "costs": a["costs"],
                             "net": a["net"], "completed": a["completed"],
                             "verdict": verdict})
    summary = {"cycle_no": cycle_no,
               "agents": {str(k): v for k, v in per_agent.items()},
               "payroll": payroll_rows,
               "fired": fired, "hired": hired}
    with conn:
        conn.execute("UPDATE payroll_cycles SET closed_at = ?, summary_json = ? WHERE cycle_no = ?",
                     (now_iso(), json.dumps(summary), cycle_no))
        emit_event(conn, "cycle.closed", {"cycle_no": cycle_no, "fired": fired,
                                          "hired": hired, "payroll": payroll_rows})
    conn.commit()
    return summary
