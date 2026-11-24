"""Seed data for HRDesk — the ATS-lite demo dataset.

3 roles, each with a stated screening rubric (required skills + pass
threshold). 12 candidates:

  - 5 in `applied`   (ids 1-5)   — the unscreened applicant batch; the
                                   "Screen the new applicant batch" job's work
  - 2 in `screening` (ids 6-7)   — already screened, rubric-consistent
                                   (one pass, one hold)
  - 2 in `interview` (ids 8-9)   — screened pass + interview scheduled
  - 3 in `onboarding`(ids 10-12) — this week's joiners, each with an
                                   onboarding checklist partially done

Rubric scoring is deterministic and shared with app.py / jobs.py:
    score   = round(100 * |candidate skills ∩ role required skills|
                        / |role required skills|)
    verdict = "recommend_interview" if score >= role threshold
              else "recommend_hold"
Screening NEVER hires or rejects anyone — it produces a rubric-scored
recommendation. The hiring decision stays human (platform rule).

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hrdesk.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    key             TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    required_skills TEXT NOT NULL,   -- JSON list; the stated rubric
    pass_threshold  INTEGER NOT NULL -- minimum rubric score to recommend
);
CREATE TABLE IF NOT EXISTS candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL DEFAULT '',
    role_key        TEXT NOT NULL REFERENCES roles(key),
    stage           TEXT NOT NULL DEFAULT 'applied',
                    -- applied | screening | interview | onboarding
    source          TEXT NOT NULL DEFAULT '',  -- LinkedIn | referral | careers page | agency
    skills          TEXT NOT NULL DEFAULT '[]', -- JSON list
    screening_score INTEGER,                    -- NULL until screened
    screening_verdict TEXT,                     -- recommend_interview | recommend_hold
    screening_notes TEXT,
    screened_by     TEXT,
    screened_at     TEXT,
    applied_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interviews (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    scheduled_at TEXT NOT NULL,
    interviewer  TEXT NOT NULL DEFAULT '',
    kind         TEXT NOT NULL DEFAULT 'panel',  -- phone | panel | final
    status       TEXT NOT NULL DEFAULT 'scheduled', -- scheduled | done | cancelled
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS onboarding_steps (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    step_key     TEXT NOT NULL,
    label        TEXT NOT NULL,
    required     INTEGER NOT NULL DEFAULT 1,  -- 1 = on the required-documents list
    done         INTEGER NOT NULL DEFAULT 0,
    done_at      TEXT,
    UNIQUE(candidate_id, step_key)
);
CREATE TABLE IF NOT EXISTS hr_notes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    author       TEXT NOT NULL,
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""

ROLES = [
    dict(key="support-engineer", title="Support Engineer",
         required_skills=["ticket triage", "written communication", "sql basics"],
         pass_threshold=60),
    dict(key="backend-developer", title="Backend Developer",
         required_skills=["python", "fastapi", "postgresql", "rest apis"],
         pass_threshold=75),
    dict(key="qa-engineer", title="QA Engineer",
         required_skills=["test cases", "bug reporting", "selenium"],
         pass_threshold=67),
]

ROLES_BY_KEY = {r["key"]: r for r in ROLES}


def rubric_score(skills: list, role: dict) -> int:
    """The rubric, in code: % of the role's required skills the candidate has."""
    have = {s.strip().lower() for s in skills}
    required = role["required_skills"]
    present = sum(1 for s in required if s.strip().lower() in have)
    return round(100 * present / len(required)) if required else 0


def rubric_verdict(score: int, role: dict) -> str:
    return "recommend_interview" if score >= role["pass_threshold"] else "recommend_hold"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# Each candidate: name, email, role_key, stage, source, skills,
# applied_d_ago, screening (None or dict override of notes), interviews,
# onboarding steps (list of (step_key, label, required, done)).
CANDIDATES = [
    # --- the applied batch (ids 1-5): the screening job's work ---------------
    dict(name="Ananya Rao", email="ananya.rao@mail.in", role_key="support-engineer",
         stage="applied", source="LinkedIn", applied_d=2,
         skills=["ticket triage", "written communication", "sql basics", "zendesk"],
         screening=None, interviews=[], steps=[]),  # rubric 100 -> pass
    dict(name="Rohit Sharma", email="rohit.sharma@mail.in", role_key="support-engineer",
         stage="applied", source="careers page", applied_d=2,
         skills=["written communication", "ms excel"],
         screening=None, interviews=[], steps=[]),  # rubric 33 -> hold
    dict(name="Priya Nair", email="priya.nair@mail.in", role_key="backend-developer",
         stage="applied", source="referral", applied_d=1,
         skills=["python", "fastapi", "postgresql", "docker"],
         screening=None, interviews=[], steps=[]),  # rubric 75 -> pass
    dict(name="Karan Mehta", email="karan.mehta@mail.in", role_key="backend-developer",
         stage="applied", source="agency", applied_d=1,
         skills=["python", "javascript", "html"],
         screening=None, interviews=[], steps=[]),  # rubric 25 -> hold
    dict(name="Sneha Patil", email="sneha.patil@mail.in", role_key="qa-engineer",
         stage="applied", source="LinkedIn", applied_d=3,
         skills=["test cases", "bug reporting", "jira"],
         screening=None, interviews=[], steps=[]),  # rubric 67 -> pass
    # --- already screened (ids 6-7), rubric-consistent -----------------------
    dict(name="Vikram Reddy", email="vikram.reddy@mail.in", role_key="backend-developer",
         stage="screening", source="referral", applied_d=6,
         skills=["python", "fastapi", "postgresql", "rest apis", "redis"],
         screening=dict(notes="All four required skills evidenced in the CV and the "
                              "take-home repo. Recommend interview."),
         interviews=[], steps=[]),  # rubric 100 -> pass
    dict(name="Divya Iyer", email="divya.iyer@mail.in", role_key="support-engineer",
         stage="screening", source="careers page", applied_d=5,
         skills=["ticket triage", "phone support"],
         screening=dict(notes="Only ticket triage of the three required skills; no "
                              "written-communication sample and no SQL. Recommend "
                              "hold — a human decides whether to keep warm."),
         interviews=[], steps=[]),  # rubric 33 -> hold
    # --- in interview (ids 8-9): screened pass + interview scheduled ---------
    dict(name="Arjun Malhotra", email="arjun.m@mail.in", role_key="qa-engineer",
         stage="interview", source="LinkedIn", applied_d=9,
         skills=["test cases", "bug reporting", "selenium"],
         screening=dict(notes="Full rubric coverage; strong bug reports in the "
                              "screening exercise."),
         interviews=[dict(in_days=2, interviewer="qa-lead", kind="panel")],
         steps=[]),  # rubric 100 -> pass
    dict(name="Meera Joshi", email="meera.joshi@mail.in", role_key="backend-developer",
         stage="interview", source="referral", applied_d=8,
         skills=["python", "fastapi", "postgresql", "git"],
         screening=dict(notes="Meets the threshold exactly (3 of 4 required skills); "
                              "REST API depth to probe in the panel."),
         interviews=[dict(in_days=3, interviewer="eng-manager", kind="panel")],
         steps=[]),  # rubric 75 -> pass
    # --- this week's joiners (ids 10-12): checklists partially done ----------
    dict(name="Nikhil Verma", email="nikhil.verma@mail.in", role_key="support-engineer",
         stage="onboarding", source="LinkedIn", applied_d=21,
         skills=["ticket triage", "written communication", "sql basics"],
         screening=dict(notes="Full rubric coverage; hired by the hiring manager "
                              "(human decision, recorded outside the agent flow)."),
         interviews=[dict(in_days=-9, interviewer="support-lead", kind="final", done=True)],
         steps=[("offer_letter_signed", "Offer letter signed", 1, 1),
                ("id_proof", "Government ID proof", 1, 1),
                ("address_proof", "Address proof", 1, 0),
                ("bank_details", "Bank details for payroll", 1, 0),
                ("laptop_issued", "Laptop issued", 0, 0)]),
    dict(name="Sara Khan", email="sara.khan@mail.in", role_key="qa-engineer",
         stage="onboarding", source="careers page", applied_d=19,
         skills=["test cases", "bug reporting", "selenium", "api testing"],
         screening=dict(notes="Full rubric coverage; hired by the hiring manager "
                              "(human decision, recorded outside the agent flow)."),
         interviews=[dict(in_days=-8, interviewer="qa-lead", kind="final", done=True)],
         steps=[("offer_letter_signed", "Offer letter signed", 1, 1),
                ("id_proof", "Government ID proof", 1, 0),
                ("education_certificates", "Education certificates", 1, 0),
                ("laptop_issued", "Laptop issued", 0, 0)]),
    dict(name="Rahul Gupta", email="rahul.gupta@mail.in", role_key="backend-developer",
         stage="onboarding", source="agency", applied_d=24,
         skills=["python", "fastapi", "postgresql", "rest apis"],
         screening=dict(notes="Full rubric coverage; hired by the hiring manager "
                              "(human decision, recorded outside the agent flow)."),
         interviews=[dict(in_days=-11, interviewer="eng-manager", kind="final", done=True)],
         steps=[("offer_letter_signed", "Offer letter signed", 1, 1),
                ("id_proof", "Government ID proof", 1, 1),
                ("address_proof", "Address proof", 1, 0),
                ("relieving_letter", "Previous employer relieving letter", 1, 0),
                ("laptop_issued", "Laptop issued", 0, 0)]),
]


def seed(db_path: str = DB_PATH) -> int:
    """(Re)create the database with the seeded dataset. Returns candidate count."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        for r in ROLES:
            conn.execute(
                "INSERT INTO roles (key, title, required_skills, pass_threshold)"
                " VALUES (?,?,?,?)",
                (r["key"], r["title"], json.dumps(r["required_skills"]),
                 r["pass_threshold"]),
            )
        for c in CANDIDATES:
            role = ROLES_BY_KEY[c["role_key"]]
            applied = now - timedelta(days=c["applied_d"])
            score = verdict = notes = screened_by = screened_at = None
            if c["screening"] is not None:
                score = rubric_score(c["skills"], role)
                verdict = rubric_verdict(score, role)
                notes = c["screening"]["notes"]
                screened_by = "hr-screening"
                screened_at = _iso(applied + timedelta(days=2))
            cur = conn.execute(
                """INSERT INTO candidates
                   (name, email, role_key, stage, source, skills,
                    screening_score, screening_verdict, screening_notes,
                    screened_by, screened_at, applied_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (c["name"], c["email"], c["role_key"], c["stage"], c["source"],
                 json.dumps(c["skills"]), score, verdict, notes, screened_by,
                 screened_at, _iso(applied), _iso(applied)),
            )
            cid = cur.lastrowid
            for iv in c["interviews"]:
                when = now + timedelta(days=iv["in_days"])
                conn.execute(
                    "INSERT INTO interviews (candidate_id, scheduled_at, interviewer,"
                    " kind, status, created_at) VALUES (?,?,?,?,?,?)",
                    (cid, _iso(when), iv["interviewer"], iv["kind"],
                     "done" if iv.get("done") else "scheduled", _iso(applied)),
                )
            for step_key, label, required, done in c["steps"]:
                conn.execute(
                    "INSERT INTO onboarding_steps (candidate_id, step_key, label,"
                    " required, done, done_at) VALUES (?,?,?,?,?,?)",
                    (cid, step_key, label, required, done,
                     _iso(applied + timedelta(days=3)) if done else None),
                )
            if c["screening"] is not None:
                conn.execute(
                    "INSERT INTO hr_notes (candidate_id, author, text, created_at)"
                    " VALUES (?,?,?,?)",
                    (cid, "hr-screening", f"Screening recorded: {notes}",
                     screened_at),
                )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} candidates into {DB_PATH}")
