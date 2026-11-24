"""Seed data for Engineering — the repo-lite demo dataset.

12 engineering issues, 3 pre-existing pull requests, CI results for each
PR (computed by the SAME deterministic CI rule the service runs live —
see compute_ci below), and a few engineering notes.

Planted shape (mirrors TicketDesk's planted messiness):
  - 6 solvable issues with an `acceptance` statement, acceptance keywords
    and a listed file set a correct PR must touch        (ids 1-5, 10-12 minus claimed ones)
  - 4 unlabelled issues with NO priority — the triage job's raw material (ids 6-9)
  - 2 issues already claimed / in flight                 (ids 3, 11)
  - 3 PR records: one open with green CI (PR 1, issue 3),
    one changes-requested with red CI (PR 2, issue 11),
    one APPROVED with green CI (PR 3, issue 5) — approved but NOT merged
    and its issue NOT done: merging is a human gate on THE FLOOR.

THE CI RULE (deterministic, service-owned):
  A PR passes CI iff
    (a) every keyword in the issue's acceptance_keywords appears in the
        PR's change_summary (case-insensitive), AND
    (b) the PR's files_touched is a superset of the issue's files list.
  The rule is evaluated once, at PR creation, and the outcome is stored
  as a ci_results row. It never changes afterwards — a changes-requested
  PR is answered by opening a NEW PR, exactly like re-pushing a branch.

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engineering.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    body                TEXT NOT NULL DEFAULT '',
    labels              TEXT NOT NULL DEFAULT '[]',   -- JSON list of strings
    priority            TEXT,                          -- P1..P4 or NULL (untriaged)
    status              TEXT NOT NULL DEFAULT 'open',  -- open|claimed|in_progress|pr_opened|done
    assignee            TEXT,                          -- the agent who claimed it
    acceptance          TEXT NOT NULL DEFAULT '',      -- checkable acceptance statement
    acceptance_keywords TEXT NOT NULL DEFAULT '[]',    -- JSON list; CI rule (a)
    files               TEXT NOT NULL DEFAULT '[]',    -- JSON list; CI rule (b)
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pull_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id       INTEGER NOT NULL REFERENCES issues(id),
    title          TEXT NOT NULL,
    author         TEXT NOT NULL,
    change_summary TEXT NOT NULL DEFAULT '',
    files_touched  TEXT NOT NULL DEFAULT '[]',   -- JSON list
    status         TEXT NOT NULL DEFAULT 'open', -- open|changes_requested|approved
    reviewer       TEXT,
    reviewer_note  TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ci_results (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_id      INTEGER NOT NULL REFERENCES pull_requests(id),
    status     TEXT NOT NULL,                    -- pass | fail
    detail     TEXT NOT NULL DEFAULT '',         -- which rule clauses failed, if any
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id   INTEGER NOT NULL REFERENCES issues(id),
    pr_id      INTEGER REFERENCES pull_requests(id),
    author     TEXT NOT NULL,
    text       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

PRIORITIES = ("P1", "P2", "P3", "P4")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_ci(issue: dict, change_summary: str, files_touched: list) -> tuple[str, str]:
    """The service's deterministic CI rule. Returns (status, detail).

    pass  <=> every acceptance keyword appears in the change summary AND
              every file the issue lists is touched by the PR.
    """
    summary = (change_summary or "").lower()
    keywords = json.loads(issue["acceptance_keywords"] or "[]")
    required_files = json.loads(issue["files"] or "[]")
    missing_kw = [k for k in keywords if k.lower() not in summary]
    missing_files = [f for f in required_files if f not in (files_touched or [])]
    failures = []
    if missing_kw:
        failures.append(f"change summary does not address acceptance keyword(s): {missing_kw}")
    if missing_files:
        failures.append(f"PR does not touch required file(s): {missing_files}")
    if failures:
        return "fail", "; ".join(failures)
    return "pass", "CI green: change summary addresses the acceptance criteria and all required files are touched."


# Each issue: title, body, labels, priority, status, assignee,
# acceptance, acceptance_keywords, files, created_h_ago
ISSUES = [
    # --- solvable, unclaimed (ids 1, 2, 4) ---
    dict(title="Login session not refreshed after token expiry",
         body="Users are forced to re-login when the access token expires even "
              "though a valid refresh token exists.",
         labels=["bug", "auth"], priority="P1", status="open", assignee=None,
         acceptance="Refreshing an expired session must issue a new access token "
                    "without forcing re-login.",
         acceptance_keywords=["session", "refresh", "token"],
         files=["auth/session.py", "auth/tokens.py"], created_h=30),
    dict(title="Billing webhook processed twice on retry",
         body="Stripe retries a webhook after a slow response and the customer "
              "is charged twice; deliveries carry no dedupe check.",
         labels=["bug", "billing"], priority="P1", status="open", assignee=None,
         acceptance="Duplicate webhook deliveries must be ignored via an "
                    "idempotency key check before any charge is recorded.",
         acceptance_keywords=["idempotency", "webhook"],
         files=["billing/webhooks.py"], created_h=26),
    # --- solvable, already claimed, PR 1 open against it (id 3) ---
    dict(title="Search returns stale results after index rebuild",
         body="After a reindex, cached results from the old index keep being "
              "served until the cache TTL expires.",
         labels=["bug", "search"], priority="P2", status="pr_opened", assignee="ravi",
         acceptance="After an index rebuild, the stale result cache must be "
                    "invalidated so searches hit the new index.",
         acceptance_keywords=["index", "cache"],
         files=["search/indexer.py"], created_h=50),
    dict(title="Add rate-limit headers to the public API",
         body="API consumers cannot see their remaining quota; responses should "
              "carry standard rate-limit headers.",
         labels=["feature", "api"], priority="P2", status="open", assignee=None,
         acceptance="Every public API response must include rate-limit headers "
                    "showing limit, remaining and reset.",
         acceptance_keywords=["rate-limit", "headers"],
         files=["api/middleware.py"], created_h=20),
    # --- solvable, PR 3 APPROVED against it, awaiting human merge (id 5) ---
    dict(title="CSV export truncates beyond 10k rows",
         body="Exports silently stop at 10,000 rows; finance lost a day of "
              "transactions before noticing.",
         labels=["bug", "export"], priority="P3", status="pr_opened", assignee="sana",
         acceptance="CSV export must paginate so exports larger than 10k rows "
                    "are complete.",
         acceptance_keywords=["csv", "pagination"],
         files=["export/csv_exporter.py"], created_h=90),
    # --- 4 unlabelled, no priority: the triage job's raw material (ids 6-9) ---
    dict(title="App crashes on PNG profile photos with alpha channel",
         body="Uploading a transparent PNG as a profile photo crashes the "
              "profile page for everyone who views it.",
         labels=[], priority=None, status="open", assignee=None,
         acceptance="", acceptance_keywords=[], files=[], created_h=8),
    dict(title="Dark mode for the settings page",
         body="Multiple customers asked for a dark theme on settings.",
         labels=[], priority=None, status="open", assignee=None,
         acceptance="", acceptance_keywords=[], files=[], created_h=15),
    dict(title="Invoice PDF totals do not match checkout totals",
         body="The PDF invoice shows a different grand total than the checkout "
              "page for orders with a discount code.",
         labels=[], priority=None, status="open", assignee=None,
         acceptance="", acceptance_keywords=[], files=[], created_h=12),
    dict(title="API returns 500 on an empty search query",
         body="GET /search?q= returns a 500 instead of an empty result set.",
         labels=[], priority=None, status="open", assignee=None,
         acceptance="", acceptance_keywords=[], files=[], created_h=5),
    # --- solvable, unclaimed (id 10) ---
    dict(title="Flaky checkout test blocks CI for everyone",
         body="tests/test_checkout.py fails intermittently (~1 in 5 runs) and "
              "the team has started ignoring red builds.",
         labels=["tech-debt", "ci"], priority="P3", status="open", assignee=None,
         acceptance="The flaky checkout test must be quarantined so it stops "
                    "blocking the main CI gate while it is investigated.",
         acceptance_keywords=["quarantine", "flaky"],
         files=["tests/test_checkout.py"], created_h=60),
    # --- solvable, claimed, PR 2 changes-requested against it (id 11) ---
    dict(title="Deprecated v1 endpoint still receiving production traffic",
         body="The v1 routes were supposed to be sunset last quarter; logs show "
              "steady traffic and no deprecation signal to callers.",
         labels=["tech-debt", "api"], priority="P4", status="pr_opened", assignee="meera",
         acceptance="v1 routes must emit deprecation headers with a sunset date "
                    "so callers can migrate before removal.",
         acceptance_keywords=["deprecation", "sunset"],
         files=["api/legacy_routes.py"], created_h=120),
    dict(title="Onboarding email sent twice to new users",
         body="New users receive the welcome/onboarding email two times, a few "
              "minutes apart.",
         labels=["bug", "email"], priority="P2", status="open", assignee=None,
         acceptance="Onboarding email sending must dedupe per user so exactly "
                    "one email is sent.",
         acceptance_keywords=["dedupe", "onboarding"],
         files=["email/onboarding.py"], created_h=18),
]

# Each PR: issue index (1-based), title, author, change_summary, files_touched,
# status, reviewer, reviewer_note, created_h_ago. CI is COMPUTED, never hand-set.
PRS = [
    dict(issue=3, title="Invalidate search cache on index rebuild", author="ravi",
         change_summary="Rebuild the search index cache invalidation so stale "
                        "results are dropped as soon as a reindex completes.",
         files_touched=["search/indexer.py", "search/cache.py"],
         status="open", reviewer=None, reviewer_note=None, created_h=6),
    dict(issue=11, title="Deprecation headers for v1 routes", author="meera",
         change_summary="Add deprecation headers to the v1 legacy routes.",
         files_touched=["api/legacy_routes.py"],
         status="changes_requested", reviewer="iris",
         reviewer_note="CI is red and the summary never states the sunset date "
                       "or plan — address the acceptance criteria and open a "
                       "fresh PR.", created_h=40),
    dict(issue=5, title="Paginate CSV export", author="sana",
         change_summary="Fix CSV export pagination so exports over 10k rows "
                        "are written completely instead of truncating.",
         files_touched=["export/csv_exporter.py"],
         status="approved", reviewer="iris",
         reviewer_note="CI green, acceptance criteria addressed. Ready — "
                       "merging is a human decision.", created_h=30),
]

# Each note: issue index (1-based), pr index (1-based or None), author, text, h_ago
NOTES = [
    dict(issue=1, pr=None, author="maya",
         text="Reproduced: refresh token is valid but session.py never calls "
              "the refresh path on expiry.", h_ago=10),
    dict(issue=3, pr=1, author="ravi",
         text="PR opened. Cache invalidation now hooks the reindex completion "
              "event; see change summary.", h_ago=6),
    dict(issue=11, pr=2, author="iris",
         text="Changes requested on PR 2 — see reviewer note. A new PR is "
              "needed; CI results are immutable once recorded.", h_ago=38),
]


def seed(db_path: str = DB_PATH) -> int:
    """(Re)create the database with the seeded dataset. Returns issue count."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        issue_ids = []
        for i in ISSUES:
            created = now - timedelta(hours=i["created_h"])
            cur = conn.execute(
                """INSERT INTO issues
                   (title, body, labels, priority, status, assignee, acceptance,
                    acceptance_keywords, files, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (i["title"], i["body"], json.dumps(i["labels"]), i["priority"],
                 i["status"], i["assignee"], i["acceptance"],
                 json.dumps(i["acceptance_keywords"]), json.dumps(i["files"]),
                 _iso(created), _iso(created)),
            )
            issue_ids.append(cur.lastrowid)
        pr_ids = []
        for p in PRS:
            issue_id = issue_ids[p["issue"] - 1]
            issue_row = conn.execute(
                "SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
            issue = {k: issue_row[k] for k in issue_row.keys()}
            created = now - timedelta(hours=p["created_h"])
            cur = conn.execute(
                """INSERT INTO pull_requests
                   (issue_id, title, author, change_summary, files_touched,
                    status, reviewer, reviewer_note, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (issue_id, p["title"], p["author"], p["change_summary"],
                 json.dumps(p["files_touched"]), p["status"], p["reviewer"],
                 p["reviewer_note"], _iso(created), _iso(created)),
            )
            pr_id = cur.lastrowid
            pr_ids.append(pr_id)
            status, detail = compute_ci(issue, p["change_summary"], p["files_touched"])
            conn.execute(
                "INSERT INTO ci_results (pr_id, status, detail, created_at)"
                " VALUES (?,?,?,?)",
                (pr_id, status, detail, _iso(created)),
            )
        for n in NOTES:
            conn.execute(
                "INSERT INTO notes (issue_id, pr_id, author, text, created_at)"
                " VALUES (?,?,?,?,?)",
                (issue_ids[n["issue"] - 1],
                 pr_ids[n["pr"] - 1] if n["pr"] else None,
                 n["author"], n["text"], _iso(now - timedelta(hours=n["h_ago"]))),
            )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM issues").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} issues into {DB_PATH}")
