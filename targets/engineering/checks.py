"""Deterministic Reviewer checks for the Engineering department.

Same contract as the orchestrator engine's verify step for TicketDesk:
re-read LIVE department state through the read tools and produce one
finding per acceptance criterion. No LLM judgement anywhere — a finding
is a pure function of the service's recorded state. Failed check = the
Reviewer's deterministic P1 reject, before any transcript review.

`call` is any tool-layer callable with the signature
    call(tool_name: str, args: dict) -> dict
(the factory's ToolClient in stdio or direct mode, or verify_e2e.py's
DirectClient below the line). Checks only ever use READ tools.
"""
from __future__ import annotations


def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": bool(passed), "detail": detail}


def all_passed(findings: list[dict]) -> bool:
    return all(f["passed"] for f in findings)


def check_work_issue(call, issue_id: int, worker: str) -> list[dict]:
    """Checks for job template `work_issue` (see jobs.json).

    Criteria:
      1. The issue is claimed by the worker who was awarded the job.
      2. A PR record exists, linked to the issue and authored by the worker.
      3. That PR's change summary is non-empty.
      4. A CI result is recorded for that PR.
      5. The recorded CI result is a pass (the service's own CI rule:
         summary addresses the acceptance keywords AND all files the
         issue lists are touched — for the seeded solvable issues this
         is the green-CI requirement).
    """
    findings = []
    issue = call("read_get_issue", {"issue_id": issue_id})
    if "error" in issue:
        return [_finding("issue readable", False, f"get_issue failed: {issue['error']}")]

    findings.append(_finding(
        f"Issue #{issue_id} is claimed by {worker}",
        issue.get("assignee") == worker,
        f"assignee is {issue.get('assignee')!r}"))

    pr_ids = [p["id"] for p in issue.get("pull_requests", [])]
    pr = None
    for pr_id in reversed(pr_ids):  # newest PR by this worker on this issue
        candidate = call("read_get_pr", {"pr_id": pr_id})
        if candidate.get("author") == worker:
            pr = candidate
            break
    findings.append(_finding(
        f"A PR record exists linked to issue #{issue_id}, authored by {worker}",
        pr is not None,
        f"linked PR ids: {pr_ids}; worker-authored PR: "
        f"{pr['id'] if pr else None}"))

    if pr is None:
        findings.append(_finding("PR change summary is non-empty", False,
                                 "no worker PR to inspect"))
        findings.append(_finding("CI result recorded for the PR", False,
                                 "no worker PR to inspect"))
        findings.append(_finding("CI status for the PR is pass", False,
                                 "no worker PR to inspect"))
        return findings

    summary = (pr.get("change_summary") or "").strip()
    findings.append(_finding(
        "PR change summary is non-empty",
        len(summary) > 0,
        f"summary length {len(summary)}"))

    ci = call("read_get_ci_status", {"pr_id": pr["id"]})
    recorded = "error" not in ci and ci.get("status") in ("pass", "fail")
    findings.append(_finding(
        "CI result recorded for the PR",
        recorded,
        f"ci lookup: {ci if not recorded else ci.get('status')}"))
    findings.append(_finding(
        "CI status for the PR is pass",
        recorded and ci.get("status") == "pass",
        f"ci status: {ci.get('status') if recorded else 'unrecorded'}; "
        f"detail: {ci.get('detail', '') if recorded else ''}"))
    return findings


def check_triage(call) -> list[dict]:
    """Checks for job template `triage_unlabelled` (see jobs.json).

    Criterion: every issue carries at least one label AND a priority —
    equivalently, the unlabelled queue is empty and no issue's priority
    is null.
    """
    unlabelled = call("read_list_issues", {"unlabelled": True})
    all_issues = call("read_list_issues", {})
    no_priority = [i["id"] for i in all_issues.get("issues", [])
                   if i.get("priority") is None]
    remaining = unlabelled.get("count", -1)
    return [_finding(
        "Every issue has labels and a priority assigned "
        "(unlabelled queue empty, no null priorities)",
        remaining == 0 and not no_priority,
        f"unlabelled issues remaining: {remaining}; "
        f"issues with null priority: {no_priority}")]
