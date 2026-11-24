"""Deterministic Reviewer checks for the SDR department's jobs pack.

Same contract as the TicketDesk engine's verify(): re-read LIVE workplace
state and return one finding per acceptance criterion — passed/failed is
decided by code over stored data, never by an LLM's impression.

Checks implemented:
  score_new_batch   (Job: research_score_new_leads)
    - every lead that started in the `new` batch has a score AND
      at least one non-empty reason;
    - every recorded score EQUALS rubric.compute_score(account) —
      an off-rubric score fails, however plausible its reasons sound.
  draft_qualified   (Job: draft_qualified_outreach)
    - every `qualified` lead has a stored draft (subject + body);
    - every qualified lead's draft references at least one account-
      specific signal: a deterministic phrase match against the
      account's stored tech_signals (rubric.draft_references_signal).

Usage:
    python3 checks.py score_new_batch     # exit 0 = all criteria pass
    python3 checks.py draft_qualified
    python3 checks.py all
Env: SDR_URL (default http://localhost:8105). The workplace must run.
"""
from __future__ import annotations

import json
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rubric import compute_score, draft_references_signal  # noqa: E402

BASE_URL = os.environ.get("SDR_URL", "http://localhost:8105").rstrip("/")


def _get(path: str, **params) -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        resp = client.get(path, params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()


def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": bool(passed), "detail": detail}


def check_score_new_batch() -> list[dict]:
    """The seeded `new` batch = the 10 lowest lead ids (seed contract).
    After the job runs, none of them may still be stage 'new', and all
    of them must carry rubric-exact scores with reasons."""
    leads = _get("/leads")["leads"]
    batch = sorted(leads, key=lambda l: l["id"])[:10]
    accounts = {a["id"]: a for a in _get("/accounts")["accounts"]}

    unscored = [l["id"] for l in batch
                if l["score"] is None or not l.get("score_reasons")
                or not any(r.strip() for r in l["score_reasons"])]
    f1 = _finding(
        "Every lead in the new batch has a score with reasons",
        not unscored,
        f"batch lead ids { [l['id'] for l in batch] }; unscored/reasonless: {unscored}",
    )

    off_rubric = []
    for lead in batch:
        if lead["score"] is None:
            continue
        expected, _ = compute_score(accounts[lead["account_id"]])
        if lead["score"] != expected:
            off_rubric.append(
                {"lead_id": lead["id"], "recorded": lead["score"], "expected": expected})
    f2 = _finding(
        "Every recorded score follows the ICP rubric (recomputed from account data)",
        not off_rubric,
        f"off-rubric scores: {off_rubric}" if off_rubric else "all batch scores rubric-exact",
    )
    return [f1, f2]


def check_draft_qualified() -> list[dict]:
    qualified = _get("/leads", stage="qualified")["leads"]
    accounts = {a["id"]: a for a in _get("/accounts")["accounts"]}

    missing = [l["id"] for l in qualified if not l.get("draft_body")]
    f1 = _finding(
        "Every qualified lead has a stored outreach draft",
        not missing,
        f"qualified lead ids { [l['id'] for l in qualified] }; without draft: {missing}",
    )

    generic = []
    for lead in qualified:
        if not lead.get("draft_body"):
            continue
        acct = accounts[lead["account_id"]]
        text = f"{lead.get('draft_subject') or ''} {lead['draft_body']}"
        if draft_references_signal(text, acct["tech_signals"]) is None:
            generic.append({"lead_id": lead["id"], "account": acct["name"],
                            "signals": acct["tech_signals"]})
    f2 = _finding(
        "Every qualified lead's draft references at least one account-specific signal",
        not generic,
        f"drafts with no signal reference: {generic}" if generic
        else "all qualified drafts reference a stored account signal",
    )
    return [f1, f2]


CHECKS = {
    "score_new_batch": check_score_new_batch,
    "draft_qualified": check_draft_qualified,
}


def run(check_names: list[str]) -> tuple[list[dict], bool]:
    findings: list[dict] = []
    for name in check_names:
        findings.extend(CHECKS[name]())
    return findings, all(f["passed"] for f in findings)


def main(argv: list[str]) -> int:
    names = argv[1:] or ["all"]
    if names == ["all"]:
        names = list(CHECKS)
    unknown = [n for n in names if n not in CHECKS]
    if unknown:
        print(f"unknown check(s): {unknown} (known: {sorted(CHECKS)})")
        return 2
    findings, passed = run(names)
    print(json.dumps({"checks": names, "passed": passed, "findings": findings},
                     indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
