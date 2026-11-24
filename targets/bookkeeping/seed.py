"""Seed data for Bookkeeping — one deliberately messy month of books.

Mirrors targets/ticketdesk/seed.py: all timestamps are computed relative
to seed time so the dataset is reproducible whenever seed.py / reset.py
runs, and the messiness is planted in known, countable amounts:

  - 49 transactions across 3 accounts (amounts in whole rupees,
    negative = money out, positive = money in)
  - exactly 12 uncategorised transactions: 8 older than 7 days
    (these MUST be cleared by the categorise job) and 4 recent ones
  - exactly 3 duplicate transactions (ids 4, 12, 22 — second copies of
    ids 3, 11, 21: same account, date, payee and amount, unflagged)
  - the operating account's bank statement disagrees with the books by
    exactly +751: an unrecorded interest credit of 1,250 less an
    unrecorded bank fee of 499. The books are never "fixed" by seeding —
    finding and explaining that delta is the reconciliation job.
  - 11 invoices: 3 paid, 8 open — 2 not yet due, 2 in the +3 chase
    band (3-14 days overdue), 2 in the +15 band (15-29), 2 in the
    +30 band (30+).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bookkeeping.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    kind    TEXT NOT NULL DEFAULT 'bank',      -- bank | cash
    bank    TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chart_of_accounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL                          -- income | expense
);
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   INTEGER NOT NULL REFERENCES accounts(id),
    date         TEXT NOT NULL,                 -- ISO date (YYYY-MM-DD)
    payee        TEXT NOT NULL DEFAULT '',
    memo         TEXT NOT NULL DEFAULT '',
    amount       INTEGER NOT NULL,              -- whole rupees, signed
    category     TEXT,                          -- chart name, NULL = uncategorised
    duplicate_of INTEGER REFERENCES transactions(id),
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS statements (
    account_id        INTEGER PRIMARY KEY REFERENCES accounts(id),
    statement_balance INTEGER NOT NULL,
    as_of             TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no  TEXT NOT NULL UNIQUE,
    customer    TEXT NOT NULL,
    amount      INTEGER NOT NULL,
    issued_date TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open'    -- open | paid
);
CREATE TABLE IF NOT EXISTS reminder_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    level      INTEGER NOT NULL,                -- 1 gentle | 2 firm | 3 final
    note       TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS finance_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER REFERENCES accounts(id),
    kind       TEXT NOT NULL DEFAULT 'note',    -- note | reconciliation | audit
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

ACCOUNTS = [
    (1, "Operating Account", "bank", "HDFC Bank — Current"),
    (2, "Savings Account", "bank", "HDFC Bank — Savings"),
    (3, "Petty Cash", "cash", ""),
]

# The chart of accounts: (code, category name, type). Transaction
# `category` values must be one of these names (or NULL).
CHART = [
    ("4100", "client_services", "income"),
    ("4200", "interest_income", "income"),
    ("5100", "salaries", "expense"),
    ("5200", "rent", "expense"),
    ("5300", "software", "expense"),
    ("5400", "cloud_hosting", "expense"),
    ("5500", "utilities", "expense"),
    ("5600", "travel", "expense"),
    ("5700", "meals", "expense"),
    ("5800", "marketing", "expense"),
    ("5900", "office_supplies", "expense"),
    ("6000", "hardware", "expense"),
    ("6100", "bank_fees", "expense"),
    ("6900", "miscellaneous", "expense"),
]

# The planted reconciliation story (operating account):
# statement = recorded + INTEREST_UNRECORDED - FEE_UNRECORDED
STATEMENT_DELTA = 751
INTEREST_UNRECORDED = 1250
FEE_UNRECORDED = 499

# Each transaction: account_id, days_ago, payee, memo, amount, category
# (None = uncategorised). Order matters: ids are assigned sequentially,
# and the three rows marked by a following duplicate copy are ids 3, 11, 21.
TXNS = [
    # --- regular, categorised (ids 1-3) ---
    (1, 29, "AWS", "Cloud hosting — October usage", -12750, "cloud_hosting"),          # id 1
    (1, 28, "BESCOM", "Electricity — October", -1750, "utilities"),                    # id 2
    (1, 26, "Salary: Team", "Payroll — November salaries", -145000, "salaries"),       # id 3
    (1, 26, "Salary: Team", "Payroll — November salaries", -145000, "salaries"),       # id 4  DUPLICATE of 3
    (1, 25, "Office Rent — MG Road", "Office rent — November", -38000, "rent"),        # id 5
    (1, 24, "AWS", "Cloud hosting — November usage", -12400, "cloud_hosting"),         # id 6
    (1, 23, "Google Workspace", "Workspace seats — November", -2999, "software"),      # id 7
    (1, 22, "Acme Corp", "Client payment — INV-1042", 450000, "client_services"),      # id 8
    (1, 21, "BESCOM", "Electricity — November", -1850, "utilities"),                   # id 9
    (1, 20, "Airtel", "Broadband — November", -1199, "utilities"),                     # id 10
    (1, 19, "Figma", "Design seats — annual", -4999, "software"),                      # id 11
    (1, 19, "Figma", "Design seats — annual", -4999, "software"),                      # id 12 DUPLICATE of 11
    (1, 18, "IndiGo", "Flights — Bengaluru→Delhi, client visit", -8600, "travel"),     # id 13
    (1, 17, "Swiggy", "Office lunch — sprint week", -2450, "meals"),                   # id 14
    (1, 16, "Meta Ads", "Campaign — November", -15000, "marketing"),                   # id 15
    (1, 15, "Amazon", "Stationery and peripherals", -7300, "office_supplies"),         # id 16
    (2, 15, "HDFC Bank", "Savings interest credit", 3200, "interest_income"),           # id 17
    (1, 14, "BrightRetail", "Client payment — INV-1043", 275000, "client_services"),   # id 18
    (1, 13, "Notion", "Workspace plan — annual", -1899, "software"),                   # id 19
    (1, 12, "DesignWorks Studio", "Contractor payout — brand design", -42000, "miscellaneous"),  # id 20
    (1, 11, "Zoom", "Meetings plan — November", -999, "software"),                     # id 21
    (1, 11, "Zoom", "Meetings plan — November", -999, "software"),                     # id 22 DUPLICATE of 21
    (1, 10, "Uber", "Client-visit cabs", -3120, "travel"),                             # id 23
    (1, 9, "Zomato", "Team dinner — release night", -5600, "meals"),                   # id 24
    (1, 8, "LinkedIn", "LinkedIn Ads — November", -22000, "marketing"),                # id 25
    (1, 7, "Amazon", "27-inch monitor — new joiner", -15499, "hardware"),              # id 26
    (3, 6, "Staples", "Petty cash — printer cartridges", -1200, "office_supplies"),     # id 27
    (1, 6, "DeltaExports", "Client payment — INV-1045", 95000, "client_services"),     # id 28
    (1, 5, "HDFC Bank", "Account maintenance charge", -640, "bank_fees"),              # id 29
    (1, 4, "Northwind", "Client payment — INV-1044", 180000, "client_services"),       # id 30
    (1, 3, "AWS", "Cloud hosting — December usage", -11750, "cloud_hosting"),          # id 31
    (1, 2, "Swiggy", "Office lunch — demo day", -2600, "meals"),                       # id 32
    (1, 1, "Airtel", "Broadband — December", -1499, "utilities"),                      # id 33
    (1, 27, "Staples", "Notebooks and supplies", -2100, "office_supplies"),             # id 34
    (1, 24, "Uber", "Airport cabs — founder travel", -3300, "travel"),                 # id 35
    (1, 20, "IndiGo", "Flights — Mumbai workshop", -9800, "travel"),                   # id 36
    # --- uncategorised, OLDER than 7 days (ids 37-44) — the job's queue ---
    (1, 21, "AWS", "Cloud hosting — burst usage", -11800, None),                       # id 37
    (1, 16, "Figma", "Design seats — extra licences", -4999, None),                    # id 38
    (1, 15, "IndiGo", "Flights — investor meeting", -9400, None),                      # id 39
    (1, 14, "Swiggy", "Office lunch — client visit", -1980, None),                     # id 40
    (1, 12, "Meta Ads", "Campaign — retargeting", -12500, None),                       # id 41
    (1, 11, "BESCOM", "Electricity — arrears", -2010, None),                           # id 42
    (1, 10, "Google Workspace", "Workspace seats — extra", -2999, None),               # id 43
    (1, 9, "Uber", "Late-night cabs — launch week", -2740, None),                      # id 44
    # --- uncategorised, RECENT (ids 45-48) — may legitimately remain ---
    (1, 3, "Notion", "Workspace plan — extra seats", -1899, None),                     # id 45
    (1, 2, "Zomato", "Team lunch", -3320, None),                                       # id 46
    (1, 1, "Amazon", "Cables and adapters", -4410, None),                              # id 47
    (1, 0, "Airtel", "Mobile recharge — office SIM", -1199, None),                      # id 48
    # --- one more regular row (id 49) ---
    (1, 13, "Swiggy", "Office lunch — planning week", -2150, "meals"),                 # id 49
]

DUPLICATE_IDS = [4, 12, 22]  # second copies; canonical ids are 3, 11, 21

# Each invoice: invoice_no, customer, amount, due_in_days (negative = overdue
# by that many days), status. Issued = due - 14 days (net-14 terms).
INVOICES = [
    ("INV-1042", "Acme Corp", 450000, -22, "paid"),
    ("INV-1043", "BrightRetail", 275000, -14, "paid"),
    ("INV-1044", "Northwind", 180000, -4, "paid"),
    ("INV-1046", "ShopKart", 120000, 6, "open"),
    ("INV-1047", "MegaMart", 86000, 2, "open"),
    ("INV-1048", "InsightLabs", 64000, -5, "open"),     # +3 band
    ("INV-1049", "Growthly", 152000, -9, "open"),       # +3 band
    ("INV-1050", "PrimeEvents", 48000, -18, "open"),    # +15 band
    ("INV-1051", "MedSupply", 97500, -24, "open"),      # +15 band
    ("INV-1052", "LegalDocs", 73000, -34, "open"),      # +30 band
    ("INV-1053", "FitLife", 210000, -47, "open"),       # +30 band
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def seed(db_path: str = DB_PATH) -> int:
    """(Re)create the database with the seeded dataset.

    Returns the transaction count (mirrors ticketdesk seed()'s contract).
    """
    if os.path.exists(db_path):
        os.remove(db_path)
    today = datetime.now(timezone.utc).date()
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO accounts (id, name, kind, bank) VALUES (?,?,?,?)",
                         ACCOUNTS)
        conn.executemany("INSERT INTO chart_of_accounts (code, name, type) VALUES (?,?,?)",
                         CHART)
        for account_id, days_ago, payee, memo, amount, category in TXNS:
            d = today - timedelta(days=days_ago)
            conn.execute(
                "INSERT INTO transactions"
                " (account_id, date, payee, memo, amount, category, duplicate_of, created_at)"
                " VALUES (?,?,?,?,?,?,NULL,?)",
                (account_id, d.isoformat(), payee, memo, amount, category, _iso(now)),
            )
        recorded_operating = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE account_id = 1"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO statements (account_id, statement_balance, as_of) VALUES (1, ?, ?)",
            (recorded_operating + STATEMENT_DELTA, today.isoformat()),
        )
        for invoice_no, customer, amount, due_in, status in INVOICES:
            due = today + timedelta(days=due_in)
            issued = due - timedelta(days=14)
            conn.execute(
                "INSERT INTO invoices (invoice_no, customer, amount, issued_date, due_date, status)"
                " VALUES (?,?,?,?,?,?)",
                (invoice_no, customer, amount, issued.isoformat(), due.isoformat(), status),
            )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} transactions into {DB_PATH}")
