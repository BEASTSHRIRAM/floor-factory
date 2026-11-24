"""Seed data for QADesk — the deliberately realistic CI failure dataset.

6 nightly CI runs (ids 1-6; run 6 is "the overnight run" the jobs target)
and 25 failures across 5 suites, planted so the deterministic checks in
checks.py have exactly one right answer:

  - 3 FLAKY tests (>=3 failures with a pass after the first failure —
    the quarantine set):
        test_pay_now_button        F P F P F P   (TimeoutError)
        test_webhook_delivery      P F P F P F   (ECONNRESET)
        test_apply_discount_banner F P F P F F   (TimeoutError)
  - 3 REGRESSION tests (pass, then fail every run after — never flaky):
        test_cart_total_recalc     P P P F F F   (total assertion)
        test_coupon_stacking       P P P F F F   (total assertion, same cluster)
        test_session_token_issued  P P F F F F   (KeyError session_token)
  - 1 BRAND-NEW failure in run 6 (signature first seen in run 6, so the
    overnight run's new-failure count is 1 and its only consistent
    regression verdict is "regression"):
        test_search_ranking_order  P P P P P F   (ranking assertion)
  - 2 BELOW-THRESHOLD intermittent tests (passes between, but <3 fails —
    must NOT be quarantined):
        test_payment_sandbox_charge P F P P F P  (sandbox 502)
        test_invoice_email_sent     P F P F P P  (ECONNRESET)
  - 4 always-passing tests for history realism.

Run 6 failures (6): webhook_delivery, discount_banner, cart_total_recalc,
coupon_stacking, session_token_issued, search_ranking_order — spanning 5
signatures (cart + coupon share one), so clustering run 6 yields 5 clusters.

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    branch            TEXT NOT NULL DEFAULT 'main',
    commit_sha        TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'failed',  -- passed | failed
    started_at        TEXT NOT NULL,
    finished_at       TEXT NOT NULL,
    regression_verdict TEXT,                            -- regression | no_regression
    verdict_by        TEXT,
    verdict_at        TEXT
);
CREATE TABLE IF NOT EXISTS test_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id),
    test_name   TEXT NOT NULL,
    suite       TEXT NOT NULL,
    outcome     TEXT NOT NULL,                          -- pass | fail
    duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS failures (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER NOT NULL REFERENCES runs(id),
    test_result_id INTEGER REFERENCES test_results(id),
    test_name     TEXT NOT NULL,
    suite         TEXT NOT NULL,
    signature     TEXT NOT NULL,
    message       TEXT NOT NULL DEFAULT '',
    stack_excerpt TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'new',  -- new | clustered | quarantined
    cluster_id    INTEGER REFERENCES clusters(id)
);
CREATE TABLE IF NOT EXISTS clusters (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    signature  TEXT NOT NULL UNIQUE,
    title      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'qa'
);
CREATE TABLE IF NOT EXISTS triage_notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,   -- failure | cluster | run | test
    target_id   TEXT NOT NULL,
    author      TEXT NOT NULL,
    text        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantined_tests (
    test_name      TEXT PRIMARY KEY,
    author         TEXT NOT NULL,
    reason         TEXT NOT NULL DEFAULT '',
    quarantined_at TEXT NOT NULL
);
"""

# --- error signatures -------------------------------------------------------

SIG_TIMEOUT = "TimeoutError: waiting for selector '#pay-now' to be visible"
SIG_TOTAL = "AssertionError: expected order total 499.00, got 549.00"
SIG_SESSION = "KeyError: 'session_token' missing from login response"
SIG_WEBHOOK = "ConnectionError: ECONNRESET while delivering webhook"
SIG_SANDBOX = "ConnectionError: payments sandbox unreachable (502)"
SIG_RANK = "AssertionError: search result ranking order mismatch at position 1"

MESSAGES = {
    SIG_TIMEOUT: "Timed out after 10000ms waiting for the pay-now button; "
                 "page rendered the skeleton but never hydrated the CTA.",
    SIG_TOTAL: "Order total mismatch: cart shows 499.00 but checkout computed "
               "549.00 (a 50.00 delta, looks like shipping charged twice).",
    SIG_SESSION: "Login response JSON has no 'session_token' key; keys present: "
                 "['user_id', 'refresh_token', 'expires_in'].",
    SIG_WEBHOOK: "Webhook POST to the staging receiver reset mid-flight; "
                 "delivery retried 3 times and exhausted.",
    SIG_SANDBOX: "Payments sandbox returned 502 on charge creation; sandbox "
                 "status page showed degraded performance.",
    SIG_RANK: "Expected first result to be the exact-match SKU; got a sponsored "
              "listing in position 1 instead.",
}

STACKS = {
    SIG_TIMEOUT: "tests/checkout/helpers.py:88 in wait_for_pay_now\n"
                 "playwright._impl._errors.TimeoutError: Timeout 10000ms exceeded",
    SIG_TOTAL: "tests/checkout/test_cart.py:141 in test_cart_total_recalc\n"
               "assert summary.total == Decimal('499.00')",
    SIG_SESSION: "tests/auth/test_login.py:57 in test_session_token_issued\n"
                 "token = resp.json()['session_token']",
    SIG_WEBHOOK: "tests/notifications/hook_client.py:203 in deliver\n"
                 "httpx.RemoteProtocolError: Server disconnected without sending a response",
    SIG_SANDBOX: "tests/payments/gateway.py:64 in charge\n"
                 "httpx.HTTPStatusError: Server error '502 Bad Gateway'",
    SIG_RANK: "tests/search/test_ranking.py:92 in test_search_ranking_order\n"
            "assert results[0].sku == query.exact_sku",
}

# Each test: (test_name, suite, signature or None, outcomes for runs 1..6)
# P = pass, F = fail. A failure row exists exactly where the outcome is F.
TESTS = [
    # --- flaky (the quarantine set) ---
    ("tests/checkout/test_pay_now.py::test_pay_now_button",
     "checkout", SIG_TIMEOUT, "FPFPFP"),
    ("tests/notifications/test_webhooks.py::test_webhook_delivery",
     "notifications", SIG_WEBHOOK, "PFPFPF"),
    ("tests/checkout/test_promo.py::test_apply_discount_banner",
     "checkout", SIG_TIMEOUT, "FPFPFF"),
    # --- regressions (fail from some run on, never pass again) ---
    ("tests/checkout/test_cart.py::test_cart_total_recalc",
     "checkout", SIG_TOTAL, "PPPFFF"),
    ("tests/checkout/test_cart.py::test_coupon_stacking",
     "checkout", SIG_TOTAL, "PPPFFF"),
    ("tests/auth/test_login.py::test_session_token_issued",
     "auth", SIG_SESSION, "PPFFFF"),
    # --- brand-new in run 6 ---
    ("tests/search/test_ranking.py::test_search_ranking_order",
     "search", SIG_RANK, "PPPPPF"),
    # --- intermittent but below the flaky threshold (<3 fails) ---
    ("tests/payments/test_sandbox.py::test_payment_sandbox_charge",
     "payments", SIG_SANDBOX, "PFPPFP"),
    ("tests/notifications/test_email.py::test_invoice_email_sent",
     "notifications", SIG_WEBHOOK, "PFPFPP"),
    # --- always passing (history realism) ---
    ("tests/auth/test_login.py::test_login_happy_path", "auth", None, "PPPPPP"),
    ("tests/search/test_basic.py::test_search_returns_results", "search", None, "PPPPPP"),
    ("tests/payments/test_card.py::test_card_payment_success", "payments", None, "PPPPPP"),
    ("tests/checkout/test_cart.py::test_add_to_cart", "checkout", None, "PPPPPP"),
]

RUN_COUNT = 6
RUN_NAME = "nightly-main"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(run_no: int) -> str:
    return hashlib.sha1(f"floor-qa-run-{run_no}".encode()).hexdigest()[:10]


def seed(db_path: str = DB_PATH) -> dict:
    """(Re)create the database with the seeded dataset.

    Returns {"runs": n_runs, "failures": n_failures}."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        # Runs: run i finished (RUN_COUNT - i) days + 2h ago; run 6 is last night.
        run_ids = []
        for i in range(1, RUN_COUNT + 1):
            finished = now - timedelta(days=(RUN_COUNT - i), hours=2)
            started = finished - timedelta(minutes=38)
            cur = conn.execute(
                "INSERT INTO runs (name, branch, commit_sha, status, started_at,"
                " finished_at) VALUES (?,?,?,?,?,?)",
                (f"{RUN_NAME} #{230 + i}", "main", _sha(i), "failed",
                 _iso(started), _iso(finished)),
            )
            run_ids.append(cur.lastrowid)
        n_failures = 0
        for test_name, suite, signature, outcomes in TESTS:
            assert len(outcomes) == RUN_COUNT
            for idx, outcome in enumerate(outcomes):
                run_id = run_ids[idx]
                # Deterministic pseudo-duration from the names, no randomness.
                dur = 400 + (abs(hash((test_name, run_id))) % 4000)
                cur = conn.execute(
                    "INSERT INTO test_results (run_id, test_name, suite, outcome,"
                    " duration_ms) VALUES (?,?,?,?,?)",
                    (run_id, test_name, suite,
                     "pass" if outcome == "P" else "fail", dur),
                )
                if outcome == "F":
                    assert signature is not None
                    conn.execute(
                        "INSERT INTO failures (run_id, test_result_id, test_name,"
                        " suite, signature, message, stack_excerpt, status,"
                        " cluster_id) VALUES (?,?,?,?,?,?,?, 'new', NULL)",
                        (run_id, cur.lastrowid, test_name, suite, signature,
                         MESSAGES[signature], STACKS[signature]),
                    )
                    n_failures += 1
        conn.commit()
        return {"runs": len(run_ids), "failures": n_failures}
    finally:
        conn.close()


if __name__ == "__main__":
    out = seed()
    print(f"Seeded {out['runs']} runs and {out['failures']} failures into {DB_PATH}")
