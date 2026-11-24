"""Seed data for the SDR workplace — a CRM-lite demo dataset.

15 accounts with firmographics (size, industry, tech/buying signals, last
touch) and 25 leads in stages new / researching / drafted / qualified.
Scores seeded on non-new leads are computed with rubric.compute_score, so
the seeded state already satisfies the Reviewer's deterministic checks;
the `new` batch (leads 1-10) is deliberately unscored — scoring it is
Job 1 of the department's jobs pack.

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from rubric import compute_score

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sdr.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    domain           TEXT NOT NULL DEFAULT '',
    industry         TEXT NOT NULL DEFAULT '',
    employee_count   INTEGER NOT NULL DEFAULT 0,
    country          TEXT NOT NULL DEFAULT 'India',
    tech_signals     TEXT NOT NULL DEFAULT '[]',   -- JSON list of signal keys
    last_touch_days  INTEGER,                      -- NULL = never touched
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS leads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    contact_name  TEXT NOT NULL,
    title         TEXT NOT NULL DEFAULT '',
    email         TEXT NOT NULL DEFAULT '',
    stage         TEXT NOT NULL DEFAULT 'new',  -- new|researching|drafted|qualified
    score         INTEGER,                      -- ICP score 0-100, NULL = unscored
    score_reasons TEXT,                         -- JSON list of reason strings
    draft_subject TEXT,
    draft_body    TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS crm_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,                  -- lead | account
    target_id   INTEGER NOT NULL,
    author      TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""

# Each account: name, domain, industry, employee_count, signals, last_touch_days
ACCOUNTS = [
    ("CloudKart", "cloudkart.in", "ecommerce", 220,
     ["recent_funding", "hiring_sales_team", "high_web_engagement"], 45),
    ("FinEdge Payments", "finedgepay.com", "fintech", 85,
     ["hiring_sales_team", "tech_stack_fit"], 12),
    ("MedScribe AI", "medscribe.ai", "healthtech", 40,
     ["recent_funding", "tech_stack_fit"], 60),
    ("TruckRoute", "truckroute.in", "logistics", 640,
     ["expanding_new_market"], 8),
    ("LearnLoop", "learnloop.co", "edtech", 130,
     ["high_web_engagement", "hiring_sales_team"], 33),
    ("ShopStack", "shopstack.io", "saas", 310,
     ["recent_funding", "expanding_new_market", "uses_competitor_crm",
      "hiring_sales_team"], None),
    ("PropNest", "propnest.in", "realestate", 25,
     ["high_web_engagement"], 90),
    ("SteelWorks India", "steelworks.in", "manufacturing", 900, [], 20),
    ("QuickBite Foods", "quickbite.in", "hospitality", 60,
     ["hiring_sales_team"], 5),
    ("DataDock", "datadock.io", "saas", 48,
     ["tech_stack_fit", "high_web_engagement"], 47),
    ("PayNest", "paynest.in", "fintech", 12, ["recent_funding"], 70),
    ("FleetIQ", "fleetiq.com", "logistics", 180,
     ["uses_competitor_crm", "expanding_new_market", "tech_stack_fit"], 15),
    ("ClinicOS", "clinicos.in", "healthtech", 520,
     ["expanding_new_market", "high_web_engagement"], 15),
    ("RetailRadar", "retailradar.in", "ecommerce", 8, [], 120),
    ("DevMetrics", "devmetrics.io", "saas", 95,
     ["hiring_sales_team", "recent_funding"], 28),
]

# Each lead: account index (1-based), contact, title, stage.
# Drafts (where present) reference a real signal of the lead's account.
LEADS_NEW = [  # ids 1-10 — the batch Job 1 must research + score
    (1, "Ananya Rao", "VP Sales"),
    (3, "Vikram Shetty", "Founder"),
    (4, "Meera Joshi", "Head of Growth"),
    (7, "Kabir Anand", "Sales Director"),
    (8, "Ritu Malhotra", "VP Operations"),
    (9, "Arjun Nair", "Founder"),
    (11, "Sana Iqbal", "CEO"),
    (13, "Rohan Verma", "Head of Partnerships"),
    (14, "Ishita Bose", "Owner"),
    (15, "Nikhil Menon", "VP Revenue"),
]
LEADS_RESEARCHING = [  # ids 11-16 — scored, not yet drafted/qualified
    (2, "Priya Nair", "Revenue Operations Manager"),
    (5, "Aditya Kulkarni", "Head of Sales"),
    (6, "Divya Reddy", "VP Sales"),
    (10, "Karan Malhotra", "Growth Lead"),
    (12, "Farah Khan", "Director of Sales"),
    (4, "Suresh Patil", "VP Commercial"),
]
LEADS_DRAFTED = [  # ids 17-20 — scored + a signal-referencing draft exists
    (3, "Neha Gupta", "Co-founder"),
    (5, "Manav Kapoor", "SDR Team Lead"),
    (10, "Tara Bhatt", "Head of Demand Gen"),
    (13, "Varun Iyer", "Clinic Director"),
]
LEADS_QUALIFIED = [  # ids 21-25 — scored >= threshold; 21-22 drafted, 23-25 not
    (1, "Ananya Rao", "VP Sales"),
    (6, "Rahul Khanna", "Chief Revenue Officer"),
    (12, "Farah Khan", "Director of Sales"),
    (15, "Nikhil Menon", "VP Revenue"),
    (2, "Imran Sheikh", "VP Sales"),
]

_DRAFTS = {
    3: ("Quick idea for MedScribe's next phase",
        "Hi Neha — saw MedScribe's recent funding round; teams usually "
        "spend it on pipeline. We help healthtech teams turn investor "
        "momentum into booked meetings. Open to a 15-min look?"),
    5: ("For LearnLoop's growing sales motion",
        "Hi Manav — noticed LearnLoop is hiring for its sales team. New reps "
        "ramp faster when research and first drafts are already done. "
        "Worth a short walkthrough?"),
    10: ("DataDock + your current stack",
         "Hi Tara — because DataDock's tech stack already integrates with "
         "the tools we plug into, your team could pilot in a week. "
         "Shall I send a one-pager?"),
    13: ("ClinicOS expansion outreach",
         "Hi Varun — with ClinicOS expanding into new markets, consistent "
         "outreach per region gets hard to hand-run. We draft it account by "
         "account. Open to a chat?"),
    1: ("CloudKart's post-funding pipeline",
        "Hi Ananya — congrats on the recent funding. CloudKart's sales team "
        "is growing; we help teams like yours keep research quality high "
        "while volume rises. 15 minutes next week?"),
    6: ("ShopStack: switching without the swamp",
        "Hi Rahul — teams on your current CRM often tell us reporting is "
        "the pain. We can mirror your pipeline before any switch. "
        "Worth a look?"),
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _email(contact: str, domain: str) -> str:
    first = contact.split()[0].lower()
    return f"{first}@{domain}"


def seed(db_path: str = DB_PATH) -> dict:
    """(Re)create the database with the seeded dataset.
    Returns {"accounts": n, "leads": m}."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        account_rows = {}
        for i, (name, domain, industry, size, signals, last_touch) in enumerate(ACCOUNTS, 1):
            conn.execute(
                """INSERT INTO accounts
                   (name, domain, industry, employee_count, country,
                    tech_signals, last_touch_days, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (name, domain, industry, size, "India", json.dumps(signals),
                 last_touch, _iso(now - timedelta(days=30)), _iso(now)),
            )
            account_rows[i] = {"id": i, "employee_count": size, "industry": industry,
                               "tech_signals": signals, "domain": domain}
        lead_specs = (
            [(a, c, t, "new", False, False) for a, c, t in LEADS_NEW]
            + [(a, c, t, "researching", True, False) for a, c, t in LEADS_RESEARCHING]
            + [(a, c, t, "drafted", True, True) for a, c, t in LEADS_DRAFTED]
            + [(a, c, t, "qualified", True, idx < 2)
               for idx, (a, c, t) in enumerate(LEADS_QUALIFIED)]
        )
        for account_idx, contact, title, stage, scored, drafted in lead_specs:
            acct = account_rows[account_idx]
            score, reasons = compute_score(acct) if scored else (None, None)
            subject, body = _DRAFTS.get(account_idx, (None, None)) if drafted else (None, None)
            conn.execute(
                """INSERT INTO leads
                   (account_id, contact_name, title, email, stage, score,
                    score_reasons, draft_subject, draft_body, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (account_idx, contact, title, _email(contact, acct["domain"]),
                 stage, score, json.dumps(reasons) if reasons else None,
                 subject, body, _iso(now - timedelta(days=3)), _iso(now)),
            )
        conn.commit()
        return {
            "accounts": conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "leads": conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    counts = seed()
    print(f"Seeded {counts['accounts']} accounts and {counts['leads']} leads into {DB_PATH}")
