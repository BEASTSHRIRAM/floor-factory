"""Seed data for TicketDesk — the deliberately messy demo dataset.

25 tickets with planted messiness (ARCHITECTURE §6.1):
  - exactly 6 unassigned tickets, 2 of them P1          (ids 7-12)
  - 4 duplicates of 2 originals                          (ids 2,3 dup of 1; ids 5,6 dup of 4)
  - 5 stale `resolved` tickets never closed              (ids 13-17; id 17 has NO resolution comment)
  - 3 SLA-breached tickets                               (ids 18-20)
  - inconsistent categories: billing / Billing / billng (typo) / Login Issue / ...
  - 2 angry-customer tickets                             (ids 21-22)

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ticketdesk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    customer    TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT 'general',
    priority    TEXT NOT NULL DEFAULT 'P3',
    status      TEXT NOT NULL DEFAULT 'new',
    assignee    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    resolved_at TEXT,
    sla_due_at  TEXT,
    merged_into INTEGER
);
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id),
    author     TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'comment',   -- comment | escalation | resolution
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# SLA hours by priority, used for tickets created via POST /tickets.
SLA_HOURS = {"P1": 4, "P2": 24, "P3": 72, "P4": 120}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Each ticket: subject, body, customer, category, priority, status, assignee,
# created_h_ago, resolved_h_ago (or None), sla_due_h_from_now (negative = past),
# comments: list of (author, kind, text, h_ago)
TICKETS = [
    # --- duplicate group A: login (original id 1, duplicates ids 2-3) ---
    dict(subject="Cannot login to portal",
         body="Since yesterday I get 'invalid session' every time I sign in.",
         customer="priya@acme.in", category="login", priority="P2",
         status="open", assignee="ravi", created_h=48, resolved_h=None, sla_due_h=20,
         comments=[("ravi", "comment", "Looking into the session store now.", 40)]),
    dict(subject="Re: Cannot login to portal",
         body="Same issue as my earlier mail - invalid session on login.",
         customer="priya@acme.in", category="Login Issue", priority="P2",
         status="open", assignee="ravi", created_h=24, resolved_h=None, sla_due_h=30,
         comments=[]),
    dict(subject="cannot login to portal!!",
         body="login broken pls fix asap",
         customer="priya@acme.in", category="login", priority="P3",
         status="new", assignee="meera", created_h=5, resolved_h=None, sla_due_h=60,
         comments=[]),
    # --- duplicate group B: double charge (original id 4, duplicates ids 5-6) ---
    dict(subject="Charged twice for subscription",
         body="Two charges of Rs 4,999 on my card for the same month. Please refund one.",
         customer="orders@brightretail.com", category="billing", priority="P1",
         status="open", assignee="meera", created_h=24, resolved_h=None, sla_due_h=6,
         comments=[("meera", "comment", "Checking with the payments team.", 20)]),
    dict(subject="Charged twice for subscription",
         body="I was charged twice for my subscription this month.",
         customer="orders@brightretail.com", category="Billing", priority="P2",
         status="new", assignee="ravi", created_h=20, resolved_h=None, sla_due_h=40,
         comments=[]),
    dict(subject="Charged twice for subscription.",
         body="Duplicate charge on card ending 4412.",
         customer="orders@brightretail.com", category="billng", priority="P2",
         status="open", assignee="ravi", created_h=18, resolved_h=None, sla_due_h=44,
         comments=[]),
    # --- 6 unassigned (ids 7-12), 2 of them P1 (ids 7-8) ---
    dict(subject="Production API down for our account",
         body="All API calls return 503 since 09:00. Our checkout is down.",
         customer="tech@shopkart.io", category="technical", priority="P1",
         status="new", assignee=None, created_h=3, resolved_h=None, sla_due_h=2,
         comments=[]),
    dict(subject="Payment gateway failing at checkout",
         body="Customers see 'payment failed' but the money is deducted.",
         customer="support@megamart.in", category="billing", priority="P1",
         status="open", assignee=None, created_h=2, resolved_h=None, sla_due_h=3,
         comments=[]),
    dict(subject="Need invoice copy for March",
         body="Please share the GST invoice copy for March for our accounts team.",
         customer="finance@northwind.co", category="Billing", priority="P2",
         status="new", assignee=None, created_h=24, resolved_h=None, sla_due_h=30,
         comments=[]),
    dict(subject="How to export reports to Excel?",
         body="Is there a way to export the monthly report as .xlsx?",
         customer="ops@deltaexports.com", category="product", priority="P3",
         status="new", assignee=None, created_h=48, resolved_h=None, sla_due_h=50,
         comments=[]),
    dict(subject="Password reset email not arriving",
         body="Requested a reset twice, nothing in inbox or spam.",
         customer="karan@smallbiz.in", category="login", priority="P2",
         status="open", assignee=None, created_h=8, resolved_h=None, sla_due_h=20,
         comments=[]),
    dict(subject="Feature request: dark mode for dashboard",
         body="Our team works nights; a dark mode would help a lot.",
         customer="nina@designhub.co", category="product", priority="P4",
         status="new", assignee=None, created_h=72, resolved_h=None, sla_due_h=100,
         comments=[]),
    # --- 5 stale resolved, never closed (ids 13-17) ---
    dict(subject="Refund for cancelled order",
         body="Order cancelled last week, refund still not received.",
         customer="amit@homeneeds.in", category="billing", priority="P2",
         status="resolved", assignee="meera", created_h=24 * 14, resolved_h=24 * 12,
         sla_due_h=-24 * 10,
         comments=[("meera", "resolution", "Refund issued to source account, txn ref RF-2211.", 24 * 12)]),
    dict(subject="Change billing address",
         body="Please update our billing address to the new office in Pune.",
         customer="admin@cloudnine.io", category="account", priority="P3",
         status="resolved", assignee="ravi", created_h=24 * 17, resolved_h=24 * 15,
         sla_due_h=-24 * 13,
         comments=[("ravi", "resolution", "Address updated and confirmed over email.", 24 * 15)]),
    dict(subject="Coupon code not applying",
         body="WELCOME20 shows invalid at checkout.",
         customer="sara@trendywear.com", category="product", priority="P3",
         status="resolved", assignee="sana", created_h=24 * 10, resolved_h=24 * 9,
         sla_due_h=-24 * 7,
         comments=[("sana", "resolution", "Coupon was expired; issued a fresh code WELCOME25.", 24 * 9)]),
    dict(subject="GST invoice correction needed",
         body="GSTIN on the invoice is wrong, need a corrected copy.",
         customer="accounts@shreelogistics.in", category="billng", priority="P2",
         status="resolved", assignee="meera", created_h=24 * 22, resolved_h=24 * 20,
         sla_due_h=-24 * 18,
         comments=[("meera", "resolution", "Corrected invoice INV-8841 re-issued with the right GSTIN.", 24 * 20)]),
    dict(subject="App crashes on file upload",
         body="Uploading a PDF larger than 2MB crashes the app.",
         customer="dev@legaldocs.co", category="technical", priority="P2",
         status="resolved", assignee="ravi", created_h=24 * 12, resolved_h=24 * 11,
         sla_due_h=-24 * 9,
         comments=[("dev@legaldocs.co", "comment", "Any update on this? We still cannot upload.", 24 * 11 + 2)]),
    # --- 3 SLA-breached (ids 18-20) ---
    dict(subject="Enterprise SSO not working",
         body="SAML login fails for all 40 users in our org since the last update.",
         customer="it@bigcorp.com", category="technical", priority="P1",
         status="in_progress", assignee="meera", created_h=24 * 4, resolved_h=None,
         sla_due_h=-48,
         comments=[("meera", "comment", "Reproduced with their IdP metadata; investigating.", 50)]),
    dict(subject="Data export stuck at 99%",
         body="Full account export has been stuck at 99% for two days.",
         customer="data@insightlabs.ai", category="technical", priority="P2",
         status="open", assignee="ravi", created_h=24 * 3, resolved_h=None,
         sla_due_h=-24, comments=[]),
    dict(subject="Billing discrepancy in annual plan",
         body="We were billed for 55 seats but only have 48 active users.",
         customer="finance@growthly.io", category="Billing", priority="P2",
         status="open", assignee="meera", created_h=24 * 5, resolved_h=None,
         sla_due_h=-72, comments=[]),
    # --- 2 angry customers (ids 21-22) ---
    dict(subject="THIRD time I am writing - nobody responds!!!",
         body="I have raised this twice before. If this is not fixed today we are "
              "cancelling our contract. This is unacceptable.",
         customer="director@primeevents.in", category="account", priority="P1",
         status="open", assignee="ravi", created_h=24, resolved_h=None, sla_due_h=5,
         comments=[]),
    dict(subject="Worst support ever - refund everything NOW",
         body="Your app charged me after I cancelled. I want a full refund today or "
              "I am posting this everywhere.",
         customer="rohit@fitlife.in", category="Billing", priority="P2",
         status="open", assignee="meera", created_h=12, resolved_h=None, sla_due_h=12,
         comments=[]),
    # --- 3 ordinary tickets (ids 23-25) ---
    dict(subject="Schedule onboarding call",
         body="We signed up yesterday; please schedule the onboarding call.",
         customer="hr@newhire.co", category="account", priority="P3",
         status="in_progress", assignee="sana", created_h=48, resolved_h=None, sla_due_h=40,
         comments=[("sana", "comment", "Sent calendar invite for Thursday 11am.", 30)]),
    dict(subject="API rate limit increase request",
         body="We are hitting the 1k/min limit; request an increase to 5k/min.",
         customer="platform@finlytics.com", category="technical", priority="P3",
         status="open", assignee="ravi", created_h=24, resolved_h=None, sla_due_h=60,
         comments=[]),
    dict(subject="Login issue after password change",
         body="Could not login after changing my password; support fixed it on call.",
         customer="omar@medsupply.co", category="login", priority="P4",
         status="closed", assignee="sana", created_h=24 * 6, resolved_h=24 * 5,
         sla_due_h=-24 * 4,
         comments=[("sana", "resolution", "Password reset and session cleared on call; verified login works.", 24 * 5)]),
]


def seed(db_path: str = DB_PATH) -> int:
    """(Re)create the database with the seeded dataset. Returns ticket count."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        for t in TICKETS:
            created = now - timedelta(hours=t["created_h"])
            resolved = now - timedelta(hours=t["resolved_h"]) if t["resolved_h"] else None
            sla_due = now + timedelta(hours=t["sla_due_h"])
            cur = conn.execute(
                """INSERT INTO tickets
                   (subject, body, customer, category, priority, status, assignee,
                    created_at, updated_at, resolved_at, sla_due_at, merged_into)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (t["subject"], t["body"], t["customer"], t["category"], t["priority"],
                 t["status"], t["assignee"], _iso(created),
                 _iso(resolved or created), _iso(resolved) if resolved else None,
                 _iso(sla_due)),
            )
            ticket_id = cur.lastrowid
            for author, kind, text, h_ago in t["comments"]:
                conn.execute(
                    "INSERT INTO comments (ticket_id, author, kind, text, created_at)"
                    " VALUES (?,?,?,?,?)",
                    (ticket_id, author, kind, text, _iso(now - timedelta(hours=h_ago))),
                )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} tickets into {DB_PATH}")
