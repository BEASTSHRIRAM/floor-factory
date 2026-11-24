"""Battery test for the COO / E-Manager router (orchestrator/router.py).

Run from the repo root:
    .venv/bin/python -m orchestrator.test_router

Asserts the routed department for a battery of sample work items —
at least one per department plus the fallback — and that the router
emits exactly one work.routed event per call when given an emitter.
Deterministic rules only; no services need to be running.
Exits 0 and prints PASS lines when everything holds.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import router  # noqa: E402

# (title, body, expected_department, expected_routed)
BATTERY: list[tuple[str, str, str, str]] = [
    ("Checkout page crashes on payment",
     "Users hit a 500 error and an exception in the logs when they try "
     "to pay. The page goes down for them.",
     "engineering", "rule"),
    ("API returns an exception on large uploads",
     "The upload endpoint throws an exception for files over 10 MB.",
     "engineering", "rule"),
    ("Invoice #482 charged twice",
     "Please reconcile this payment against the ledger and confirm "
     "the duplicate transaction.",
     "bookkeeping", "rule"),
    ("Month-end categorisation",
     "Categorise the uncategorised transactions before we close the "
     "books and chase the outstanding receivable.",
     "bookkeeping", "rule"),
    ("New candidate for the designer role",
     "She shared her resume and looks strong — please schedule the "
     "interview and start onboarding paperwork if she clears screening.",
     "hr", "rule"),
    ("Screen this week's applicants",
     "Twelve new applicants for the support role need screening "
     "against the rubric before Friday.",
     "hr", "rule"),
    ("Angry customer threatening to churn",
     "A customer is unhappy with the renewal and is asking for a "
     "refund; they said they will cancel subscription unless we act.",
     "support", "rule"),
    ("Nightly CI is red again",
     "The nightly build has a flaky test failure in the test suite — "
     "same regression we quarantined last week is back.",
     "qa", "rule"),
    ("Warm prospect from the outbound list",
     "This lead fits the ICP; draft outreach and try for a demo "
     "booking this week to keep the pipeline moving.",
     "sdr", "rule"),
    ("Landing page lost its Google ranking",
     "Organic traffic is down 30% since the rank drop on our main "
     "keyword; the meta titles may have been overwritten.",
     "seo", "rule"),
    ("Meta descriptions for the new category pages",
     "Write meta descriptions and check keyword cannibalisation "
     "across the new category pages before they ship.",
     "seo", "rule"),
    ("Plan the office offsite",
     "Book a venue for the team offsite next quarter and sort the "
     "travel schedule.",
     "support", "fallback"),
]


def main() -> int:
    failures = 0
    events: list[tuple[str, dict]] = []

    def emit(type_: str, payload: dict) -> None:
        events.append((type_, payload))

    for title, body, want_dept, want_routed in BATTERY:
        before = len(events)
        d = router.route_work_item({"title": title, "body": body,
                                    "source": "test"}, emit=emit)
        ok = (d["department"] == want_dept and d["routed"] == want_routed
              and len(events) == before + 1
              and events[-1][0] == "work.routed"
              and events[-1][1]["department"] == want_dept)
        if want_routed == "fallback":
            ok = ok and d["matched_signals"] == [] and d["confidence"] < 0.5
        else:
            ok = ok and len(d["matched_signals"]) >= 1 and d["confidence"] >= 0.55
        print(f"{'PASS' if ok else 'FAIL'}  -> {d['department']:<12} "
              f"({d['routed']}, conf {d['confidence']}, "
              f"signals {d['matched_signals']})  {title}")
        failures += 0 if ok else 1

    # Determinism: the same item routes identically twice.
    item = {"title": BATTERY[0][0], "body": BATTERY[0][1], "source": "test"}
    assert router.route_work_item(item) == router.route_work_item(item)
    print("PASS  routing is deterministic (same item, same decision)")

    # No emitter -> no crash, same decision.
    d = router.route_work_item(item)
    assert d["department"] == "engineering"
    print("PASS  router works without an emitter")

    covered = {want for _, _, want, _ in BATTERY}
    assert covered == set(router.DEPARTMENTS), covered
    print(f"PASS  battery covers all {len(router.DEPARTMENTS)} departments "
          f"+ the fallback")

    print(f"\n{'ALL ROUTER TESTS PASSED' if failures == 0 else f'{failures} FAILURES'}"
          f" ({len(BATTERY)} items)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
