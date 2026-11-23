"""THE FLOOR — economy DB layer.

SQLite schema + connection handling for the factory's money/state store.
Stdlib only (sqlite3). Money is integer credits everywhere; the ledger is
append-only (enforced by triggers, not just convention).

DB path: $FLOOR_DB if set, else <repo>/floor.db (repo = parent of economy/).
Schema follows ARCHITECTURE.md §5.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["default_db_path", "get_conn", "init_db", "emit_event", "now_iso", "SCHEMA"]


def now_iso() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_db_path() -> Path:
    env = os.environ.get("FLOOR_DB")
    if env:
        return Path(env)
    # economy/db.py -> repo root is two levels up.
    return Path(__file__).resolve().parent.parent / "floor.db"


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS agents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'worker',   -- worker | reviewer
    persona_prompt      TEXT NOT NULL DEFAULT '',
    model               TEXT NOT NULL DEFAULT 'openai/gpt-oss-120b',
    tier                TEXT NOT NULL DEFAULT 'junior',   -- junior|senior|veteran
    base_salary_credits INTEGER NOT NULL DEFAULT 0,       -- charged per cycle as running cost
    risk_appetite       REAL NOT NULL DEFAULT 0.5,        -- 0..1
    status              TEXT NOT NULL DEFAULT 'active',   -- active | fired
    parent_agent_id     INTEGER REFERENCES agents(id),
    generation          INTEGER NOT NULL DEFAULT 1,
    mutation_note       TEXT,
    reputation          REAL NOT NULL DEFAULT 50.0,       -- 0..100 cache of reputation_events
    hired_cycle         INTEGER NOT NULL DEFAULT 0,       -- cycle_no when hired (grace period)
    created_at          TEXT NOT NULL,
    fired_at            TEXT,
    fire_reason         TEXT
);

CREATE TABLE IF NOT EXISTS target_systems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    repo_path   TEXT,
    api_base_url TEXT,
    status      TEXT NOT NULL DEFAULT 'online'
);

CREATE TABLE IF NOT EXISTS mcp_servers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id   INTEGER REFERENCES target_systems(id),
    kind        TEXT,                                     -- auto_local|auto_hosted|custom_local
    entry_point TEXT,
    status      TEXT NOT NULL DEFAULT 'online'
);

CREATE TABLE IF NOT EXISTS tools_registry (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    mcp_server_id        INTEGER REFERENCES mcp_servers(id),
    tool_name            TEXT NOT NULL,
    description          TEXT,
    effect               TEXT NOT NULL DEFAULT 'read',    -- read | write
    requires_confirmation INTEGER NOT NULL DEFAULT 0,
    status               TEXT NOT NULL DEFAULT 'active',  -- active | retired
    UNIQUE (mcp_server_id, tool_name)
);

CREATE TABLE IF NOT EXISTS jobs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    system_id            INTEGER REFERENCES target_systems(id),
    source               TEXT NOT NULL DEFAULT 'seeded',  -- seeded|backlog_scan|live_demo
    title                TEXT NOT NULL,
    brief                TEXT NOT NULL DEFAULT '',
    acceptance_criteria  TEXT NOT NULL DEFAULT '[]',      -- JSON list of strings
    budget_credits       INTEGER NOT NULL,
    status               TEXT NOT NULL DEFAULT 'open',
    -- draft|open|bidding|awarded|executing|in_review|appealed|paid|failed
    requires_human_merge INTEGER NOT NULL DEFAULT 0,
    created_cycle        INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bids (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id        INTEGER NOT NULL REFERENCES jobs(id),
    agent_id      INTEGER NOT NULL REFERENCES agents(id),
    price_credits INTEGER NOT NULL,
    confidence    REAL NOT NULL,                          -- 0..1
    rationale     TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    UNIQUE (job_id, agent_id)
);

CREATE TABLE IF NOT EXISTS work_orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL REFERENCES jobs(id),
    agent_id            INTEGER NOT NULL REFERENCES agents(id),
    agreed_price_credits INTEGER NOT NULL,
    plan                TEXT,
    status              TEXT NOT NULL DEFAULT 'working',
    -- working|submitted|accepted|rejected|appeal_accepted|appeal_rejected
    cycle_no            INTEGER NOT NULL DEFAULT 0,
    started_at          TEXT NOT NULL,
    finished_at         TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id   INTEGER NOT NULL REFERENCES work_orders(id),
    tool_name       TEXT NOT NULL,
    args_json       TEXT NOT NULL DEFAULT '{}',
    effect          TEXT NOT NULL DEFAULT 'read',         -- read | write
    confirmation_id TEXT,
    confirmed_by    TEXT,                                 -- human | policy
    confirmed_at    TEXT,
    status          TEXT NOT NULL DEFAULT 'proposed',
    -- proposed|confirmed|denied|executed|error
    result_summary  TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL,
    CHECK (NOT (effect = 'write' AND status = 'executed') OR confirmation_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS reviews (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id     INTEGER NOT NULL REFERENCES work_orders(id),
    reviewer_agent_id INTEGER NOT NULL REFERENCES agents(id),
    kind              TEXT NOT NULL DEFAULT 'primary',    -- primary | appeal
    severity          TEXT NOT NULL DEFAULT 'none',       -- none|P3|P2|P1|P0
    verdict           TEXT NOT NULL,                      -- accept | reject
    rationale         TEXT NOT NULL DEFAULT '',
    findings_json     TEXT NOT NULL DEFAULT '[]',
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appeals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id    INTEGER NOT NULL UNIQUE REFERENCES work_orders(id),
    agent_id         INTEGER NOT NULL REFERENCES agents(id),
    fee_credits      INTEGER NOT NULL,
    status           TEXT NOT NULL DEFAULT 'pending',     -- pending|upheld|denied
    appeal_review_id INTEGER REFERENCES reviews(id),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id       INTEGER NOT NULL REFERENCES agents(id),
    kind           TEXT NOT NULL,
    -- earning|review_fee|appeal_fee|running_cost|tool_cost|bonus|penalty
    amount_credits INTEGER NOT NULL,                      -- signed
    balance_after  INTEGER NOT NULL,                      -- chain: prev balance_after + amount
    ref_type       TEXT,
    ref_id         INTEGER,
    cycle_no       INTEGER NOT NULL DEFAULT 0,
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL
);

-- Ledger is APPEND-ONLY: block UPDATE/DELETE at the DB level.
CREATE TRIGGER IF NOT EXISTS ledger_no_update
BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete
BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;

CREATE TABLE IF NOT EXISTS payroll_cycles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    cycle_no     INTEGER NOT NULL UNIQUE,
    opened_at    TEXT NOT NULL,
    closed_at    TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS reputation_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id   INTEGER NOT NULL REFERENCES agents(id),
    delta      REAL NOT NULL,
    reason     TEXT NOT NULL,
    ref_type   TEXT,
    ref_id     INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    id          INTEGER,
    type        TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
"""


def get_conn(db_path=None) -> sqlite3.Connection:
    """Open a connection (WAL, foreign keys on, Row factory). Does NOT create schema."""
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
    """Create (or, with reset=True, drop and recreate) the schema. Returns a connection."""
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


def emit_event(conn: sqlite3.Connection, type: str, payload: dict | None = None) -> int:
    """Append a UI-stream event; returns its seq. (Parameter name `type` matches §5/UI spec.)"""
    cur = conn.execute(
        "INSERT INTO events (type, payload_json, created_at) VALUES (?, ?, ?)",
        (type, json.dumps(payload or {}), now_iso()),
    )
    seq = cur.lastrowid
    conn.execute("UPDATE events SET id = ? WHERE seq = ?", (seq, seq))
    return seq
