"""Department registration for THE FLOOR — the non-Support workplaces.

Each department in targets/ ships as a standalone workplace (its own
system of record, MCP server file, jobs pack and deterministic checks).
This module is the integration seam the department builds left behind:
it loads each department's own jobs pack + check/worker modules and
adapts them to the engine's Family contract, so a shift (manual or the
auto-run loop, which consumes JOB_FAMILIES generically) posts jobs for
every department through the same bid → award → execute → review →
appeal machinery as Support.

Adapter contract (engine side):
  execute(engine, family, wo_id, worker)  — do the work via engine.call
  check(engine, family, wo_id, worker_name) -> findings
      [{"criterion": str, "passed": bool, "detail": str}]

Every check below is the department's OWN deterministic check module —
nothing here re-implements a rubric. Where a department's check uses a
slightly different finding shape (bookkeeping: pass/evidence) it is
normalised at this seam, not edited at the source.

Known exclusion — engineering `answer_changes_requested`: the template's
acceptance criteria require the awarded worker to claim issue #11 and
open a fresh PR on it, but the seed leaves issue #11 claimed by "meera"
(a seed persona, not a floor worker) and the workplace's claim rule
refuses re-claims (409). The criteria are therefore unreachable through
the tool surface in the seeded state, so the family is NOT registered —
posting an un-completable job every cycle would be theatre, not work.
The template stays in targets/engineering/jobs.json; reseeding issue
#11 unclaimed makes it registrable with no code change here.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS = REPO_ROOT / "targets"

DEPT_LABELS = {
    "support": "Support",
    "qa": "QA triage",
    "bookkeeping": "Bookkeeping",
    "sdr": "SDR",
    "engineering": "Engineering",
    "hr": "HR",
}


def _load(name: str, rel: str):
    """Load a department module from its file, under a unique name."""
    spec = importlib.util.spec_from_file_location(name, TARGETS / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ctx(engine, wo_id: int) -> dict:
    return engine._job_ctx.setdefault(wo_id, {})


# ---------------------------------------------------------------------------
# QA triage (server "qa") — checks + worker logic from targets/qa
# ---------------------------------------------------------------------------

_qa_checks = None


def _qa():
    global _qa_checks
    if _qa_checks is None:
        _qa_checks = _load("floor_qa_checks", "qa/checks.py")
    return _qa_checks


def _qa_latest_run(call) -> int:
    runs = call("read_list_runs", {})["runs"]
    return max(r["id"] for r in runs)


def _qa_exec_cluster(engine, family, wo_id, worker):
    call = engine.dept_call("qa", wo_id, worker["name"])
    run_id = _qa_latest_run(call)
    _ctx(engine, wo_id)["run_id"] = run_id
    call("read_list_failures", {"run_id": run_id})
    out = call("write_cluster_failures", {"run_id": run_id, "author": worker["name"]})
    for c in out.get("clusters", []):
        call("write_add_triage_note", {
            "target_type": "cluster", "target_id": str(c["id"]),
            "author": worker["name"],
            "text": f"Cluster of {c['count']} failure(s) sharing signature: {c['signature']}"})


def _qa_exec_quarantine(engine, family, wo_id, worker):
    call = engine.dept_call("qa", wo_id, worker["name"])
    for test_name in sorted(_qa().expected_flaky_tests(call)):
        call("write_quarantine_test", {
            "test_name": test_name, "author": worker["name"],
            "reason": "Flaky per recorded history: >=3 failures with a pass "
                      "after the first failure."})
        call("write_add_triage_note", {
            "target_type": "test", "target_id": test_name, "author": worker["name"],
            "text": "Quarantined as flaky; removed from the regression signal."})


def _qa_exec_verdict(engine, family, wo_id, worker):
    call = engine.dept_call("qa", wo_id, worker["name"])
    run_id = _qa_latest_run(call)
    _ctx(engine, wo_id)["run_id"] = run_id
    failures = call("read_list_failures", {"run_id": run_id})["failures"]
    new_count = sum(1 for f in failures if f["is_new_signature"])
    verdict = _qa().expected_verdict(new_count)
    call("write_set_regression_verdict", {
        "run_id": run_id, "verdict": verdict, "author": worker["name"],
        "note": f"{new_count} failure(s) with a brand-new signature in this run."})


def _qa_check(key):
    def check(engine, family, wo_id, worker_name):
        call = engine.dept_call("qa", wo_id, worker_name)
        criterion = family.criteria[0]
        fn = _qa().CHECKS[key]
        if key in ("cluster_failures", "regression_verdict"):
            run_id = _ctx(engine, wo_id).get("run_id") or _qa_latest_run(call)
            return fn(call, criterion, run_id=run_id)
        return fn(call, criterion)
    return check


_QA_EXEC = {
    "cluster_failures": _qa_exec_cluster,
    "quarantine_flaky": _qa_exec_quarantine,
    "regression_verdict": _qa_exec_verdict,
}


# ---------------------------------------------------------------------------
# Bookkeeping (server "bookkeeping") — jobs.py ships Family + WORKERS + CHECKS
# ---------------------------------------------------------------------------

_bk_jobs = None


def _bk():
    global _bk_jobs
    if _bk_jobs is None:
        _bk_jobs = _load("floor_bookkeeping_jobs", "bookkeeping/jobs.py")
    return _bk_jobs


def _bk_exec(key):
    def execute(engine, family, wo_id, worker):
        call = engine.dept_call("bookkeeping", wo_id, worker["name"])
        _bk().WORKERS[key](call)
    return execute


def _bk_check(key):
    def check(engine, family, wo_id, worker_name):
        call = engine.dept_call("bookkeeping", wo_id, worker_name)
        findings = _bk().CHECKS[key](call)
        # Bookkeeping findings use {pass, evidence}; normalise to the
        # engine's {passed, detail} shape at this seam.
        return [{"criterion": f["criterion"], "passed": bool(f["pass"]),
                 "detail": f["evidence"]} for f in findings]
    return check


# ---------------------------------------------------------------------------
# SDR (server "sdr") — rubric-driven scoring + drafts; checks are the
# department's own HTTP checks (targets/sdr/checks.py, SDR_URL env)
# ---------------------------------------------------------------------------

_sdr_rubric = None
_sdr_checks = None


def _sdr():
    global _sdr_rubric, _sdr_checks
    if _sdr_rubric is None:
        _sdr_rubric = _load("floor_sdr_rubric", "sdr/rubric.py")
        _sdr_checks = _load("floor_sdr_checks", "sdr/checks.py")
    return _sdr_rubric, _sdr_checks


_SIGNAL_SENTENCE = {
    "recent_funding": "raised new funding recently",
    "hiring_sales_team": "hiring and growing your sales team",
    "expanding_new_market": "expanding into a new market",
    "uses_competitor_crm": "using a competitor crm today",
    "high_web_engagement": "visited our pricing page recently",
    "tech_stack_fit": "running a tech stack we integrate with natively",
}


def _sdr_exec_score(engine, family, wo_id, worker):
    rubric, _ = _sdr()
    call = engine.dept_call("sdr", wo_id, worker["name"])
    leads = call("list_leads", {"stage": "new"})["leads"]
    for lead in leads:
        research = call("research_account", {"account_id": lead["account_id"]})
        score, reasons = rubric.compute_score(research["account"])
        call("score_lead", {"lead_id": lead["id"], "score": score, "reasons": reasons})


def _sdr_exec_draft(engine, family, wo_id, worker):
    rubric, _ = _sdr()
    call = engine.dept_call("sdr", wo_id, worker["name"])
    leads = call("list_leads", {"stage": "qualified"})["leads"]
    for lead in leads:
        if lead.get("draft_body"):
            continue
        res = call("get_account", {"account_id": lead["account_id"]})
        account = res.get("account", res)
        signals = account.get("tech_signals") or []
        if not signals:
            continue
        signal = signals[0]
        sentence = _SIGNAL_SENTENCE.get(signal) or rubric.SIGNAL_PHRASES[signal][0]
        subject = f"Quick note for {account['name']}"
        body = (f"Hi {lead['contact_name']}, noticed {account['name']} is "
                f"{sentence} — teams at that stage usually feel the squeeze "
                "in their pipeline. We help teams like yours book more "
                "meetings without adding headcount. Worth a short look?")
        call("draft_outreach", {"lead_id": lead["id"], "subject": subject, "body": body})


def _sdr_check(check_name):
    def check(engine, family, wo_id, worker_name):
        _, checks = _sdr()
        return checks.CHECKS[check_name]()
    return check


# ---------------------------------------------------------------------------
# Engineering (server "engineering") — checks from targets/engineering
# ---------------------------------------------------------------------------

_eng_checks = None


def _eng():
    global _eng_checks
    if _eng_checks is None:
        _eng_checks = _load("floor_eng_checks", "engineering/checks.py")
    return _eng_checks


def _eng_exec_work_issue(engine, family, wo_id, worker):
    call = engine.dept_call("engineering", wo_id, worker["name"])
    name = worker["name"]
    issues = call("read_list_issues", {})["issues"]
    solvable = [i for i in issues if not i.get("assignee")]
    chosen = None
    for stub in sorted(solvable, key=lambda i: i["id"]):
        full = call("read_get_issue", {"issue_id": stub["id"]})
        if full.get("acceptance_keywords"):
            chosen = full
            break
    if chosen is None:
        raise RuntimeError("engineering: no unclaimed solvable issue available")
    issue_id = chosen["id"]
    _ctx(engine, wo_id)["issue_id"] = issue_id
    call("write_claim_issue", {"issue_id": issue_id, "assignee": name})
    summary = (f"{chosen['acceptance']} Delivered: "
               + ", ".join(chosen["acceptance_keywords"]) + ".")
    pr = call("write_open_pr", {
        "issue_id": issue_id, "author": name,
        "title": f"Fix #{issue_id}: {chosen['title']}",
        "change_summary": summary,
        "files_touched": list(chosen["files"])})
    call("read_get_ci_status", {"pr_id": pr["id"]})
    call("write_add_eng_note", {
        "issue_id": issue_id, "author": name,
        "text": "PR opened with CI evaluated by the service rule; merge is "
                "a human decision.", "pr_id": pr["id"]})


def _eng_exec_triage(engine, family, wo_id, worker):
    call = engine.dept_call("engineering", wo_id, worker["name"])
    unlabelled = call("read_list_issues", {"unlabelled": True})["issues"]
    for stub in unlabelled:
        full = call("read_get_issue", {"issue_id": stub["id"]})
        text = f"{full.get('title', '')} {full.get('body', '')}".lower()
        labels: list[str] = []
        if any(k in text for k in ("crash", "error", "500", "fail", "mismatch",
                                   "duplicate", "twice", "broken", "sent two")):
            labels.append("bug")
        else:
            labels.append("feature")
        if any(k in text for k in ("mobile", "android", "viewer", "app")):
            labels.append("mobile")
        elif any(k in text for k in ("billing", "money", "invoice", "charge", "export")):
            labels.append("billing" if "billing" in text or "money" in text else "api")
        elif any(k in text for k in ("api", "endpoint", "route")):
            labels.append("api")
        elif any(k in text for k in ("dark mode", "ui", "button", "theme")):
            labels.append("ui")
        if any(k in text for k in ("crash", "money", "mismatch", "every viewer", "all users")):
            priority = "P1"
        elif "500" in text or "core" in text:
            priority = "P2"
        elif "feature" in labels:
            priority = "P4"
        else:
            priority = "P3"
        call("write_triage_issue", {"issue_id": stub["id"], "labels": labels,
                                    "priority": priority})


def _eng_check_work_issue(engine, family, wo_id, worker_name):
    call = engine.dept_call("engineering", wo_id, worker_name)
    issue_id = _ctx(engine, wo_id).get("issue_id")
    if issue_id is None:
        return [{"criterion": family.criteria[0], "passed": False,
                 "detail": "no issue was worked in this job"}]
    return _eng().check_work_issue(call, issue_id, worker_name)


def _eng_check_triage(engine, family, wo_id, worker_name):
    call = engine.dept_call("engineering", wo_id, worker_name)
    return _eng().check_triage(call)


# ---------------------------------------------------------------------------
# HR (server "hrdesk") — jobs.py EXECUTORS/VERIFIERS take a call_tool client
# ---------------------------------------------------------------------------

_hr_jobs = None


def _hr():
    global _hr_jobs
    if _hr_jobs is None:
        d = str(TARGETS / "hrdesk")
        if d not in sys.path:
            sys.path.insert(0, d)  # jobs.py does `import seed` / `direct_client`
        _hr_jobs = _load("floor_hr_jobs", "hrdesk/jobs.py")
    return _hr_jobs


class _HRClient:
    """Adapts the engine's gated tool path to HR jobs.py's client shape."""

    def __init__(self, engine, wo_id: int, worker_name: str):
        self._engine, self._wo_id, self._worker = engine, wo_id, worker_name

    def call_tool(self, tool_name: str, args: dict | None = None) -> Any:
        return self._engine.call(self._wo_id, tool_name, args or {},
                                 worker_name=self._worker, server="hrdesk")


def _hr_exec(key):
    def execute(engine, family, wo_id, worker):
        client = _HRClient(engine, wo_id, worker["name"])
        _hr().EXECUTORS[key](client, worker=worker["name"])
    return execute


def _hr_check(key):
    def check(engine, family, wo_id, worker_name):
        client = _HRClient(engine, wo_id, worker_name)
        return _hr().VERIFIERS[key](client)
    return check


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def department_families(Family) -> list:
    """Build the engine Family objects for every department workplace."""
    fams: list = []

    qa_jobs = json.loads((TARGETS / "qa" / "jobs.json").read_text())
    for t in qa_jobs["templates"]:
        fams.append(Family(
            t["key"], t["title"], t["brief"], t["budget_credits"],
            t["acceptance_criteria"], department="qa", server="qa",
            execute=_QA_EXEC[t["key"]], check=_qa_check(t["key"])))

    for f in _bk().JOB_FAMILIES:
        fams.append(Family(
            f.key, f.title, f.brief, f.budget, f.criteria,
            department="bookkeeping", server="bookkeeping",
            execute=_bk_exec(f.key), check=_bk_check(f.key)))

    sdr_manifest = json.loads((TARGETS / "sdr" / "department.json").read_text())
    sdr_exec = {"research_score_new_leads": _sdr_exec_score,
                "draft_qualified_outreach": _sdr_exec_draft}
    sdr_check = {"research_score_new_leads": _sdr_check("score_new_batch"),
                 "draft_qualified_outreach": _sdr_check("draft_qualified")}
    for t in sdr_manifest["job_templates"]:
        fams.append(Family(
            t["key"], t["title"], t["brief"], t["budget_credits"],
            t["acceptance_criteria"], department="sdr", server="sdr",
            execute=sdr_exec[t["key"]], check=sdr_check[t["key"]]))

    eng_jobs = json.loads((TARGETS / "engineering" / "jobs.json").read_text())
    eng_by_id = {t["id"]: t for t in eng_jobs["templates"]}
    t = eng_by_id["work_issue"]
    fams.append(Family(
        "work_issue", "Work an engineering issue and open a PR",
        "Claim an unclaimed solvable issue in the Engineering repo, do the "
        "work described by its acceptance criteria, and open a pull-request "
        "record whose change summary addresses every acceptance keyword and "
        "touches every file the issue lists. CI runs when the PR opens — a "
        "red CI means the summary or file set does not satisfy the issue. "
        "You prepare the PR; a human merges it.",
        t["budget_credits"],
        ["The target issue is claimed by the awarded worker",
         "A PR record exists linked to the issue, authored by the worker",
         "The PR's change summary is non-empty",
         "A CI result is recorded for the PR",
         "CI status for the PR is pass (service CI rule)"],
        department="engineering", server="engineering",
        execute=_eng_exec_work_issue, check=_eng_check_work_issue))
    t = eng_by_id["triage_unlabelled"]
    fams.append(Family(
        "triage_unlabelled", t["title_template"], t["brief_template"],
        t["budget_credits"], t["acceptance_criteria"],
        department="engineering", server="engineering",
        execute=_eng_exec_triage, check=_eng_check_triage))
    # answer_changes_requested intentionally not registered — see module
    # docstring (seeded issue #11 is claimed by a non-worker persona).

    for f in _hr().JOB_FAMILIES:
        fams.append(Family(
            f.key, f.title, f.brief, f.budget, f.criteria,
            department="hr", server="hrdesk",
            execute=_hr_exec(f.key), check=_hr_check(f.key)))

    return fams
