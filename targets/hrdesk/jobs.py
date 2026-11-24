"""HR department jobs pack — job templates, credit budgets, and the
Reviewer's deterministic checks (mirrors orchestrator/engine.py's Family
+ verify() shape, scoped to this department so it runs standalone).

Every check re-reads LIVE HRDesk state through the tool layer and
recomputes the rubric from seed.py's own functions — a stored screening
record that disagrees with the recomputation FAILS (off-rubric verdicts
fail), an interview on a below-threshold candidate FAILS, and a joiner's
completed steps must equal exactly that joiner's required-documents list.

PLATFORM RULE: no job in this pack hires or rejects anyone. Screening
produces rubric-scored recommendations; the hiring decision stays human.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import seed as seed_module
from direct_client import DirectToolClient


class Family:
    def __init__(self, key: str, title: str, brief: str, budget: int,
                 criteria: list[str]):
        self.key, self.title, self.brief = key, title, brief
        self.budget, self.criteria = budget, criteria


JOB_FAMILIES: list[Family] = [
    Family(
        "screen_batch", "Screen the new applicant batch",
        "Screen every candidate still in the 'applied' stage. For each one, "
        "record a screening through the screen tool (the rubric score and "
        "verdict are computed by HRDesk from the role's stated required "
        "skills) with notes that cite which required skills are present "
        "and which are absent. Screening is a recommendation only — the "
        "hiring decision stays human.",
        150,
        ["Every candidate has a screening record whose stored score and "
         "verdict exactly match a recomputation of the role's rubric "
         "(required skills present/absent) — off-rubric verdicts fail"],
    ),
    Family(
        "schedule_interviews", "Schedule interviews for screening passers",
        "For every candidate whose screening verdict is "
        "recommend_interview and who has no interview yet, schedule a "
        "panel interview. Never schedule for a candidate whose screening "
        "recommends hold — HRDesk refuses those calls, and the check "
        "verifies none exist.",
        120,
        ["Every candidate whose rubric score meets the role threshold has "
         "at least one scheduled interview, and no candidate below the "
         "threshold has any interview"],
    ),
    Family(
        "onboarding_paperwork", "Complete onboarding paperwork for this week's joiners",
        "Work through each joiner's onboarding checklist and complete "
        "every outstanding step on their required-documents list. Do not "
        "complete steps that are not on the required list.",
        130,
        ["For every joiner, the set of completed onboarding steps equals "
         "exactly the joiner's required-documents list"],
    ),
]

FAMILIES_BY_KEY = {f.key: f for f in JOB_FAMILIES}


# ---------------------------------------------------------------------------
# Worker execution (deterministic reference worker, via the tool layer)
# ---------------------------------------------------------------------------

def exec_screen_batch(client: DirectToolClient, worker: str = "hr-worker") -> None:
    out = client.call_tool("read_list_candidates", {"stage": "applied"})
    for cand in out.get("candidates", []):
        role = cand["role"]
        have = {s.lower() for s in cand["skills"]}
        present = [s for s in role["required_skills"] if s.lower() in have]
        absent = [s for s in role["required_skills"] if s.lower() not in have]
        notes = (f"Required skills present: {', '.join(present) or 'none'}. "
                 f"Absent: {', '.join(absent) or 'none'}. "
                 f"Screened against the {role['title']} rubric.")
        client.call_tool("write_screen_candidate",
                         {"candidate_id": cand["id"], "notes": notes,
                          "screener": worker})


def exec_schedule_interviews(client: DirectToolClient,
                             worker: str = "hr-worker") -> None:
    when = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    out = client.call_tool("read_list_candidates", {})
    for cand in out.get("candidates", []):
        if cand["screening_verdict"] != "recommend_interview":
            continue
        full = client.call_tool("read_get_candidate", {"candidate_id": cand["id"]})
        if any(iv["status"] == "scheduled" for iv in full.get("interviews", [])):
            continue
        client.call_tool("write_schedule_interview",
                         {"candidate_id": cand["id"], "scheduled_at": when,
                          "interviewer": "hiring-panel", "kind": "panel"})


def exec_onboarding_paperwork(client: DirectToolClient,
                              worker: str = "hr-worker") -> None:
    out = client.call_tool("read_list_onboarding", {})
    for joiner in out.get("joiners", []):
        for step in joiner["steps"]:
            if step["required"] and not step["done"]:
                client.call_tool(
                    "write_complete_onboarding_step",
                    {"candidate_id": joiner["candidate_id"],
                     "step_key": step["step_key"]})


EXECUTORS: dict[str, Callable[..., None]] = {
    "screen_batch": exec_screen_batch,
    "schedule_interviews": exec_schedule_interviews,
    "onboarding_paperwork": exec_onboarding_paperwork,
}


# ---------------------------------------------------------------------------
# Deterministic verification (the Reviewer's checks)
# ---------------------------------------------------------------------------

def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": bool(passed), "detail": detail}


def _all_candidates(client: DirectToolClient) -> list[dict]:
    return client.call_tool("read_list_candidates", {}).get("candidates", [])


def verify_screen_batch(client: DirectToolClient) -> list[dict]:
    criterion = FAMILIES_BY_KEY["screen_batch"].criteria[0]
    problems = []
    for cand in _all_candidates(client):
        role = cand["role"]
        expected_score = seed_module.rubric_score(cand["skills"], role)
        expected_verdict = seed_module.rubric_verdict(expected_score, role)
        if cand["screening_verdict"] is None:
            problems.append(f"candidate {cand['id']} ({cand['name']}) unscreened")
        elif cand["screening_score"] != expected_score or \
                cand["screening_verdict"] != expected_verdict:
            problems.append(
                f"candidate {cand['id']} ({cand['name']}): stored "
                f"{cand['screening_score']}/{cand['screening_verdict']} != "
                f"rubric {expected_score}/{expected_verdict} (off-rubric)")
    return [_finding(criterion, not problems,
                     "; ".join(problems) if problems else
                     "all screening records match the rubric recomputation")]


def verify_schedule_interviews(client: DirectToolClient) -> list[dict]:
    criterion = FAMILIES_BY_KEY["schedule_interviews"].criteria[0]
    problems = []
    for cand in _all_candidates(client):
        role = cand["role"]
        score = seed_module.rubric_score(cand["skills"], role)
        passed = score >= role["pass_threshold"]
        full = client.call_tool("read_get_candidate",
                                {"candidate_id": cand["id"]})
        scheduled = [iv for iv in full.get("interviews", [])
                     if iv["status"] == "scheduled"]
        if passed and cand["stage"] != "onboarding" and not scheduled:
            problems.append(
                f"candidate {cand['id']} ({cand['name']}) passed the rubric "
                f"({score}) but has no scheduled interview")
        if not passed and scheduled:
            problems.append(
                f"candidate {cand['id']} ({cand['name']}) is below threshold "
                f"({score} < {role['pass_threshold']}) but has "
                f"{len(scheduled)} scheduled interview(s)")
    return [_finding(criterion, not problems,
                     "; ".join(problems) if problems else
                     "interviews exist exactly for rubric passers")]


def verify_onboarding_paperwork(client: DirectToolClient) -> list[dict]:
    criterion = FAMILIES_BY_KEY["onboarding_paperwork"].criteria[0]
    problems = []
    out = client.call_tool("read_list_onboarding", {})
    for joiner in out.get("joiners", []):
        required = set(joiner["required_documents"])
        completed = {s["step_key"] for s in joiner["steps"] if s["done"]}
        if completed != required:
            problems.append(
                f"joiner {joiner['candidate_id']} ({joiner['candidate_name']}): "
                f"completed {sorted(completed)} != required {sorted(required)}")
    return [_finding(criterion, not problems,
                     "; ".join(problems) if problems else
                     "every joiner's completed steps exactly match the "
                     "required-documents list")]


VERIFIERS: dict[str, Callable[..., list]] = {
    "screen_batch": verify_screen_batch,
    "schedule_interviews": verify_schedule_interviews,
    "onboarding_paperwork": verify_onboarding_paperwork,
}


def run_job(client: DirectToolClient, family_key: str) -> dict[str, Any]:
    """Execute one job end-to-end and return the Reviewer's findings."""
    fam = FAMILIES_BY_KEY[family_key]
    EXECUTORS[family_key](client)
    findings = VERIFIERS[family_key](client)
    return {"job": fam.key, "title": fam.title, "budget_credits": fam.budget,
            "verdict": "accept" if all(f["passed"] for f in findings) else "reject",
            "findings": findings}
