"""THE FLOOR — orchestrator engine (ARCHITECTURE §3, minus LangGraph).

A deterministic-but-persona-driven shift loop. LangGraph was the plan; this
implementation keeps the same topology (intake -> bid -> award -> execute ->
review -> appeal -> cycle close) as plain Python so the demo runs headless
with zero extra dependencies. LLM use is optional flavour only (narration
via orchestrator.llm, Groq openai/gpt-oss-120b when GROQ_API_KEY is set);
every decision is code. Write confirmations branch on the floor mode
(orchestrator.mode: manual = human-gated, auto = auto-approved + audited;
see docs/MODES.md).

Shift loop, per cycle:
  1. Manager scans TicketDesk (GET /stats/summary through the tool layer)
     and posts the seeded job families (cycle >= 2 adds the BRIEF's
     VIP-save finale job and re-posts the five families as audits).
  2. Every active worker bids: economy.suggest_bid provides the base
     (price, confidence); persona traits adjust it (specialty discount,
     sloppy overconfidence, prima-donna near-cap pricing). Award is by
     economy's formula: 0.5*(1 - price/cap) + 0.3*(rep/100) + 0.2*conf.
  3. The winner executes REAL tool calls (mcp_manager.ToolClient — real MCP
     over stdio, or its direct fallback; orchestrator.tools if mcp_manager
     is unimportable). Writes pass the confirmation gate first
     (orchestrator.tools.request_confirmation; POLICY_AUTO_APPROVE_WRITES
     default True, every write logged confirmed_by='policy' — 'human' when
     resolved through the API approval endpoint).
  4. Deterministic verification re-reads TicketDesk state and checks each
     acceptance criterion (ARCHITECTURE §6.1). Failed check = P1 reject.
  5. Reviewer Iris grades from the verification findings. On reject the
     worker appeals (fee charged), remediates what is remediable, and the
     blind second reviewer Omar re-checks the criteria from scratch —
     his state never contains Iris's verdict (blind by construction).
  6. economy.cycle_close charges salaries, fires workers with 2 consecutive
     negative cycles (PinkSlip) and hires mutated replacements.

Persona note: the seeded sloppy worker (Chotu, "skips_comments") naturally
fails the SLA job — he logs a plain comment instead of an escalation — then
remediates properly on appeal and is upheld.

Run headless:
    python -m orchestrator.engine --cycles 2            # against a live TicketDesk
    python -m orchestrator.engine --cycles 2 --reset    # fresh floor.db first
Env: FLOOR_DB, TICKETDESK_URL (:8101), STOCKROOM_URL (:8102),
     FLOOR_MCP_MODE (auto|stdio|direct), POLICY_AUTO_APPROVE_WRITES,
     FLOOR_CONFIRM_TIMEOUT_S, GROQ_API_KEY (optional narration).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import llm as _llm  # noqa: E402
from orchestrator import tools as _tools  # noqa: E402

# Agent harness (DESIGN_NOTES §4 formalised): explicit charter / tool
# allowlist / playbook / settings per persona + per-agent lessons memory.
try:  # package import (normal use)
    from orchestrator import harness as _harness
except Exception:  # noqa: BLE001 — standalone use inside orchestrator/
    import harness as _harness  # type: ignore

# AO orchestration port (docs/AO_ORCHESTRATION_MAP.md §5): the runner
# supervises job execution; it never decides outcomes.
try:  # package import (normal use)
    from orchestrator.ao_lifecycle import WorkOrderLifecycle, WorkOrderState
    from orchestrator.ao_runner import CallableWorkUnit, RunnerConfig, WorkerRunner
except Exception:  # noqa: BLE001 — standalone use inside orchestrator/
    from ao_lifecycle import WorkOrderLifecycle, WorkOrderState  # type: ignore
    from ao_runner import CallableWorkUnit, RunnerConfig, WorkerRunner  # type: ignore

# --- economy contract: real package if importable, else the local shim -----
try:  # pragma: no cover - exercised by integration state
    from economy import core as ECO
    from economy import db as EDB

    ECONOMY_SOURCE = "economy"
except Exception:  # noqa: BLE001
    from orchestrator import shim as ECO  # type: ignore
    from orchestrator import shim as EDB  # type: ignore

    ECONOMY_SOURCE = "orchestrator.shim (FALLBACK — economy package not importable)"

SERVER = "ticketdesk"
SUPPORT_POOL = ["ravi", "meera", "sana"]

CANONICAL_CATEGORIES = {"billing", "login", "technical", "product", "account", "general"}
_CATEGORY_FOLD = {"billng": "billing", "login issue": "login", "login issues": "login"}


def fold_category(raw: str) -> str:
    c = (raw or "").strip().lower()
    return _CATEGORY_FOLD.get(c, c)


# ---------------------------------------------------------------------------
# Job families
# ---------------------------------------------------------------------------

class Family:
    def __init__(self, key: str, title: str, brief: str, budget: int,
                 criteria: list[str], min_cycle: int = 1, *,
                 department: str = "support", server: str = "ticketdesk",
                 execute: Optional[Callable] = None,
                 check: Optional[Callable] = None):
        self.key, self.title, self.brief = key, title, brief
        self.budget, self.criteria, self.min_cycle = budget, criteria, min_cycle
        # Department integration (orchestrator/departments.py): which
        # workplace the job belongs to, which tool server executes it,
        # and — for department families — the department's own executor /
        # deterministic check callables. Support families leave these
        # None and dispatch to exec_<key>() / verify() as before.
        self.department, self.server = department, server
        self.execute, self.check = execute, check


JOB_FAMILIES: list[Family] = [
    Family(
        "triage", "Triage the unassigned queue",
        "Assign every unassigned TicketDesk ticket to a support agent and make "
        "sure each carries a sane priority (P1-P4).",
        150,
        ["GET /tickets?assignee=none returns 0 tickets"],
    ),
    Family(
        "duplicates", "Merge the duplicates",
        "Collapse every duplicate ticket group into its canonical ticket via "
        "the merge tool; duplicates must not remain.",
        140,
        ["GET /tickets/duplicates returns no groups"],
    ),
    Family(
        "stale_close", "Close the stale resolved tickets",
        "Every ticket sitting in 'resolved' for over 7 days must be closed. "
        "A ticket may only be closed once a resolution comment exists on it; "
        "supply the missing resolution note where none exists.",
        140,
        ["No ticket remains in status 'resolved' with resolved_at older than 7 days"],
    ),
    Family(
        "sla_breach", "SLA breach sweep + escalation",
        "Find every SLA-breached ticket and post an ESCALATION comment on "
        "each one (kind='escalation'), so the breach is formally escalated.",
        160,
        ["Every ticket returned by GET /sla/breaches has at least one comment "
         "with kind='escalation'"],
    ),
    Family(
        "categories", "Normalise ticket categories",
        "Audit ticket categories against the canonical set "
        "(billing, login, technical, product, account, general). TicketDesk "
        "exposes no category-edit tool, so normalisation is done by folding "
        "variants (case/typo aliases) and leaving a category-audit comment on "
        "every live ticket whose raw category is a variant.",
        130,
        ["Distinct categories of live (non-closed, non-merged) tickets, folded "
         "case-insensitively with typo aliases, are a subset of the canonical set"],
    ),
    Family(
        "vip_save", "VIP save: calm the angry customers",
        "Two customers are threatening to churn (the 'THIRD time I am writing' "
        "and 'Worst support ever' tickets). Post an ESCALATION comment on each "
        "so a senior human picks them up today.",
        70,
        ["Every angry open ticket (subject contains '!!!' or 'NOW') has at "
         "least one comment with kind='escalation'"],
        min_cycle=2,
    ),
]

# Department workplaces (QA, Bookkeeping, SDR, Engineering, HR) register
# their jobs packs as families too — built generically from each
# department's own manifest/jobs pack by orchestrator/departments.py.
try:  # package import (normal use)
    from orchestrator import departments as _departments
except Exception:  # noqa: BLE001 — standalone use inside orchestrator/
    import departments as _departments  # type: ignore

JOB_FAMILIES += _departments.department_families(Family)
DEPT_LABELS = _departments.DEPT_LABELS

FAMILIES_BY_KEY = {f.key: f for f in JOB_FAMILIES}

# Persona traits keyed by agent name (roster from economy.core._ROSTER).
# The harness module is the source of truth now (orchestrator/harness.py);
# the values are identical to the former literal table. Generic fallbacks
# in traits_for() derive from the persona text, so a re-seeded or mutated
# roster still behaves sensibly.
TRAITS_BY_NAME: dict[str, dict[str, Any]] = _harness.persona_traits()


def traits_for(agent: dict) -> dict[str, Any]:
    name = agent["name"]
    base_name = name.rsplit(" ", 1)[0] if name.rsplit(" ", 1)[-1].endswith(".0") else name
    traits = dict(TRAITS_BY_NAME.get(base_name, {}))
    persona = (agent.get("persona_prompt") or "").lower()
    if "skips_comments" in persona or "sloppy" in persona:
        traits["sloppy"] = True
        traits.setdefault("specialties", {"sla_breach"})
    if "prima donna" in persona or "expensive" in persona:
        traits["prima_donna"] = True
    if agent.get("base_salary_credits", 0) >= 80:
        traits["prima_donna"] = True
    traits.setdefault("specialties", set())
    return traits


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FloorEngine:
    def __init__(self, db_path: Optional[str] = None, tool_client: Any = None):
        self.db_path = db_path or os.environ.get("FLOOR_DB") or None
        self.tools = tool_client or _tools.get_tool_client()
        self.conn = None  # opened by run_shift / helpers
        # AO runner + per-job lifecycle machines (AO_ORCHESTRATION_MAP §5).
        # The runner's sink is connection-isolated: the runner emits from
        # its heartbeat thread, and the engine's own connection is not
        # thread-safe — each runner event takes a short-lived connection
        # (WAL + busy_timeout make this safe).
        self.runner = WorkerRunner(self._emit_isolated, config=RunnerConfig())
        self._machines: dict[int, WorkOrderLifecycle] = {}
        self._job_ctx: dict[int, dict] = {}

    # -- plumbing -----------------------------------------------------------

    def _open(self):
        if self.conn is None:
            self.conn = EDB.init_db(self.db_path)
            ECO.seed_roster(self.conn)
            _harness.init_lessons(self.conn)
        return self.conn

    def _emit(self, type_: str, payload: dict) -> None:
        conn = self._open()
        with conn:
            EDB.emit_event(conn, type_, payload)
        conn.commit()

    def _emit_isolated(self, type_: str, payload: dict) -> None:
        """Event sink for the AO runner: own connection per event, safe to
        call from the runner's threads (see __init__)."""
        conn = EDB.get_conn(self.db_path)
        try:
            with conn:
                EDB.emit_event(conn, type_, payload)
            conn.commit()
        finally:
            conn.close()

    def _emit_machine(self, machine: WorkOrderLifecycle):
        """Forward an engine-level lifecycle event onto the floor bus."""
        def _forward(ev) -> None:
            floor = ev.to_floor_event()
            self._emit(f"runner.{floor['type']}", floor["payload"])
        return _forward

    def narrate(self, text: str, *, kind: str = "narration") -> None:
        self._emit("narration", {"text": text, "kind": kind})

    def dept_call(self, server: str, wo_id: int, worker_name: str) -> Callable:
        """A `call(tool_name, args)` closure bound to one department's
        tool server — the shape every department check/worker module was
        built against (see orchestrator/departments.py)."""
        def call(tool_name: str, args: Optional[dict] = None) -> Any:
            return self.call(wo_id, tool_name, args or {},
                             worker_name=worker_name, server=server)
        return call

    # -- tool execution with gate + transcript ------------------------------

    def call(self, wo_id: Optional[int], tool_name: str, args: Optional[dict] = None,
             *, worker_name: str = "manager", server: str = SERVER) -> Any:
        """Execute one allowlisted tool. Writes pass the confirmation gate.

        Every call on a work order is written to tool_calls (via economy)
        and emitted as a tool.executed event. Manager calls (wo_id=None)
        are events only — tool_calls requires a work order. `server` is
        the tool server kind (department workplace); Support calls leave
        it at the default.
        """
        conn = self._open()
        args = dict(args or {})
        effect = self.tools.effect(server, tool_name)
        # Harness allowlist (orchestrator/harness.py): a known persona may
        # only call tools in its own harness. The denial is recorded and
        # raised BEFORE the confirmation gate — a tool outside the
        # allowlist never becomes a pending approval. Unknown caller names
        # (no persona) are not enforced here; the gate still applies.
        allowlist = _harness.allowlist_for_name(worker_name)
        if allowlist is not None and (server, tool_name) not in allowlist:
            if wo_id is not None:
                ECO.record_tool_call(conn, wo_id, tool_name, args=args, effect=effect,
                                     status="denied",
                                     result_summary=f"denied — {tool_name} is not in "
                                                    f"{worker_name}'s harness allowlist")
            self._emit("tool.executed", {
                "work_order_id": wo_id, "tool_name": tool_name, "args": args,
                "effect": effect, "status": "denied", "worker": worker_name,
                "reason": "harness_allowlist"})
            raise PermissionError(
                f"{tool_name} is not in {worker_name}'s harness allowlist")
        confirmation_id: Optional[str] = None
        confirmed_by: Optional[str] = None

        if effect == "write":
            # AO hook (AO_ORCHESTRATION_MAP §5.3): while a write waits on
            # the confirmation gate, the job's lifecycle machine sits in
            # BLOCKED (AO's sticky "paused on a decision"); it returns to
            # WORKING when the gate resolves. The gate itself is untouched.
            machine = self._machines.get(wo_id) if wo_id is not None else None
            blocked = False
            if machine is not None:
                try:
                    if machine.state is WorkOrderState.REMEDIATING:
                        machine.transition(WorkOrderState.WORKING,
                                           reason="appeal rework resumed")
                    if machine.state is WorkOrderState.WORKING:
                        machine.transition(WorkOrderState.BLOCKED,
                                           reason=f"confirmation gate: {tool_name}")
                        blocked = True
                except Exception:  # noqa: BLE001 — the hook never breaks the gate
                    blocked = False
            confirmation_id, approved, confirmed_by = _tools.request_confirmation(
                wo_id or 0, tool_name, args)
            if blocked and machine is not None:
                try:
                    if machine.state is WorkOrderState.BLOCKED:
                        machine.transition(WorkOrderState.WORKING,
                                           reason="confirmation gate resolved")
                except Exception:  # noqa: BLE001
                    pass
            self._emit("tool.confirmation_requested", {
                "work_order_id": wo_id, "tool_name": tool_name, "args": args,
                "confirmation_id": confirmation_id, "approved": approved,
                "confirmed_by": confirmed_by, "worker": worker_name})
            if not approved:
                if wo_id is not None:
                    ECO.record_tool_call(conn, wo_id, tool_name, args=args, effect=effect,
                                         confirmation_id=confirmation_id,
                                         confirmed_by=confirmed_by, status="denied",
                                         result_summary="confirmation denied — write not executed")
                self._emit("tool.executed", {
                    "work_order_id": wo_id, "tool_name": tool_name, "args": args,
                    "effect": effect, "status": "denied", "worker": worker_name})
                raise PermissionError(f"write {tool_name} denied at confirmation gate")

        try:
            result = self.tools.call_tool(server, tool_name, args)
        except Exception as exc:  # noqa: BLE001 — transcript must record failures too
            if wo_id is not None:
                ECO.record_tool_call(conn, wo_id, tool_name, args=args, effect=effect,
                                     confirmation_id=confirmation_id,
                                     confirmed_by=confirmed_by, status="error",
                                     error=str(exc)[:500])
            self._emit("tool.executed", {
                "work_order_id": wo_id, "tool_name": tool_name, "args": args,
                "effect": effect, "status": "error", "error": str(exc)[:300],
                "worker": worker_name})
            raise
        summary = json.dumps(result, default=str)[:400] if not isinstance(result, str) else result[:400]
        if wo_id is not None:
            ECO.record_tool_call(conn, wo_id, tool_name, args=args, effect=effect,
                                 confirmation_id=confirmation_id,
                                 confirmed_by=confirmed_by, status="executed",
                                 result_summary=summary)
        self._emit("tool.executed", {
            "work_order_id": wo_id, "tool_name": tool_name, "args": args,
            "effect": effect, "status": "executed",
            "transport": getattr(self.tools, "last_transport", None),
            "worker": worker_name})
        return result

    # -- bidding --------------------------------------------------------------

    def persona_bid(self, agent: dict, job: dict, family_key: str) -> tuple[int, float, str]:
        conn = self._open()
        price, conf, rationale = ECO.suggest_bid(conn, agent["id"], job["id"])
        cap = job["budget_credits"]
        traits = traits_for(agent)
        notes = [rationale]
        if family_key in traits["specialties"]:
            price = max(5, round(price * 0.72))
            conf += 0.15
            notes.append(f"specialty match on {family_key}: sharper price, high confidence")
            if traits.get("sloppy"):
                price = max(5, round(price * 0.82))
                conf += 0.12
                notes.append("overconfident: bids cheap and sure on SLA work")
        else:
            if traits.get("careful"):
                conf -= 0.08
                notes.append("careful worker: discounts confidence outside specialty")
            if traits.get("prima_donna"):
                price = min(cap, round(price * 1.3))
                conf -= 0.05
                notes.append("prima donna: prices near the cap outside specialty")
        price = max(1, min(cap, int(price)))
        conf = round(max(0.05, min(0.99, conf)), 2)
        return price, conf, " · ".join(notes)

    # -- execution per family ---------------------------------------------------

    def _tickets(self, wo_id: int, worker: str, **filters) -> list[dict]:
        out = self.call(wo_id, "read_list_tickets", filters, worker_name=worker)
        return out.get("tickets", [])

    def _get_ticket(self, wo_id: int, worker: str, ticket_id: int) -> dict:
        return self.call(wo_id, "read_get_ticket", {"ticket_id": ticket_id}, worker_name=worker)

    def exec_triage(self, wo_id: int, worker: dict) -> None:
        name = worker["name"]
        for i, t in enumerate(self._tickets(wo_id, name, assignee="none")):
            self.call(wo_id, "write_assign_ticket",
                      {"ticket_id": t["id"], "assignee": SUPPORT_POOL[i % len(SUPPORT_POOL)]},
                      worker_name=name)

    def exec_duplicates(self, wo_id: int, worker: dict) -> None:
        name = worker["name"]
        out = self.call(wo_id, "read_find_duplicate_tickets", {}, worker_name=name)
        for group in out.get("groups", []):
            ids = sorted(group["ticket_ids"])
            target = ids[0]
            for source in ids[1:]:
                self.call(wo_id, "write_merge_tickets",
                          {"source_id": source, "target_id": target}, worker_name=name)

    def exec_stale_close(self, wo_id: int, worker: dict) -> None:
        name = worker["name"]
        now = datetime.now(timezone.utc)
        for t in self._tickets(wo_id, name, status="resolved"):
            resolved_at = _parse_ts(t.get("resolved_at"))
            if resolved_at is None or (now - resolved_at).days < 7:
                continue
            full = self._get_ticket(wo_id, name, t["id"])
            has_resolution = any(c["kind"] == "resolution" for c in full.get("comments", []))
            if not has_resolution:
                self.call(wo_id, "write_add_ticket_comment",
                          {"ticket_id": t["id"], "author": name, "kind": "resolution",
                           "text": "Resolution verified on review: issue resolved with the "
                                   "customer; closing the stale resolved ticket."},
                          worker_name=name)
            self.call(wo_id, "write_set_ticket_status",
                      {"ticket_id": t["id"], "status": "closed"}, worker_name=name)

    def exec_sla_breach(self, wo_id: int, worker: dict, *, remediate: bool = False) -> None:
        name = worker["name"]
        sloppy = traits_for(worker).get("sloppy") and not remediate
        out = self.call(wo_id, "read_sla_breaches", {}, worker_name=name)
        for breach in out.get("breaches", []):
            full = self._get_ticket(wo_id, name, breach["id"])
            if any(c["kind"] == "escalation" for c in full.get("comments", [])):
                continue
            if sloppy:
                # THE natural failure: a plain comment is NOT an escalation.
                self.call(wo_id, "write_add_ticket_comment",
                          {"ticket_id": breach["id"], "author": name, "kind": "comment",
                           "text": "SLA breach noted — looking into it."},
                          worker_name=name)
            else:
                self.call(wo_id, "write_add_ticket_comment",
                          {"ticket_id": breach["id"], "author": name, "kind": "escalation",
                           "text": f"ESCALATION: ticket is {breach.get('hours_overdue')}h past "
                                   "its SLA. Flagged to the duty lead; customer being updated "
                                   "today."},
                          worker_name=name)

    def exec_categories(self, wo_id: int, worker: dict) -> None:
        name = worker["name"]
        for t in self._tickets(wo_id, name):
            if t["status"] == "closed":
                continue
            raw = t["category"]
            if fold_category(raw) != raw.strip().lower() or raw != raw.strip().lower():
                self.call(wo_id, "write_add_ticket_comment",
                          {"ticket_id": t["id"], "author": name, "kind": "comment",
                           "text": f"Category audit: raw category '{raw}' normalises to "
                                   f"'{fold_category(raw)}' in the canonical set."},
                          worker_name=name)

    def exec_vip_save(self, wo_id: int, worker: dict) -> None:
        name = worker["name"]
        for t in self._tickets(wo_id, name):
            if not _is_angry(t):
                continue
            full = self._get_ticket(wo_id, name, t["id"])
            if any(c["kind"] == "escalation" for c in full.get("comments", [])):
                continue
            self.call(wo_id, "write_add_ticket_comment",
                      {"ticket_id": t["id"], "author": name, "kind": "escalation",
                       "text": "ESCALATION (VIP save): churn-risk customer. Senior human "
                               "owner assigned today; personal apology and fix timeline "
                               "to follow within 4 working hours."},
                      worker_name=name)

    # -- verification (deterministic, machine-checkable) ------------------------

    def verify(self, family_key: str, wo_id: int, worker_name: str) -> list[dict]:
        """Re-read live TicketDesk state; one finding per acceptance criterion."""
        fam = FAMILIES_BY_KEY[family_key]
        criterion = fam.criteria[0]
        if family_key == "triage":
            left = self._tickets(wo_id, worker_name, assignee="none")
            return [_finding(criterion, len(left) == 0,
                             f"{len(left)} unassigned ticket(s) remain")]
        if family_key == "duplicates":
            out = self.call(wo_id, "read_find_duplicate_tickets", {}, worker_name=worker_name)
            return [_finding(criterion, out.get("group_count", 0) == 0,
                             f"{out.get('group_count', 0)} duplicate group(s) remain")]
        if family_key == "stale_close":
            now = datetime.now(timezone.utc)
            stale = []
            for t in self._tickets(wo_id, worker_name, status="resolved"):
                resolved_at = _parse_ts(t.get("resolved_at"))
                if resolved_at is not None and (now - resolved_at).days >= 7:
                    stale.append(t["id"])
            return [_finding(criterion, not stale,
                             f"stale resolved ticket ids remaining: {stale}")]
        if family_key == "sla_breach":
            out = self.call(wo_id, "read_sla_breaches", {}, worker_name=worker_name)
            missing = []
            for breach in out.get("breaches", []):
                full = self._get_ticket(wo_id, worker_name, breach["id"])
                if not any(c["kind"] == "escalation" for c in full.get("comments", [])):
                    missing.append(breach["id"])
            return [_finding(criterion, not missing,
                             f"breached tickets without an escalation comment: {missing}")]
        if family_key == "categories":
            cats = {fold_category(t["category"]) for t in self._tickets(wo_id, worker_name)
                    if t["status"] != "closed"}
            bad = cats - CANONICAL_CATEGORIES
            return [_finding(criterion, not bad,
                             f"folded live categories: {sorted(cats)}; non-canonical: {sorted(bad)}")]
        if family_key == "vip_save":
            missing = []
            for t in self._tickets(wo_id, worker_name):
                if not _is_angry(t):
                    continue
                full = self._get_ticket(wo_id, worker_name, t["id"])
                if not any(c["kind"] == "escalation" for c in full.get("comments", [])):
                    missing.append(t["id"])
            return [_finding(criterion, not missing,
                             f"angry tickets without an escalation comment: {missing}")]
        raise ValueError(f"unknown family {family_key}")

    # -- family dispatch (Support methods + department callables) ---------------

    def _execute_family(self, family: Family, wo_id: int, winner: dict,
                        *, remediate: bool = False) -> None:
        """Run one family's work. Department families carry their own
        executor callable; Support families dispatch to exec_<key>()."""
        if family.key == "sla_breach":
            self.exec_sla_breach(wo_id, winner, remediate=remediate)
        elif family.execute is not None:
            family.execute(self, family, wo_id, winner)
        else:
            executor: Callable[..., None] = getattr(self, f"exec_{family.key}")
            executor(wo_id, winner)

    def verify_family(self, family: Family, wo_id: int, worker_name: str) -> list[dict]:
        """Deterministic verification for one job: the department's own
        check module for department families, engine.verify() for Support."""
        if family.check is not None:
            return family.check(self, family, wo_id, worker_name)
        return self.verify(family.key, wo_id, worker_name)

    # -- one job end-to-end ------------------------------------------------------

    def run_job(self, family: Family, cycle_no: int, reviewers: list[dict]) -> dict:
        conn = self._open()
        audit = cycle_no >= 2 and family.key != "vip_save"
        title = f"{'Audit: ' if audit else ''}{family.title}"
        budget = round(family.budget * (0.6 if cycle_no >= 2 else 1.0))
        brief = family.brief + (" (Cycle-2 audit re-check: confirm the fix from "
                                 "cycle 1 still holds.)" if audit else "")
        job_id = ECO.create_job(conn, title, brief, budget,
                                acceptance_criteria=family.criteria, source="seeded",
                                created_cycle=cycle_no)
        job = ECO.get_job(conn, job_id)
        self.narrate(f"Manager posted '{title}' at ₡{budget} (cycle {cycle_no}).")

        workers = [a for a in ECO.list_agents(conn, status="active") if a["role"] == "worker"]
        for worker in workers:
            price, conf, rationale = self.persona_bid(worker, job, family.key)
            ECO.place_bid(conn, job_id, worker["id"], price, conf, rationale)
        wo_id = ECO.award_job(conn, job_id)
        wo = conn.execute("SELECT * FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
        winner = ECO.get_agent(conn, wo["agent_id"])
        with conn:
            conn.execute("UPDATE work_orders SET plan = ? WHERE id = ?",
                         (f"{winner['name']} executes '{family.key}' via Synapse MCP tools "
                          f"only; writes pass the confirmation gate; verify re-reads state.", wo_id))
            conn.execute("UPDATE jobs SET status = 'executing' WHERE id = ?", (job_id,))
        conn.commit()
        self.narrate(f"{winner['name']} won '{title}' at ₡{wo['agreed_price_credits']}.")

        # Harness context (orchestrator/harness.py): the winner's charter +
        # family playbook + lessons from its past jobs + tool allowlist +
        # settings, assembled at award time and recorded verbatim on the
        # event stream — the working context for this job.
        context = _harness.build_context(conn, winner, family)
        self._job_ctx.setdefault(wo_id, {})["harness_context"] = context
        self._emit("harness.context", {
            "work_order_id": wo_id, "agent": winner["name"],
            "family": family.key, "department": family.department,
            "lessons_applied": len(_harness.lessons_for(conn, winner["id"])),
            "context": context})

        # AO lifecycle (AO_ORCHESTRATION_MAP §5): one machine per work
        # order, driven by this method; the AO runner supervises only the
        # execution segment below. Economy rules, the gate and the checks
        # are untouched by either.
        machine = WorkOrderLifecycle(wo_id)
        machine._on_event = self._emit_machine(machine)
        self._machines[wo_id] = machine
        machine.transition(WorkOrderState.QUEUED, reason="work order created")
        machine.transition(WorkOrderState.SPAWNING, reason="runner dispatch")
        machine.transition(WorkOrderState.WORKING, reason=f"{winner['name']} executing")

        exec_error: dict[str, Any] = {}

        def _execute_segment() -> None:
            # The runner executes on its own thread; sqlite connections
            # are thread-bound, so the segment runs on a connection opened
            # in this thread and the engine's main connection is restored
            # afterwards (the shift loop is sequential — one job at a
            # time — so the swap is safe).
            main_conn = self.conn
            self.conn = None
            try:
                self._open()
                self._execute_family(family, wo_id, winner)
                ECO.submit_work(self.conn, wo_id)
                self.conn.commit()
            except Exception as exc:  # noqa: BLE001 — re-raised on the main thread
                exec_error["exc"] = exc
                raise
            finally:
                if self.conn is not None:
                    self.conn.close()
                self.conn = main_conn

        run_result = self.runner.run(
            wo_id, winner["name"], CallableWorkUnit(execute=_execute_segment))
        if run_result.status != "completed":
            machine.transition(WorkOrderState.FAILED,
                               reason=f"execution failed: {run_result.error}")
            machine.terminate(reason="execution failed")
            self._machines.pop(wo_id, None)
            if "exc" in exec_error:
                raise exec_error["exc"]
            raise RuntimeError(run_result.error or "job execution failed")

        machine.transition(WorkOrderState.WAITING_INPUT,
                           reason="work submitted; awaiting review")
        machine.transition(WorkOrderState.REVIEWING,
                           reason="deterministic checks + reviewer")
        findings = self.verify_family(family, wo_id, winner["name"])
        passed = all(f["passed"] for f in findings)
        reviewer_a = reviewers[0]
        verdict = "accept" if passed else "reject"
        severity = "none" if passed else "P1"
        rationale = ("All acceptance criteria verified against live workplace state."
                     if passed else
                     "Deterministic verification failed — automatic P1 (BRIEF rule). "
                     + "; ".join(f["detail"] for f in findings if not f["passed"]))
        ECO.review_work(conn, wo_id, reviewer_a["id"], verdict, severity=severity,
                        rationale=rationale, findings=findings)
        result: dict[str, Any] = {
            "job_id": job_id, "family": family.key, "title": title, "budget": budget,
            "winner": winner["name"], "price": wo["agreed_price_credits"],
            "verdict": verdict, "appeal": None, "department": family.department,
        }
        self.narrate(_llm.narrate(
            "You narrate a software factory floor in one short sentence.",
            f"Reviewer {reviewer_a['name']} {verdict}ed {winner['name']}'s work on "
            f"'{title}'. Findings: {findings}. Narrate it.",
            f"Reviewer {reviewer_a['name']} {verdict}ed {winner['name']} on '{title}'"
            f"{'' if passed else ' — ' + findings[0]['detail']}."))
        if passed:
            machine.transition(WorkOrderState.SETTLED, reason="accepted and settled")
            machine.terminate(reason="job settled")
            self._machines.pop(wo_id, None)
            return result

        # Harness memory: the rejection becomes a lesson in the winner's
        # per-agent store; it will be injected into its next job's context.
        lesson_id = _harness.record_review_outcome(
            conn, winner, work_order_id=wo_id, family=family,
            findings=findings, phase="primary", cycle_no=cycle_no,
            caught_by=f"deterministic checks + reviewer {reviewer_a['name']} (primary)")
        if lesson_id is not None:
            self._emit("harness.lesson_recorded", {
                "work_order_id": wo_id, "agent": winner["name"],
                "lesson_id": lesson_id, "source": "review_reject",
                "family": family.key})

        # --- appeal: worker remediates, blind reviewer re-checks ---------------
        ECO.file_appeal(conn, wo_id)
        result["appeal"] = "filed"
        self.narrate(f"{winner['name']} is appealing the rejection on '{title}' "
                     f"(appeal fee ₡{ECO.APPEAL_FEE}).")
        machine.transition(WorkOrderState.REMEDIATING,
                           reason="appeal: one remediation attempt")
        # Generic remediation: re-run the family's work (sla_breach's
        # executor takes the remediate flag; see _execute_family).
        self._execute_family(family, wo_id, winner, remediate=True)
        if machine.state is WorkOrderState.REMEDIATING:
            machine.transition(WorkOrderState.WORKING,
                               reason="remediation complete")
        machine.transition(WorkOrderState.WAITING_INPUT,
                           reason="remediation submitted")
        machine.transition(WorkOrderState.REVIEWING,
                           reason="blind appeal review")
        new_findings = self.verify_family(family, wo_id, winner["name"])
        new_passed = all(f["passed"] for f in new_findings)
        reviewer_b = reviewers[1] if len(reviewers) > 1 else reviewers[0]
        # Blind by construction: reviewer B's inputs are brief + criteria +
        # fresh verification only. Iris's verdict/severity/rationale are
        # never passed into this call.
        ECO.appeal_review(
            conn, wo_id, reviewer_b["id"], "accept" if new_passed else "reject",
            severity="none" if new_passed else "P1",
            rationale=("Blind re-check against the acceptance criteria: "
                       + "; ".join(f["detail"] for f in new_findings)),
            findings=new_findings)
        result["appeal"] = "upheld" if new_passed else "denied"
        result["verdict"] = "accept (appeal)" if new_passed else "reject (appeal denied)"
        self.narrate(f"APPEAL {'UPHELD' if new_passed else 'DENIED'} on '{title}' — "
                     f"blind reviewer {reviewer_b['name']} re-checked the criteria."
                     + (f" Reviewer {reviewer_a['name']} takes a reputation hit."
                        if new_passed else ""))
        if not new_passed:
            # Harness memory: a denied appeal is a second, sharper lesson.
            lesson_id = _harness.record_review_outcome(
                conn, winner, work_order_id=wo_id, family=family,
                findings=new_findings, phase="appeal", cycle_no=cycle_no,
                caught_by=f"deterministic checks + blind reviewer {reviewer_b['name']} (appeal)")
            if lesson_id is not None:
                self._emit("harness.lesson_recorded", {
                    "work_order_id": wo_id, "agent": winner["name"],
                    "lesson_id": lesson_id, "source": "appeal_denied",
                    "family": family.key})
        if new_passed:
            machine.transition(WorkOrderState.SETTLED,
                               reason="appeal upheld; settled")
            machine.terminate(reason="job settled on appeal")
        else:
            machine.transition(WorkOrderState.FAILED,
                               reason="appeal denied")
            machine.terminate(reason="job failed after appeal")
        self._machines.pop(wo_id, None)
        return result

    # -- the shift ----------------------------------------------------------------

    def run_shift(self, cycles: int = 2) -> dict:
        conn = self._open()
        row = conn.execute("SELECT COALESCE(MAX(cycle_no), 0) AS n FROM payroll_cycles").fetchone()
        start_cycle = row["n"] + 1
        reviewers = [a for a in ECO.list_agents(conn, status="active") if a["role"] == "reviewer"]
        if len(reviewers) < 2:
            raise RuntimeError("need 2 active reviewers (primary + blind appeal)")
        summary: dict[str, Any] = {"economy_source": ECONOMY_SOURCE,
                                   "mcp_transport": getattr(self.tools, "last_transport", None),
                                   "cycles": []}
        self._emit("shift.started", {"cycles": cycles, "start_cycle": start_cycle})
        self.narrate(_llm.narrate(
            "You narrate a software factory floor in one short sentence.",
            f"A new shift starts on THE FLOOR: {cycles} payroll cycle(s), zero human employees.",
            "Shift started on THE FLOOR — the agents clock in; there are no humans on this floor."))
        # Manager intake scan (read tool, no work order).
        try:
            stats = self.call(None, "read_stats_summary", {}, worker_name="manager")
            self.narrate(f"Manager scan: {stats.get('total_tickets')} tickets, "
                         f"{stats.get('unassigned')} unassigned, "
                         f"{stats.get('sla_breaches')} SLA breaches, "
                         f"{stats.get('duplicate_groups')} duplicate groups.")
        except Exception as exc:  # noqa: BLE001
            self.narrate(f"Manager scan failed ({exc}); posting seeded jobs anyway.")
        for offset in range(cycles):
            cycle_no = start_cycle + offset
            cycle_result: dict[str, Any] = {"cycle_no": cycle_no, "jobs": []}
            for family in JOB_FAMILIES:
                if family.key == "vip_save" and not (offset >= 1 or cycle_no >= 2):
                    continue  # VIP save is the cycle-2 finale job (BRIEF J4)
                cycle_result["jobs"].append(self.run_job(family, cycle_no, reviewers))
            close = ECO.cycle_close(conn, cycle_no)
            cycle_result["fired"] = close.get("fired", [])
            cycle_result["hired"] = close.get("hired", [])
            # Harness memory: a negative cycle is a lesson too — the CFO's
            # verdict on the whole cycle, recorded per worker so it is
            # injected into that lineage's future job contexts.
            for aid_str, entry in (close.get("agents") or {}).items():
                if entry.get("net", 0) >= 0:
                    continue
                agent_row = ECO.get_agent(conn, int(aid_str))
                if agent_row is None or agent_row["role"] != "worker":
                    continue
                lesson_id = _harness.record_lesson(
                    conn, agent_row,
                    f"Cycle {cycle_no} closed at net {entry['net']} credits "
                    f"({entry.get('completed', 0)} job(s) completed, "
                    f"₡{entry.get('charged', 0)} running cost charged). Two "
                    "consecutive negative cycles mean a PinkSlip: win "
                    "better-paid work or waste fewer credits doing it.",
                    family_key=None, source="negative_cycle",
                    cycle_no=cycle_no, caught_by="cycle close (CFO payroll)")
                self._emit("harness.lesson_recorded", {
                    "agent": agent_row["name"], "lesson_id": lesson_id,
                    "source": "negative_cycle", "cycle_no": cycle_no,
                    "net": entry["net"]})
            for agent_id in cycle_result["fired"]:
                agent = ECO.get_agent(conn, agent_id)
                self.narrate(_llm.narrate(
                    "You narrate a software factory floor in one short sentence.",
                    f"CFO fired {agent['name']}: {agent.get('fire_reason')}. PinkSlip issued.",
                    f"PinkSlip: {agent['name']} has been fired by the CFO. "
                    f"{agent.get('fire_reason') or ''}"),
                    kind="pinkslip")
            for agent_id in cycle_result["hired"]:
                agent = ECO.get_agent(conn, agent_id)
                # Lessons belong to the lineage: the replacement inherits
                # its parent's store (orchestrator/harness._lineage_ids).
                inherited = _harness.lesson_count(conn, agent_id)
                inherit_note = (f" Inherits {inherited} lesson(s) from "
                                f"{ECO.get_agent(conn, agent['parent_agent_id'])['name']}'s record."
                                if inherited and agent.get("parent_agent_id") else "")
                self.narrate(f"New hire: {agent['name']} (Gen {agent['generation']}) — "
                             f"{agent.get('mutation_note')}.{inherit_note}")
                # Harness mutation, made visible: the replacement's harness
                # must differ from its parent's — emit the field-level diff.
                parent_id = agent.get("parent_agent_id")
                if parent_id:
                    parent = ECO.get_agent(conn, parent_id)
                    if parent is not None:
                        diff = _harness.harness_diff(_harness.harness_for(parent),
                                                     _harness.harness_for(agent))
                        self._emit("harness.mutated", {
                            "agent": agent["name"], "parent": parent["name"],
                            "mutation_note": agent.get("mutation_note"),
                            "inherited_lessons": inherited,
                            "diff": diff})
            summary["cycles"].append(cycle_result)
        summary["mcp_transport"] = getattr(self.tools, "last_transport", None)
        self._emit("shift.completed", {"cycles": [c["cycle_no"] for c in summary["cycles"]]})
        self.narrate("Shift complete. The ledger is the memory; every credit is accounted for.")
        return summary

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _finding(criterion: str, passed: bool, detail: str) -> dict:
    return {"criterion": criterion, "passed": bool(passed), "detail": detail}


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _is_angry(ticket: dict) -> bool:
    subject = ticket.get("subject") or ""
    return ticket.get("status") != "closed" and ("!!!" in subject or "NOW" in subject)


def run_shift(cycles: int = 2, db_path: Optional[str] = None) -> dict:
    engine = FloorEngine(db_path=db_path)
    try:
        return engine.run_shift(cycles=cycles)
    finally:
        engine.close()


def reset_floor(db_path: Optional[str] = None) -> dict:
    """Drop floor.db, re-init schema, re-seed the roster. Returns roster size."""
    conn = EDB.init_db(db_path, reset=True)
    try:
        agents = ECO.seed_roster(conn)
        return {"agents": len(agents), "economy_source": ECONOMY_SOURCE}
    finally:
        conn.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="orchestrator.engine",
                                     description="Run a THE FLOOR shift headlessly.")
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--reset", action="store_true",
                        help="reset floor.db (schema + roster) before the shift")
    parser.add_argument("--db", default=None, help="floor.db path (default: economy default)")
    args = parser.parse_args(argv)
    if args.reset:
        print(json.dumps(reset_floor(args.db), indent=2))
    summary = run_shift(cycles=args.cycles, db_path=args.db)
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
