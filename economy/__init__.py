"""Economy: ledger writer, payroll/CFO, reputation, firing, mutation.

Pure deterministic Python — NO LLM imports allowed in this package.
Money math is code, not LLM (ARCHITECTURE §1, §5). Stdlib sqlite3 only.
"""

from .db import default_db_path, emit_event, get_conn, init_db, now_iso
from .core import (
    APPEAL_FEE, REVIEW_FEE,
    REP_ACCEPT, REP_APPEAL_REVIEWER_A, REP_APPEAL_WORKER, REP_REJECT,
    appeal_review, apply_reputation, award_job, bid_score, create_agent,
    create_job, cycle_close, file_appeal, get_agent, get_balance, get_job,
    hire_mutated_replacement, ledger_write, list_agents, place_bid,
    record_tool_call, review_work, seed_roster, settle, submit_work,
    suggest_bid, verify_ledger_chain,
)

__all__ = [
    "default_db_path", "emit_event", "get_conn", "init_db", "now_iso",
    "APPEAL_FEE", "REVIEW_FEE",
    "REP_ACCEPT", "REP_APPEAL_REVIEWER_A", "REP_APPEAL_WORKER", "REP_REJECT",
    "appeal_review", "apply_reputation", "award_job", "bid_score", "create_agent",
    "create_job", "cycle_close", "file_appeal", "get_agent", "get_balance", "get_job",
    "hire_mutated_replacement", "ledger_write", "list_agents", "place_bid",
    "record_tool_call", "review_work", "seed_roster", "settle", "submit_work",
    "suggest_bid", "verify_ledger_chain",
]
