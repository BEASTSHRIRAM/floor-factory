"""Seed data for ExtDesk — the SIMULATED external issue system.

ExtDesk stands in for a CUSTOMER's own issue tracker (their "Jira") so
THE FLOOR's connections layer + intake loop can be verified end-to-end
against a separate process with its own database. It is a simulator:
nothing here is Jira, and no real external account is ever touched.

A handful of issues in mixed states; timestamps relative to seed time.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extdesk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    severity    TEXT NOT NULL DEFAULT 'medium',  -- critical|high|medium|low
    status      TEXT NOT NULL DEFAULT 'Open',    -- Open|In Progress|Done
    source      TEXT NOT NULL DEFAULT 'seed',    -- seed|intake|api
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id   INTEGER NOT NULL REFERENCES issues(id),
    author     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# title, body, severity, status, created_h_ago, comments[(author, body, h_ago)]
ISSUES = [
    dict(title="Checkout page returns 500 after payment",
         body="Customers complete payment and then see a 500 error instead "
              "of the confirmation screen. Money is captured; no order "
              "confirmation is shown.",
         severity="critical", status="Open", created_h=26,
         comments=[("qa-lead", "Reproduced twice on staging with test cards.", 25)]),
    dict(title="Password reset email never arrives",
         body="Users requesting a password reset get no email. Spam folder "
              "checked. Affects roughly every third request.",
         severity="high", status="Open", created_h=9, comments=[]),
    dict(title="Dashboard chart overlaps legend on small screens",
         body="On viewports under 400px the revenue chart covers its own "
              "legend. Cosmetic but very visible.",
         severity="low", status="Open", created_h=50, comments=[]),
    dict(title="API tokens page shows revoked tokens as active",
         body="Revoked tokens still display an 'Active' badge until the "
              "page is hard-refreshed.",
         severity="medium", status="In Progress", created_h=30,
         comments=[("dev-ana", "Looks like a stale cache on the list endpoint.", 12)]),
    dict(title="Typo in onboarding email subject",
         body="'Welcom to the platfrom' — subject line of the first "
              "onboarding email has two typos.",
         severity="low", status="Done", created_h=96,
         comments=[("dev-ana", "Fixed in the template, verified in staging.", 90)]),
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def seed(path: str = DB_PATH) -> int:
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        now = datetime.now(timezone.utc)
        for spec in ISSUES:
            created = now - timedelta(hours=spec["created_h"])
            cur = conn.execute(
                """INSERT INTO issues (title, body, severity, status, source,
                       created_at, updated_at)
                   VALUES (?,?,?,?, 'seed', ?, ?)""",
                (spec["title"], spec["body"], spec["severity"],
                 spec["status"], _iso(created), _iso(created)))
            issue_id = int(cur.lastrowid)
            for author, body, h_ago in spec["comments"]:
                conn.execute(
                    "INSERT INTO comments (issue_id, author, body, created_at)"
                    " VALUES (?,?,?,?)",
                    (issue_id, author, body, _iso(now - timedelta(hours=h_ago))))
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"extdesk seeded: {n} issues -> {DB_PATH}")
