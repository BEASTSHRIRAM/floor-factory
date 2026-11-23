"""Self-test for THE FLOOR economy core. Stdlib only, in-memory DB.

Run from the repo root:
    .venv/bin/python -m economy.test_core
    python3 -m economy.test_core
Exits 0 and prints PASS lines when everything holds.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from economy import core  # noqa: E402
from economy.db import init_db  # noqa: E402


def fresh():
    return init_db(":memory:", reset=True)


def by_name(conn, name):
    for a in core.list_agents(conn):
        if a["name"] == name:
            return a
    raise AssertionError(f"agent {name} not found")


def run_job(conn, worker_name, reviewer, *, budget=100, price=None, verdict="accept",
            created_cycle=0, severity="none"):
    job_id = core.create_job(conn, f"job for {worker_name}", "brief", budget,
                             acceptance_criteria=["done"], created_cycle=created_cycle)
    worker = by_name(conn, worker_name)
    price = price if price is not None else 50
    core.place_bid(conn, job_id, worker["id"], price, 0.8)
    wo = core.award_job(conn, job_id)
    core.submit_work(conn, wo)
    core.review_work(conn, wo, reviewer["id"], verdict, severity=severity)
    return job_id, wo


def test_roster_and_formula():
    conn = fresh()
    roster = core.seed_roster(conn)
    assert len(roster) == 7, roster
    workers = [a for a in roster if a["role"] == "worker"]
    reviewers = [a for a in roster if a["role"] == "reviewer"]
    assert len(workers) == 5 and len(reviewers) == 2
    chotu = by_name(conn, "Chotu")
    assert "skips" in chotu["persona_prompt"] and chotu["tier"] == "junior"
    baron = by_name(conn, "Baron")
    assert baron["base_salary_credits"] == max(w["base_salary_credits"] for w in workers)
    assert core.seed_roster(conn) == roster or len(core.list_agents(conn)) == 7  # idempotent
    # Formula: 0.5*(1-50/100) + 0.3*(80/100) + 0.2*0.5 = 0.25+0.24+0.10 = 0.59
    assert abs(core.bid_score(50, 100, 80.0, 0.5) - 0.59) < 1e-9
    print("PASS roster + bid_score formula")


def test_award_picks_best_score_and_settle_pays():
    conn = fresh()
    core.seed_roster(conn)
    iris = by_name(conn, "Iris")
    job_id = core.create_job(conn, "Triage", "brief", 100, acceptance_criteria=["x"])
    maya, pixel = by_name(conn, "Maya"), by_name(conn, "Pixel")
    core.place_bid(conn, job_id, maya["id"], 90, 0.9)    # score .05+.246+.18=.476
    core.place_bid(conn, job_id, pixel["id"], 40, 0.6)   # score .30+.183+.12=.603 -> wins
    wo = core.award_job(conn, job_id)
    row = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo,)).fetchone()
    assert row["agent_id"] == pixel["id"] and row["agreed_price_credits"] == 40
    # write tool call without confirmation must fail
    try:
        core.record_tool_call(conn, wo, "close_ticket", effect="write", status="executed")
        raise AssertionError("unconfirmed write was allowed")
    except ValueError:
        pass
    core.record_tool_call(conn, wo, "close_ticket", effect="write",
                          confirmation_id="c1", confirmed_by="human", status="executed")
    try:
        core.settle(conn, wo)  # not submitted yet
        raise AssertionError("settle before submit was allowed")
    except ValueError:
        pass
    bal_before = core.get_balance(conn, pixel["id"])
    rep_before = by_name(conn, "Pixel")["reputation"]
    core.submit_work(conn, wo)
    core.review_work(conn, wo, iris["id"], "accept")
    assert core.get_balance(conn, pixel["id"]) == bal_before + 40
    assert by_name(conn, "Pixel")["reputation"] == rep_before + 4
    assert core.get_job(conn, job_id)["status"] == "paid"
    assert core.verify_ledger_chain(conn, pixel["id"])
    try:
        core.settle(conn, wo)  # double pay
        raise AssertionError("double settle was allowed")
    except ValueError:
        pass
    print("PASS award scoring + settle-only-on-accept + ledger chain")


def test_reject_no_pay_and_appeal_upheld():
    conn = fresh()
    core.seed_roster(conn)
    iris, omar = by_name(conn, "Iris"), by_name(conn, "Omar")
    chotu = by_name(conn, "Chotu")
    _, wo = run_job(conn, "Chotu", iris, verdict="reject", severity="P1")
    assert core.get_balance(conn, chotu["id"]) == 0  # rejection creates no earning
    assert by_name(conn, "Chotu")["reputation"] == 45.0 - 6
    iris_rep = by_name(conn, "Iris")["reputation"]
    core.file_appeal(conn, wo)
    assert core.get_balance(conn, chotu["id"]) == -core.APPEAL_FEE  # fee charged regardless
    try:
        core.appeal_review(conn, wo, iris["id"], "accept")  # same reviewer = not blind
        raise AssertionError("non-blind appeal review was allowed")
    except ValueError:
        pass
    core.appeal_review(conn, wo, omar["id"], "accept")
    # paid 50 on uphold, rep +3 (appeal) on top of -6; Reviewer A -8
    assert core.get_balance(conn, chotu["id"]) == -core.APPEAL_FEE + 50
    assert by_name(conn, "Chotu")["reputation"] == 45.0 - 6 + 3
    assert by_name(conn, "Iris")["reputation"] == iris_rep - 8
    assert core.verify_ledger_chain(conn, chotu["id"])
    print("PASS reject-no-pay + appeal fee + blind appeal upheld (worker +3, Reviewer A -8)")


def test_ledger_append_only():
    conn = fresh()
    core.seed_roster(conn)
    maya = by_name(conn, "Maya")
    core.ledger_write(conn, maya["id"], "bonus", 5, cycle_no=0)
    for sql in ("UPDATE ledger SET amount_credits = 999",
                "DELETE FROM ledger"):
        try:
            conn.execute(sql)
            conn.commit()
            raise AssertionError(f"ledger mutation allowed: {sql}")
        except sqlite3.DatabaseError:
            conn.rollback()
    print("PASS ledger append-only triggers")


def test_firing_and_mutated_replacement():
    conn = fresh()
    core.seed_roster(conn)
    iris = by_name(conn, "Iris")
    baron = by_name(conn, "Baron")
    # Baron: completes 1 cheap job per cycle but salary 90/cycle -> net negative both cycles.
    for cyc in (1, 2):
        run_job(conn, "Baron", iris, budget=100, price=40, created_cycle=cyc)
        summary = core.cycle_close(conn, cyc)
    baron = by_name(conn, "Baron")
    assert baron["status"] == "fired", summary
    assert summary["fired"] == [baron["id"]]
    assert len(summary["hired"]) == 1
    child = core.get_agent(conn, summary["hired"][0])
    assert child["parent_agent_id"] == baron["id"]
    assert child["generation"] == baron["generation"] + 1
    assert child["mutation_note"] and child["mutation_note"].startswith("mutation:")
    assert child["name"].startswith("Baron")
    # single-dimension mutation: exactly one of persona/model/risk differs
    diffs = sum([child["persona_prompt"] != baron["persona_prompt"],
                 child["model"] != baron["model"],
                 child["risk_appetite"] != baron["risk_appetite"]])
    assert diffs == 1, child
    # fired agents are inert
    job_id = core.create_job(conn, "post-fire", "brief", 100)
    try:
        core.place_bid(conn, job_id, baron["id"], 10, 0.5)
        raise AssertionError("fired agent could bid")
    except ValueError:
        pass
    # grace: the new hire cannot be fired in its first 2 cycles even if negative
    s3 = core.cycle_close(conn, 3)
    assert child["id"] not in s3["fired"]
    print("PASS firing rule (2 negative cycles + completed job) + mutated replacement + grace")


def main():
    test_roster_and_formula()
    test_award_picks_best_score_and_settle_pays()
    test_reject_no_pay_and_appeal_upheld()
    test_ledger_append_only()
    test_firing_and_mutated_replacement()
    print("ALL ECONOMY TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
