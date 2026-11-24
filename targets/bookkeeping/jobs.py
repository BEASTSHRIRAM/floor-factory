"""Bookkeeping jobs pack — templates, credit budgets, and the Reviewer's
deterministic checks.

Mirrors how orchestrator/engine.py defines TicketDesk JOB_FAMILIES:
each family has a key, title, brief, a credit budget, and acceptance
criteria written as machine-checkable statements. The `check_*`
functions below are the deterministic half of the Reviewer for this
department: they re-read live Bookkeeping state through the tool layer
(never the DB) and return findings — one per criterion, pass/fail plus
evidence. The `work_*` functions are deterministic reference workers
used by verify.py to prove each job is completable end-to-end; in the
live factory an LLM worker does the same job through the same tools.

A `call` callable has the orchestrator's shape:
    call(tool_name: str, args: dict) -> dict
"""
from __future__ import annotations

from datetime import date

# Payee -> chart category. The deterministic mapping a competent
# bookkeeper (human or agent) applies to this month's payees.
PAYEE_CATEGORY = {
    "aws": "cloud_hosting",
    "google workspace": "software",
    "figma": "software",
    "notion": "software",
    "zoom": "software",
    "salary: team": "salaries",
    "office rent — mg road": "rent",
    "bescom": "utilities",
    "airtel": "utilities",
    "indigo": "travel",
    "uber": "travel",
    "swiggy": "meals",
    "zomato": "meals",
    "meta ads": "marketing",
    "linkedin": "marketing",
    "amazon": "office_supplies",
    "staples": "office_supplies",
    "hdfc bank": "bank_fees",
}


class Family:
    def __init__(self, key: str, title: str, brief: str, budget: int,
                 criteria: list[str]):
        self.key, self.title, self.brief = key, title, brief
        self.budget, self.criteria = budget, criteria


JOB_FAMILIES: list[Family] = [
    Family(
        "categorise_queue", "Categorise the uncategorised queue",
        "Work the uncategorised queue: assign every transaction older "
        "than 7 days a category from the chart of accounts, using its "
        "payee and memo. Recent transactions (7 days or younger) may be "
        "left for next cycle, but nothing old may remain uncategorised.",
        120,
        ["No uncategorised transaction older than 7 days remains "
         "(GET /transactions/uncategorised ages all <= 7 days)"],
    ),
    Family(
        "flag_duplicates", "Flag the duplicate transactions",
        "Find every set of transactions that are exact duplicates of "
        "each other (same account, date, payee and amount) and flag "
        "each later copy as a duplicate of the earliest (canonical) "
        "one. Flagging marks rows only — nothing is deleted.",
        90,
        ["Flagged duplicate ids exactly match the seeded duplicate set, "
         "and GET /transactions/duplicates returns no open groups"],
    ),
    Family(
        "reconcile_operating", "Reconcile the operating account",
        "Reconcile the Operating Account against its bank statement. "
        "Compute the delta between the recorded balance and the "
        "statement balance, work out what explains it, and record a "
        "reconciliation finance note stating the delta and its cause. "
        "Reconciliation explains differences — it never moves money.",
        110,
        ["Reconciliation delta computed correctly (statement - recorded "
         "= +751) and a reconciliation note recording the delta and its "
         "explanation exists for the account"],
    ),
    Family(
        "chase_receivables", "Chase overdue receivables (+3/+15/+30)",
        "Chase every open invoice that has crossed its chase threshold: "
        "record a reminder for each invoice 3+ days overdue. The system "
        "sets the reminder level from the band (+3 gentle, +15 firm, "
        "+30 final). Invoices not yet due — or less than 3 days overdue "
         "— must NOT be chased. Reminders are recorded drafts; no real "
        "email is sent.",
        130,
        ["Reminders are recorded for exactly the open invoices past "
         "their chase thresholds, each at the correct band level, and "
         "for no others"],
    ),
]

FAMILIES_BY_KEY = {f.key: f for f in JOB_FAMILIES}


def _finding(criterion: str, ok: bool, evidence: str) -> dict:
    return {"criterion": criterion, "pass": ok, "evidence": evidence}


# ---------------------------------------------------------------------------
# Deterministic Reviewer checks (re-read live state through the tools)
# ---------------------------------------------------------------------------

def check_categorise_queue(call) -> list[dict]:
    criterion = FAMILIES_BY_KEY["categorise_queue"].criteria[0]
    out = call("read_list_uncategorised", {})
    old = [t for t in out.get("transactions", []) if t["age_days"] > 7]
    return [_finding(criterion, not old,
                     f"{len(old)} uncategorised transaction(s) older than 7 days "
                     f"remain: {[t['id'] for t in old]}")]


def check_flag_duplicates(call) -> list[dict]:
    criterion = FAMILIES_BY_KEY["flag_duplicates"].criteria[0]
    all_txns = call("read_list_transactions", {}).get("transactions", [])
    # Independently derive the expected duplicate set: within each
    # (account, date, payee, amount) group, every row after the earliest
    # is a duplicate of the earliest.
    groups: dict[tuple, list] = {}
    for t in all_txns:
        key = (t["account_id"], t["date"], t["payee"].strip().lower(), t["amount"])
        groups.setdefault(key, []).append(t)
    expected = {}
    for members in groups.values():
        if len(members) > 1:
            members.sort(key=lambda t: t["id"])
            for dup in members[1:]:
                expected[dup["id"]] = members[0]["id"]
    flagged = {t["id"]: t["duplicate_of"] for t in all_txns
               if t.get("duplicate_of") is not None}
    open_groups = call("read_find_duplicates", {}).get("group_count", -1)
    ok = flagged == expected and open_groups == 0
    return [_finding(criterion, ok,
                     f"expected duplicates {expected}; flagged {flagged}; "
                     f"open duplicate groups {open_groups}")]


def check_reconcile_operating(call) -> list[dict]:
    criterion = FAMILIES_BY_KEY["reconcile_operating"].criteria[0]
    rec = call("read_reconcile_account", {"account_id": 1})
    notes = call("read_list_notes", {}).get("notes", [])
    good_notes = [n for n in notes
                  if n.get("kind") == "reconciliation"
                  and n.get("account_id") == 1
                  and "751" in n.get("text", "")]
    ok = rec.get("delta") == 751 and len(good_notes) >= 1
    return [_finding(criterion, ok,
                     f"recorded {rec.get('recorded_balance')}, statement "
                     f"{rec.get('statement_balance')}, delta {rec.get('delta')}; "
                     f"reconciliation notes stating the delta: {len(good_notes)}")]


def check_chase_receivables(call) -> list[dict]:
    criterion = FAMILIES_BY_KEY["chase_receivables"].criteria[0]
    invoices = call("read_list_receivables", {}).get("invoices", [])
    problems = []
    for inv in invoices:
        reminders = inv.get("reminders", [])
        if inv["status"] == "open" and inv["chase_level_due"] > 0:
            if not reminders:
                problems.append(f"{inv['invoice_no']}: past +{inv['chase_level_due']} "
                                "threshold but no reminder recorded")
            elif reminders[-1]["level"] != inv["chase_level_due"]:
                problems.append(f"{inv['invoice_no']}: latest reminder level "
                                f"{reminders[-1]['level']} != band level "
                                f"{inv['chase_level_due']}")
        elif reminders:
            problems.append(f"{inv['invoice_no']}: reminder recorded but invoice "
                            f"is not past a chase threshold (status "
                            f"{inv['status']}, {inv['days_overdue']}d overdue)")
    return [_finding(criterion, not problems,
                     "; ".join(problems) if problems else
                     "reminders match the chase thresholds exactly")]


CHECKS = {
    "categorise_queue": check_categorise_queue,
    "flag_duplicates": check_flag_duplicates,
    "reconcile_operating": check_reconcile_operating,
    "chase_receivables": check_chase_receivables,
}


# ---------------------------------------------------------------------------
# Deterministic reference workers (used by verify.py; the live factory's
# LLM workers do the same work through the same tools)
# ---------------------------------------------------------------------------

def work_categorise_queue(call) -> list[dict]:
    """Categorise every uncategorised transaction older than 7 days."""
    actions = []
    for t in call("read_list_uncategorised", {}).get("transactions", []):
        if t["age_days"] <= 7:
            continue
        category = PAYEE_CATEGORY[t["payee"].strip().lower()]
        call("write_categorise_transaction",
             {"txn_id": t["id"], "category": category})
        actions.append({"txn_id": t["id"], "category": category})
    return actions


def work_flag_duplicates(call) -> list[dict]:
    actions = []
    for group in call("read_find_duplicates", {}).get("groups", []):
        ids = sorted(group["transaction_ids"])
        for dup_id in ids[1:]:
            call("write_flag_duplicate",
                 {"txn_id": dup_id, "duplicate_of": ids[0]})
            actions.append({"txn_id": dup_id, "duplicate_of": ids[0]})
    return actions


def work_reconcile_operating(call) -> list[dict]:
    rec = call("read_reconcile_account", {"account_id": 1})
    text = (
        f"Reconciled Operating Account as of {date.today().isoformat()}: "
        f"statement balance exceeds the recorded balance by ₹{rec['delta']} "
        f"(recorded ₹{rec['recorded_balance']}, statement "
        f"₹{rec['statement_balance']}). Explained by two unrecorded bank "
        "items: an interest credit of ₹1,250 and a bank fee of ₹499 "
        "(1,250 - 499 = 751). No money moved; items referred to the "
        "accountant for posting."
    )
    note = call("write_add_finance_note",
                {"text": text, "account_id": 1, "kind": "reconciliation"})
    return [{"note_id": note.get("id"), "delta": rec["delta"]}]


def work_chase_receivables(call) -> list[dict]:
    actions = []
    invoices = call("read_list_receivables", {"status": "open"}).get("invoices", [])
    for inv in invoices:
        if inv["chase_level_due"] > 0 and not inv.get("reminders"):
            call("write_send_reminder",
                 {"invoice_id": inv["id"],
                  "note": f"Payment reminder (level {inv['chase_level_due']}) for "
                          f"{inv['invoice_no']} — ₹{inv['amount']} now "
                          f"{inv['days_overdue']} days overdue. Draft recorded "
                          "in the books; no email sent by the agent."})
            actions.append({"invoice_no": inv["invoice_no"],
                            "level": inv["chase_level_due"]})
    return actions


WORKERS = {
    "categorise_queue": work_categorise_queue,
    "flag_duplicates": work_flag_duplicates,
    "reconcile_operating": work_reconcile_operating,
    "chase_receivables": work_chase_receivables,
}
