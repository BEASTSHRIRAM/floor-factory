"""Bookkeeping — a deliberately ordinary internal accounting API.

THE FLOOR's Bookkeeping department workplace (mirrors targets/ticketdesk/
app.py exactly in shape): plain FastAPI + its own SQLite file. THE FLOOR
never modifies this code; agents only reach it through Synapse-generated
MCP tools.

Deliberate platform limit, stated in the write-up: there are NO payment
or money-movement endpoints anywhere in this API, and no delete routes.
Agents organise the books and draft the chases; money never moves.

Run:   uvicorn app:app --port 8104
Seed:  python3 seed.py     (creates bookkeeping.db with the messy month)
Reset: python3 reset.py    (deletes bookkeeping.db and reseeds)
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="Bookkeeping", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _txn_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _get_txn_or_404(conn: sqlite3.Connection, txn_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"transaction {txn_id} not found")
    return row


def _get_invoice_or_404(conn: sqlite3.Connection, invoice_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"invoice {invoice_id} not found")
    return row


def _days_overdue(inv: sqlite3.Row, today: date) -> int:
    due = date.fromisoformat(inv["due_date"])
    return (today - due).days


def _chase_level(days_overdue: int) -> int:
    """Chase band for an overdue invoice: 0 = not chaseable yet,
    1 = gentle (+3), 2 = firm (+15), 3 = final (+30)."""
    if days_overdue >= 30:
        return 3
    if days_overdue >= 15:
        return 2
    if days_overdue >= 3:
        return 1
    return 0


def _invoice_dict(conn: sqlite3.Connection, inv: sqlite3.Row, today: date) -> dict:
    d = dict(inv)
    overdue = _days_overdue(inv, today) if inv["status"] == "open" else 0
    d["days_overdue"] = max(overdue, 0)
    d["chase_level_due"] = _chase_level(overdue) if inv["status"] == "open" else 0
    reminders = conn.execute(
        "SELECT id, level, note, created_at FROM reminder_events"
        " WHERE invoice_id = ? ORDER BY id",
        (inv["id"],),
    ).fetchall()
    d["reminders"] = [dict(r) for r in reminders]
    return d


def _recorded_balance(conn: sqlite3.Connection, account_id: int) -> int:
    return conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id = ?",
        (account_id,),
    ).fetchone()[0]


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class CategoriseBody(BaseModel):
    category: str


class FlagDuplicateBody(BaseModel):
    duplicate_of: int


class ReminderBody(BaseModel):
    note: str = ""


class NoteBody(BaseModel):
    text: str
    account_id: Optional[int] = None
    kind: str = "note"  # note | reconciliation | audit


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist for this department)
# --------------------------------------------------------------------------

@app.get("/transactions")
def list_transactions(
    account_id: Optional[int] = Query(default=None),
    category: Optional[str] = Query(default=None),
    uncategorised: Optional[bool] = Query(default=None),
):
    """List transactions, optionally filtered. uncategorised=true lists
    only transactions with no category yet."""
    sql = "SELECT * FROM transactions WHERE 1=1"
    params: list = []
    if account_id is not None:
        sql += " AND account_id = ?"
        params.append(account_id)
    if category is not None:
        sql += " AND category = ?"
        params.append(category)
    if uncategorised:
        sql += " AND category IS NULL"
    sql += " ORDER BY date, id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"transactions": [_txn_dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/transactions/uncategorised")
def list_uncategorised():
    """The categorisation queue: transactions with no category, oldest
    first, each with its age in days."""
    today = _today()
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE category IS NULL ORDER BY date, id"
        ).fetchall()
        out = []
        for r in rows:
            d = _txn_dict(r)
            d["age_days"] = (today - date.fromisoformat(r["date"])).days
            out.append(d)
        return {"transactions": out, "count": len(out)}
    finally:
        conn.close()


@app.get("/transactions/duplicates")
def find_duplicates():
    """Group UNFLAGGED transactions that look like exact duplicates of
    each other (same account, date, payee and amount). Flagged rows drop
    out, so an empty result means every duplicate has been dealt with."""
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE duplicate_of IS NULL ORDER BY date, id"
        ).fetchall()
        groups: dict[tuple, list] = {}
        for r in rows:
            key = (r["account_id"], r["date"], r["payee"].strip().lower(), r["amount"])
            groups.setdefault(key, []).append(dict(r))
        dupes = [
            {"account_id": key[0], "date": key[1], "payee": members[0]["payee"],
             "amount": key[3], "transaction_ids": [t["id"] for t in members],
             "transactions": members}
            for key, members in groups.items() if len(members) > 1
        ]
        return {"groups": dupes, "group_count": len(dupes)}
    finally:
        conn.close()


@app.get("/accounts/{account_id}/reconcile")
def reconcile_account(account_id: int):
    """Compare the recorded balance (sum of the books) against the bank
    statement balance for one account and report the delta. Read-only:
    reconciliation explains a difference, it never moves money."""
    conn = _conn()
    try:
        acct = conn.execute("SELECT * FROM accounts WHERE id = ?",
                            (account_id,)).fetchone()
        if acct is None:
            raise HTTPException(status_code=404, detail=f"account {account_id} not found")
        stmt = conn.execute("SELECT * FROM statements WHERE account_id = ?",
                            (account_id,)).fetchone()
        if stmt is None:
            raise HTTPException(status_code=404,
                                detail=f"no statement on file for account {account_id}")
        recorded = _recorded_balance(conn, account_id)
        delta = stmt["statement_balance"] - recorded
        return {
            "account_id": account_id,
            "account_name": acct["name"],
            "recorded_balance": recorded,
            "statement_balance": stmt["statement_balance"],
            "statement_as_of": stmt["as_of"],
            "delta": delta,
            "status": "reconciled" if delta == 0 else "discrepancy",
        }
    finally:
        conn.close()


@app.get("/receivables")
def list_receivables(status: Optional[str] = Query(default=None)):
    """List invoices/receivables with days overdue, the chase level each
    has reached, and every reminder recorded against it."""
    today = _today()
    conn = _conn()
    try:
        sql = "SELECT * FROM invoices"
        params: list = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY due_date, id"
        rows = conn.execute(sql, params).fetchall()
        invoices = [_invoice_dict(conn, r, today) for r in rows]
        open_total = sum(i["amount"] for i in invoices if i["status"] == "open")
        overdue = [i for i in invoices
                   if i["status"] == "open" and i["days_overdue"] > 0]
        return {"invoices": invoices, "count": len(invoices),
                "open_total": open_total, "overdue_count": len(overdue),
                "overdue_total": sum(i["amount"] for i in overdue)}
    finally:
        conn.close()


@app.get("/accounts")
def list_accounts():
    """All accounts with their recorded balances."""
    conn = _conn()
    try:
        out = []
        for a in conn.execute("SELECT * FROM accounts ORDER BY id").fetchall():
            d = dict(a)
            d["recorded_balance"] = _recorded_balance(conn, a["id"])
            out.append(d)
        return {"accounts": out, "count": len(out)}
    finally:
        conn.close()


@app.get("/chart")
def chart_of_accounts():
    """The chart of accounts — the only valid category names."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM chart_of_accounts ORDER BY code").fetchall()
        return {"categories": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/notes")
def list_notes():
    """Finance notes recorded by agents (incl. reconciliation write-ups)."""
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM finance_notes ORDER BY id").fetchall()
        return {"notes": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    today = _today()
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        uncat = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE category IS NULL").fetchone()[0]
        uncat_rows = conn.execute(
            "SELECT date FROM transactions WHERE category IS NULL").fetchall()
        uncat_old = sum(
            1 for r in uncat_rows
            if (today - date.fromisoformat(r["date"])).days > 7)
        flagged = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE duplicate_of IS NOT NULL"
        ).fetchone()[0]
        balances = {a["name"]: _recorded_balance(conn, a["id"])
                    for a in conn.execute("SELECT * FROM accounts").fetchall()}
    finally:
        conn.close()
    dupes = find_duplicates()
    recv = list_receivables(None)  # explicit: the bare default is a Query object
    return {
        "total_transactions": total,
        "uncategorised": uncat,
        "uncategorised_older_than_7d": uncat_old,
        "duplicate_groups_open": dupes["group_count"],
        "duplicates_flagged": flagged,
        "open_receivables": recv["open_total"],
        "overdue_invoices": recv["overdue_count"],
        "balances": balances,
    }


@app.post("/transactions/{txn_id}/categorise")
def categorise_transaction(txn_id: int, body: CategoriseBody):
    """Set a transaction's category. The category must be a name from
    the chart of accounts."""
    conn = _conn()
    try:
        _get_txn_or_404(conn, txn_id)
        valid = {r["name"] for r in
                 conn.execute("SELECT name FROM chart_of_accounts").fetchall()}
        if body.category not in valid:
            raise HTTPException(
                status_code=422,
                detail=f"invalid category {body.category!r}; chart has {sorted(valid)}")
        conn.execute("UPDATE transactions SET category = ? WHERE id = ?",
                     (body.category, txn_id))
        conn.commit()
        return _txn_dict(_get_txn_or_404(conn, txn_id))
    finally:
        conn.close()


@app.post("/transactions/{txn_id}/flag-duplicate")
def flag_duplicate(txn_id: int, body: FlagDuplicateBody):
    """Flag a transaction as a duplicate of another (canonical) one.
    Flagging only marks the row — nothing is deleted, ever."""
    if txn_id == body.duplicate_of:
        raise HTTPException(status_code=422,
                            detail="a transaction cannot duplicate itself")
    conn = _conn()
    try:
        _get_txn_or_404(conn, txn_id)
        _get_txn_or_404(conn, body.duplicate_of)
        conn.execute("UPDATE transactions SET duplicate_of = ? WHERE id = ?",
                     (body.duplicate_of, txn_id))
        conn.commit()
        return _txn_dict(_get_txn_or_404(conn, txn_id))
    finally:
        conn.close()


@app.post("/receivables/{invoice_id}/reminder")
def send_reminder(invoice_id: int, body: ReminderBody):
    """Record a payment-chase reminder for an overdue invoice. This
    RECORDS the reminder (draft + event) in the books — it does not send
    real email, and it never moves money. The chase level is derived
    from how overdue the invoice is (+3 gentle, +15 firm, +30 final);
    invoices not yet 3 days overdue cannot be chased."""
    today = _today()
    conn = _conn()
    try:
        inv = _get_invoice_or_404(conn, invoice_id)
        if inv["status"] != "open":
            raise HTTPException(status_code=422,
                                detail=f"invoice {invoice_id} is {inv['status']}, not open")
        overdue = _days_overdue(inv, today)
        level = _chase_level(overdue)
        if level == 0:
            raise HTTPException(
                status_code=422,
                detail=f"invoice {invoice_id} is {overdue} day(s) overdue; "
                       "chasing starts at +3 days")
        cur = conn.execute(
            "INSERT INTO reminder_events (invoice_id, level, note, created_at)"
            " VALUES (?,?,?,?)",
            (invoice_id, level, body.note, seed_module._iso(_now())),
        )
        conn.commit()
        reminder = conn.execute(
            "SELECT id, level, note, created_at FROM reminder_events WHERE id = ?",
            (cur.lastrowid,)).fetchone()
        return {"reminder": dict(reminder),
                "invoice": _invoice_dict(conn, _get_invoice_or_404(conn, invoice_id),
                                         today)}
    finally:
        conn.close()


@app.post("/notes")
def add_finance_note(body: NoteBody):
    """Record a finance note (e.g. a reconciliation write-up) in the books."""
    conn = _conn()
    try:
        if body.kind not in ("note", "reconciliation", "audit"):
            raise HTTPException(status_code=422, detail=f"invalid note kind {body.kind}")
        if body.account_id is not None:
            acct = conn.execute("SELECT id FROM accounts WHERE id = ?",
                                (body.account_id,)).fetchone()
            if acct is None:
                raise HTTPException(status_code=404,
                                    detail=f"account {body.account_id} not found")
        cur = conn.execute(
            "INSERT INTO finance_notes (account_id, kind, text, created_at)"
            " VALUES (?,?,?,?)",
            (body.account_id, body.kind, body.text, seed_module._iso(_now())),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM finance_notes WHERE id = ?",
                           (cur.lastrowid,)).fetchone()
        return dict(row)
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
    return {"reset": True, "transactions": n}
