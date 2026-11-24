"""THE FLOOR — the COO / E-Manager router (DESIGN_NOTES §6).

The whiteboard's "E-Manager": the manager-of-managers that takes work
arriving WITHOUT a department on it — an intake event on a connection
with no fixed department mapping, a free-form request — and decides
which department owns it.

Deterministic rules only. No LLM call, no learned model: a documented
signal table (below) is matched against the item's title + body, each
department scores one point per distinct signal it matches, and the
highest score wins. Ties break by the table's priority order (most
specific departments first; Support last because its signals are the
most generic). An item matching nothing routes to Support with
``routed="fallback"`` — Support is the floor's front door, and the
fallback is always NAMED, never silent.

Signal table (lowercase substrings, matched against title + body):

    qa           flaky, test failure, failing test, regression, ci run,
                 test suite, nightly build, quarantine
    engineering  bug, crash, error, exception, 500, outage, downtime,
                 stack trace, broken build, api down
    bookkeeping  invoice, payment, reconcile, reconciliation,
                 transaction, ledger, receivable, expense report,
                 categorise, categorize
    hr           candidate, interview, resume, cv, applicant, hiring,
                 onboarding, screen applicants
    sdr          prospect, lead, outreach, cold email, pipeline,
                 demo booking
    seo          seo, ranking, rank drop, traffic, keyword, meta,
                 organic, serp, google search
    support      churn, complaint, refund, customer, support ticket,
                 escalation, unhappy, cancel subscription

The decision is explainable by construction: route_work_item returns
{department, matched_signals, confidence, routed, scores} — the winning
department's matched signals and every department's score — and, when
an ``emit`` callable is supplied, fires a ``work.routed`` event with
the same payload so the routing is visible on the floor's event stream
(the API passes its event emitter; the engine could pass its own).

Confidence is a pure function of the winner's signal count:
1 signal -> 0.55, 2 -> 0.70, 3 -> 0.85, 4+ -> 0.95; fallback -> 0.25.
It expresses how much evidence the rules found — nothing more.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

# Priority order = tie-break order (most specific first).
SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    ("qa", ("flaky", "test failure", "failing test", "regression",
            "ci run", "test suite", "nightly build", "quarantine")),
    ("engineering", ("bug", "crash", "error", "exception", "500",
                     "outage", "downtime", "stack trace", "broken build",
                     "api down")),
    ("bookkeeping", ("invoice", "payment", "reconcile", "reconciliation",
                     "transaction", "ledger", "receivable",
                     "expense report", "categorise", "categorize")),
    ("hr", ("candidate", "interview", "resume", "cv", "applicant",
            "hiring", "onboarding", "screen applicants")),
    ("sdr", ("prospect", "lead", "outreach", "cold email", "pipeline",
             "demo booking")),
    ("seo", ("seo", "ranking", "rank drop", "traffic", "keyword", "meta",
             "organic", "serp", "google search")),
    ("support", ("churn", "complaint", "refund", "customer",
                 "support ticket", "escalation", "unhappy",
                 "cancel subscription")),
]

DEPARTMENTS: tuple[str, ...] = tuple(d for d, _ in SIGNALS)
FALLBACK_DEPARTMENT = "support"

_CONFIDENCE = {0: 0.25, 1: 0.55, 2: 0.70, 3: 0.85}


def _confidence(signal_count: int) -> float:
    if signal_count >= 4:
        return 0.95
    return _CONFIDENCE[signal_count]


def route_work_item(item: dict, *,
                    emit: Optional[Callable[[str, dict], None]] = None
                    ) -> dict:
    """Route one work item {title, body, source} to a department.

    Pure and deterministic: same item in, same decision out. When
    ``emit`` is given it is called once as emit("work.routed", payload)
    with the full decision (the API wires this to the floor event log).
    """
    title = str(item.get("title", "") or "")
    body = str(item.get("body", "") or "")
    source = str(item.get("source", "") or "")
    text = f"{title}\n{body}".lower()

    matched: dict[str, list[str]] = {}
    for department, signals in SIGNALS:
        hits = [s for s in signals if s in text]
        if hits:
            matched[department] = hits
    scores = {d: len(hits) for d, hits in matched.items()}

    if matched:
        # Highest score wins. max() returns the first maximal element,
        # and SIGNALS is in priority order — so a tie resolves to the
        # most specific department, deterministically.
        department = max(SIGNALS, key=lambda kv: scores.get(kv[0], 0))[0]
        signals = matched[department]
        routed = "rule"
        confidence = _confidence(len(signals))
    else:
        department = FALLBACK_DEPARTMENT
        signals = []
        routed = "fallback"
        confidence = _confidence(0)

    decision: dict[str, Any] = {
        "department": department,
        "matched_signals": signals,
        "confidence": confidence,
        "routed": routed,
        "scores": scores,
        "title": title,
        "source": source,
    }
    if emit is not None:
        emit("work.routed", dict(decision))
    return decision
