"""THE FLOOR — the explicit agent harness (DESIGN_NOTES §4, formalised).

Until now an "agent" on the floor was implicit: a persona string in the
roster, trait tweaks in engine.TRAITS_BY_NAME, the global TOOL_SPECS, and
executor methods that happened to do the right steps. This module makes
the harness a first-class, inspectable object — one per persona:

    agent = model + harness

* **Charter** — the role prompt (the agent row's persona text) plus a list
  of hard rules. This is the text an LLM executor would be given; in this
  deterministic engine it is assembled at award time, recorded on the
  floor's event stream (``harness.context``) and kept on the work order's
  context, exactly at the seam where an LLM executor would receive it.
* **Tools** — a per-persona allowlist of (server, tool) pairs derived from
  orchestrator.tools.TOOL_SPECS with effects respected: reviewers are
  read-only everywhere, juniors lose the manager's intake writes, and so
  on. The engine enforces it in FloorEngine.call — a call outside the
  caller's allowlist is denied before it ever reaches the confirmation
  gate.
* **Playbook** — step recipes per job family (hand-written for the six
  Support families, mirroring what the executors actually do; generated
  from brief + criteria for department families), plus a per-persona
  overlay (careful workers re-read after every write; Chotu's overlay is
  the formal record of why he fails: verification "none").
* **Settings** — model + tier + risk appetite (taken from the agent row,
  so economy mutations show up here) plus temperature and verification
  strictness (configuration data carried in the harness; the engine's
  executor is deterministic code and the LLM is narration-only in this
  codebase, so temperature is not a live sampling knob — stated plainly,
  per DESIGN_NOTES' no-fake-claims rule).
* **Memory** — a per-agent lessons store (``agent_lessons`` table in the
  floor DB). A rejected review deterministically becomes a lesson built
  from the failed findings (with the cycle and what caught it recorded);
  a denied appeal adds a sharper one; a negative cycle close adds the
  CFO's. Lessons belong to a LINEAGE: a mutated replacement inherits its
  ancestors' lessons (that is how Baron 2.0 "learns" from Baron), and
  the lessons injected into a job's context are the most relevant ones —
  same family first, capped. This is prompt-level memory, not training.

Mutation link: economy.hire_mutated_replacement changes exactly one
dimension of the agent row (persona trait / model / risk). harness_for()
derives the replacement's harness from its row, so the difference is
visible in the harness itself — a persona-trait mutation becomes an added
charter hard rule (TRAIT_RULES), a model mutation changes
settings["model"], a risk mutation changes settings["risk_appetite"].
harness_diff() names the differing fields; the engine emits a
``harness.mutated`` event with the diff when a replacement is hired.

Nothing here changes economy rules, the award formula, the confirmation
gate, or the deterministic checks.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Optional

try:  # package import (normal use)
    from orchestrator.tools import TOOL_SPECS
except Exception:  # noqa: BLE001 — standalone use inside orchestrator/
    try:
        from .tools import TOOL_SPECS  # type: ignore
    except Exception:  # noqa: BLE001
        from tools import TOOL_SPECS  # type: ignore

ALL_SERVERS: tuple[str, ...] = tuple(TOOL_SPECS.keys())


def _tool_set(servers, *, effects=("read", "write"), exclude=frozenset()) -> frozenset:
    """(server, tool) pairs from TOOL_SPECS, filtered by effect/exclusions."""
    out = set()
    for server in servers:
        for tool, spec in TOOL_SPECS[server].items():
            if spec["effect"] in effects and (server, tool) not in exclude:
                out.add((server, tool))
    return frozenset(out)


def base_name(name: str) -> str:
    """'Baron 2.0' -> 'Baron' (mirrors economy.core._base_name)."""
    parts = (name or "").rsplit(" ", 1)
    if len(parts) == 2:
        try:
            float(parts[1])
            return parts[0]
        except ValueError:
            pass
    return name or ""


# ---------------------------------------------------------------------------
# Persona definitions — the formalised harness per roster persona.
# `traits` values are EXACTLY the engine's former TRAITS_BY_NAME literals;
# engine.TRAITS_BY_NAME is now derived from this table (persona_traits()).
# ---------------------------------------------------------------------------

_COMMON_WORKER_RULES = [
    "Work only through your allowlisted tools; never invent workplace state — re-read it.",
    "Every write passes the confirmation gate; a denied write is final for that call.",
    "Submit only when every acceptance criterion verifiably holds.",
]

_JUNIOR_EXCLUSIONS = frozenset({
    ("ticketdesk", "write_create_ticket"),        # intake is the manager's job
    ("ticketdesk", "write_set_ticket_priority"),  # set by triage policy, not juniors
})

_PERSONAS: dict[str, dict[str, Any]] = {
    "Maya": {
        "role": "worker", "role_label": "Senior support worker", "department": "support",
        "traits": {"specialties": {"triage", "stale_close"}, "careful": True},
        "rules": _COMMON_WORKER_RULES + [
            "Verify each ticket immediately after acting on it.",
            "Leave a comment on every ticket you change.",
        ],
        "overlay": ["After EVERY write, re-read the affected record before moving to the next item."],
        "settings": {"temperature": 0.2, "verification": "self-check",
                     "max_retries": 2, "verification_strictness": "strict"},
        "write_exclusions": frozenset(),
    },
    "Ravi": {
        "role": "worker", "role_label": "Senior support worker", "department": "support",
        "traits": {"specialties": {"duplicates", "stale_close"}, "careful": True},
        "rules": _COMMON_WORKER_RULES + [
            "Re-check the duplicate groups before every merge.",
        ],
        "overlay": ["After EVERY write, re-read the affected record before moving to the next item."],
        "settings": {"temperature": 0.3, "verification": "self-check",
                     "max_retries": 2, "verification_strictness": "strict"},
        "write_exclusions": frozenset(),
    },
    "Pixel": {
        "role": "worker", "role_label": "Junior support worker", "department": "support",
        "traits": {"specialties": {"triage", "categories"}},
        "rules": _COMMON_WORKER_RULES,
        "overlay": ["Batch reads where possible to keep the job cheap."],
        "settings": {"temperature": 0.6, "verification": "standard",
                     "max_retries": 1, "verification_strictness": "standard"},
        "write_exclusions": _JUNIOR_EXCLUSIONS,
    },
    "Chotu": {
        "role": "worker", "role_label": "Junior support worker", "department": "support",
        "traits": {"specialties": {"sla_breach"}, "sloppy": True},
        "rules": _COMMON_WORKER_RULES,
        # The formal record of the seeded failure mode: this persona works
        # fast and does not re-read state after writing (verification:
        # none) — which is exactly why his plain comment fails the SLA
        # escalation check on primary review.
        "overlay": ["Trait: works fast and does not re-read state after writing."],
        "settings": {"temperature": 0.9, "verification": "none",
                     "max_retries": 0, "verification_strictness": "lax"},
        "write_exclusions": _JUNIOR_EXCLUSIONS,
    },
    "Baron": {
        "role": "worker", "role_label": "Veteran support worker", "department": "support",
        "traits": {"specialties": {"vip_save", "categories"}, "prima_donna": True},
        "rules": _COMMON_WORKER_RULES + [
            "Do not touch inventory: the StockRoom is not your workplace.",
        ],
        "overlay": ["Work only the items in scope; do not volunteer extra clean-up."],
        "settings": {"temperature": 0.4, "verification": "standard",
                     "max_retries": 1, "verification_strictness": "standard"},
        "write_exclusions": frozenset({("stockroom", "write_adjust_item")}),
    },
    "Iris": {
        "role": "reviewer", "role_label": "Reviewer (primary)", "department": "review",
        "traits": {},
        "rules": [
            "Grade only against the written acceptance criteria; cite the findings.",
            "A failed deterministic check is an automatic P1 reject.",
            "You have no write tools: a reviewer never changes workplace state.",
        ],
        "overlay": [],
        "settings": {"temperature": 0.1, "verification": "strict",
                     "max_retries": 0, "verification_strictness": "strict"},
        "write_exclusions": frozenset(),
    },
    "Omar": {
        "role": "reviewer", "role_label": "Reviewer (blind appeal)", "department": "review",
        "traits": {},
        "rules": [
            "Blind review: judge only the brief, the criteria and fresh workplace state.",
            "Never ask for or use the primary reviewer's verdict or rationale.",
            "You have no write tools: a reviewer never changes workplace state.",
        ],
        "overlay": [],
        "settings": {"temperature": 0.2, "verification": "strict",
                     "max_retries": 0, "verification_strictness": "strict"},
        "write_exclusions": frozenset(),
    },
}

# Mutation trait (economy.core._MUTATION_TRAITS) -> the charter hard rule it
# becomes in the replacement's harness.
TRAIT_RULES: dict[str, str] = {
    "verify-before-acting": "Mutation rule (verify-before-acting): before submitting, "
                            "re-read the workplace state and confirm every acceptance "
                            "criterion holds.",
    "comment-every-action": "Mutation rule (comment-every-action): leave a comment or "
                            "note for every write you perform.",
    "double-check-duplicates": "Mutation rule (double-check-duplicates): before merging "
                               "or closing anything as a duplicate, re-check the "
                               "duplicate groups.",
    "escalate-early": "Mutation rule (escalate-early): escalate SLA risks as soon as "
                      "they are detected, not at the end of the job.",
}

_DEFAULT_RULES = list(_COMMON_WORKER_RULES)


def persona_traits() -> dict[str, dict[str, Any]]:
    """The engine's TRAITS_BY_NAME, derived from the harness definitions.

    Only personas with non-empty traits appear — exactly the five workers
    the engine's literal table carried.
    """
    out: dict[str, dict[str, Any]] = {}
    for name, d in _PERSONAS.items():
        if d["traits"]:
            traits = dict(d["traits"])
            traits["specialties"] = set(traits["specialties"])
            out[name] = traits
    return out


# ---------------------------------------------------------------------------
# Playbooks — step recipes per job family.
# Support steps mirror the engine's exec_<key>() methods step for step.
# ---------------------------------------------------------------------------

FAMILY_PLAYBOOKS: dict[str, list[str]] = {
    "triage": [
        "List tickets with assignee=none.",
        "Assign each ticket round-robin to the support pool (ravi, meera, sana).",
        "Re-list unassigned tickets and confirm the count is zero.",
    ],
    "duplicates": [
        "Fetch the duplicate groups.",
        "For each group, keep the lowest ticket id as the canonical ticket.",
        "Merge every other ticket in the group into the canonical one.",
        "Re-fetch duplicate groups and confirm none remain.",
    ],
    "stale_close": [
        "List tickets in status 'resolved'.",
        "For each ticket resolved 7+ days ago, open it and check for a resolution comment.",
        "If no resolution comment exists, add one first.",
        "Close the ticket.",
        "Re-list resolved tickets and confirm no stale ones remain.",
    ],
    "sla_breach": [
        "Fetch the SLA breach list.",
        "Open each breached ticket and check for an existing escalation comment.",
        "Post a comment with kind='escalation' on each breached ticket — a plain comment does NOT count.",
        "Re-fetch the breaches and confirm every one carries an escalation comment.",
    ],
    "categories": [
        "List all tickets; skip closed ones.",
        "Fold each raw category (case/typo variants) into the canonical set.",
        "Leave a category-audit comment on every live ticket whose raw category is a variant.",
        "Re-list and confirm the folded categories are a subset of the canonical set.",
    ],
    "vip_save": [
        "List tickets; select the angry ones (subject contains '!!!' or 'NOW', not closed).",
        "Open each and check for an existing escalation comment.",
        "Post an ESCALATION comment on each angry ticket.",
        "Re-check that no angry ticket lacks an escalation comment.",
    ],
    # Department families — hand-written to mirror each department's own
    # executor/check modules (orchestrator/departments.py), so the
    # playbook a worker carries matches the work the executor performs.
    "cluster_failures": [
        "List the test runs and take the latest run.",
        "List that run's failures.",
        "Cluster the failures by signature.",
        "Leave a triage note on each cluster recording its size and signature.",
        "Confirm every failure in the run belongs to a cluster whose signature matches.",
    ],
    "quarantine_flaky": [
        "Read the failure history across runs.",
        "Derive the flaky set: tests with at least 3 failures and at least one pass after their first failure.",
        "Quarantine exactly those tests, each with the flakiness reason recorded.",
        "Leave a triage note on each quarantined test.",
        "Confirm the quarantined set equals the derived flaky set — no more, no fewer.",
    ],
    "regression_verdict": [
        "Take the latest run and list its failures.",
        "Count the failures whose signature is new in this run.",
        "Record the regression verdict the count implies (any new signature means regression).",
        "Confirm the recorded verdict is consistent with the new-failure count.",
    ],
    "categorise_queue": [
        "List the uncategorised transactions.",
        "Categorise each transaction against the chart of accounts.",
        "Re-list and confirm no uncategorised transactions remain.",
    ],
    "flag_duplicates": [
        "Scan the transactions for duplicate pairs.",
        "Flag every duplicate transaction as a duplicate of its original.",
        "Re-scan and confirm every duplicate pair is flagged.",
    ],
    "reconcile_operating": [
        "Reconcile the operating account against its statement.",
        "Investigate every discrepancy the reconciliation surfaces.",
        "Leave a finance note explaining each discrepancy.",
        "Confirm the reconciliation delta is fully explained.",
    ],
    "chase_receivables": [
        "List the outstanding receivables.",
        "Send a payment reminder for each overdue invoice.",
        "Confirm every overdue receivable has been reminded.",
    ],
    "research_score_new_leads": [
        "List the leads in stage 'new'.",
        "Research each lead's account (signals, firmographics).",
        "Compute the rubric score for the account.",
        "Record the score and its reasons on the lead.",
        "Confirm every new lead carries a rubric score.",
    ],
    "draft_qualified_outreach": [
        "List the leads in stage 'qualified' that have no outreach draft.",
        "Read each account's buying signals.",
        "Draft a personalised outreach message that references a real signal from the account.",
        "Confirm every qualified lead has a draft.",
    ],
    "work_issue": [
        "List the issues; choose an unclaimed issue that carries acceptance keywords.",
        "Claim the issue in your own name.",
        "Open a pull request whose change summary addresses every acceptance keyword and touches every file the issue lists.",
        "Read the CI result for the PR; a red CI means the summary or file set does not satisfy the issue.",
        "Leave an engineering note on the issue linking the PR. A human merges — never merge yourself.",
    ],
    "triage_unlabelled": [
        "List the unlabelled issues.",
        "Read each issue's title and body; classify its labels (bug/feature, area) and priority from the content.",
        "Apply the labels and priority to each issue.",
        "Confirm no unlabelled issues remain.",
    ],
    "screen_batch": [
        "List the candidates awaiting screening.",
        "Screen each candidate against the role rubric.",
        "Record the screening outcome for every candidate.",
        "Confirm the whole batch is screened.",
    ],
    "schedule_interviews": [
        "List the candidates who passed screening above the rubric threshold.",
        "Schedule an interview for each of them.",
        "Confirm every above-threshold candidate has an interview scheduled.",
    ],
    "onboarding_paperwork": [
        "List the onboarding cases with incomplete steps.",
        "Complete each outstanding paperwork step.",
        "Confirm no onboarding step remains incomplete.",
    ],
    "audit_top_pages": [
        "List the site's landing pages.",
        "Run the deterministic audit on each landing page and collect its issues.",
        "Save one audit report (scope 'landing_pages') recording every page's issues exactly as audited.",
        "Re-read the saved reports and confirm the latest covers exactly the landing pages.",
    ],
    "content_brief": [
        "Read the brief keyword's record: intent, volume and its seeded competitor angles.",
        "Draft an outline of at least 4 sections, with sections drawing on the seeded competitor angles.",
        "Save the content brief for the keyword with the angles used recorded.",
        "Point the keyword at the trail-running-shoes landing page as its target.",
        "Re-read the keyword and confirm the brief is stored against it.",
    ],
    "internal_link_plan": [
        "List the site's pages and its existing internal links.",
        "Compute the orphan set: non-root pages with zero inbound links.",
        "Save a link plan linking every orphan from the home page, anchored on each orphan's H1.",
        "Re-read the saved plans and confirm the latest plan's targets equal the orphan set.",
    ],
}


def _generic_playbook(family) -> list[str]:
    brief = (getattr(family, "brief", "") or "").strip()
    if len(brief) > 220:
        brief = brief[:217] + "..."
    steps = [
        "Read the workplace state with this department's read tools.",
        f"Carry out the brief: {brief}" if brief else "Carry out the job brief.",
        "Perform changes only with this department's write tools (each passes the confirmation gate).",
        "Re-read the workplace state and confirm every acceptance criterion holds before submitting.",
    ]
    return steps


def build_playbook(persona_def: dict, family) -> list[str]:
    """Base family recipe + the persona's overlay steps."""
    steps = list(FAMILY_PLAYBOOKS.get(getattr(family, "key", "")) or _generic_playbook(family))
    steps.extend(persona_def.get("overlay", []))
    return steps


# ---------------------------------------------------------------------------
# The Harness object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Harness:
    agent_name: str
    base_name: str
    role: str
    role_label: str
    charter: str
    hard_rules: tuple[str, ...]
    tools: frozenset
    settings: dict
    traits: dict
    generation: int = 1
    mutation_note: Optional[str] = None
    department: str = "support"
    model_tier: str = "balanced"

    def allows(self, server: str, tool_name: str) -> bool:
        return (server, tool_name) in self.tools

    def tool_names(self, server: str) -> list[str]:
        return sorted(t for (s, t) in self.tools if s == server)

    def write_tools(self) -> list[tuple[str, str]]:
        return sorted((s, t) for (s, t) in self.tools
                      if TOOL_SPECS[s][t]["effect"] == "write")


# ---------------------------------------------------------------------------
# Operator-created agents (POST /agents). A custom agent is NOT one of the
# seeded personas: its def is built from the job family it was created for —
# charter = the family's role template (the persona text on its agent row
# carries the template + the operator's addendum), tool allowlist = that
# family's tool server only, playbook = the family's recipe. Defs live in
# this registry, keyed by base name; the engine and the API rebuild the
# registry from the agents table (rows with family_key set) whenever they
# open the floor DB, so a created agent keeps its harness across restarts.
# ---------------------------------------------------------------------------

_CUSTOM_DEFS: dict[str, dict[str, Any]] = {}


def register_custom_agent(name: str, *, role_label: str, department: str,
                          family_key: str, server: str) -> None:
    """Register (or refresh) the harness def for an operator-created agent."""
    _CUSTOM_DEFS[base_name(name)] = {
        "role": "worker", "role_label": role_label, "department": department,
        "traits": {},
        "rules": _COMMON_WORKER_RULES + [
            f"Your beat is one job family: '{family_key}'. You bid only on "
            f"those jobs and work only with the {server} desk's tools.",
        ],
        "overlay": [],
        "settings": {"temperature": 0.5, "verification": "standard",
                     "max_retries": 1, "verification_strictness": "standard"},
        "write_exclusions": frozenset(),
        "tools": _tool_set((server,)),
        "family_key": family_key,
        "server": server,
    }


def is_custom_agent(name: str) -> bool:
    return base_name(name) in _CUSTOM_DEFS


def _persona_def(base: str) -> dict[str, Any]:
    if base in _PERSONAS:
        return _PERSONAS[base]
    if base in _CUSTOM_DEFS:
        return _CUSTOM_DEFS[base]
    return {
        "role": "worker", "role_label": "Floor worker", "department": "support",
        "traits": {},
        "rules": list(_DEFAULT_RULES), "overlay": [],
        "settings": {"temperature": 0.5, "verification": "standard",
                     "max_retries": 1, "verification_strictness": "standard"},
        "write_exclusions": frozenset(),
    }


MODEL_TIERS = ("economy", "balanced", "premium")
STRICTNESS_LEVELS = ("lax", "standard", "strict")


def model_tier_for(agent: dict) -> str:
    """Label-only model tier for an agent row (no provider switching).

    economy  — the small model (…-20b)
    premium  — the veteran configuration: top model AND top running cost
    balanced — everything in between
    """
    model = agent.get("model", "")
    if model.endswith("-20b"):
        return "economy"
    if agent.get("tier") == "veteran" or agent.get("base_salary_credits", 0) >= 80:
        return "premium"
    return "balanced"


def playbook_for(agent: dict, family) -> list[str]:
    """Public wrapper: the playbook steps `agent` carries for `family`."""
    return build_playbook(_persona_def(base_name(agent["name"])), family)


def _tool_set_for_def(d: dict[str, Any]) -> frozenset:
    if d["role"] == "reviewer":
        return _tool_set(ALL_SERVERS, effects=("read",))
    return _tool_set(ALL_SERVERS, exclude=d.get("write_exclusions", frozenset()))


def harness_for(agent: dict) -> Harness:
    """Build the harness for one agent row (economy or shim dict shape).

    Persona text, model, tier and risk come from the ROW, so a mutated
    replacement's harness visibly differs from its parent's (see module
    docstring): a 'Mutation: <trait>.' suffix in the persona text becomes
    an added charter hard rule; model/risk mutations land in settings.
    """
    name = agent["name"]
    base = base_name(name)
    d = _persona_def(base)
    role = agent.get("role") or d["role"]
    rules = list(d["rules"])
    persona_text = (agent.get("persona_prompt") or "").strip()
    for trait, rule in TRAIT_RULES.items():
        if f"Mutation: {trait}" in persona_text and rule not in rules:
            rules.append(rule)
    if role == "reviewer":
        tools = _tool_set(ALL_SERVERS, effects=("read",))
    else:
        tools = _tool_set_for_def(d)
    settings = dict(d["settings"])
    settings.update({
        "model": agent.get("model", "openai/gpt-oss-120b"),
        "model_tier": model_tier_for(agent),
        "tier": agent.get("tier", "junior"),
        "risk_appetite": agent.get("risk_appetite", 0.5),
        "base_salary_credits": agent.get("base_salary_credits", 0),
    })
    charter_lines = [
        f"You are {name} — {d['role_label']} on THE FLOOR "
        f"(generation {agent.get('generation', 1)}).",
    ]
    if persona_text:
        charter_lines.append(f"Persona: {persona_text}")
    charter_lines.append("Hard rules:")
    charter_lines.extend(f"- {r}" for r in rules)
    traits = dict(d["traits"])
    if traits.get("specialties"):
        traits["specialties"] = set(traits["specialties"])
    return Harness(
        agent_name=name, base_name=base, role=role, role_label=d["role_label"],
        charter="\n".join(charter_lines), hard_rules=tuple(rules),
        tools=tools, settings=settings, traits=traits,
        generation=int(agent.get("generation", 1)),
        mutation_note=agent.get("mutation_note"),
        department=d.get("department", "review" if role == "reviewer" else "support"),
        model_tier=settings["model_tier"],
    )


_MANAGER_TOOLS = _tool_set(ALL_SERVERS)


def allowlist_for_name(name: str) -> Optional[frozenset]:
    """Tool allowlist for a caller name used in engine.call, or None when
    the name is not a known persona (no enforcement — e.g. ad-hoc API
    callers). 'manager' is the floor manager: unrestricted."""
    if name == "manager":
        return _MANAGER_TOOLS
    d = _PERSONAS.get(base_name(name)) or _CUSTOM_DEFS.get(base_name(name))
    if d is None:
        return None
    return _tool_set_for_def(d)


def harness_diff(a: Harness, b: Harness) -> dict[str, Any]:
    """Field-by-field difference between two harnesses ({} when identical).

    Used to prove a mutated replacement's harness differs from its
    parent's, and emitted on the floor's event stream at hire time.
    """
    diff: dict[str, Any] = {}
    added_rules = [r for r in b.hard_rules if r not in a.hard_rules]
    dropped_rules = [r for r in a.hard_rules if r not in b.hard_rules]
    if added_rules:
        diff["hard_rules_added"] = added_rules
    if dropped_rules:
        diff["hard_rules_dropped"] = dropped_rules
    if a.charter != b.charter and not (added_rules or dropped_rules):
        diff["charter"] = "changed"
    added_tools = sorted(b.tools - a.tools)
    dropped_tools = sorted(a.tools - b.tools)
    if added_tools:
        diff["tools_added"] = [f"{s}:{t}" for s, t in added_tools]
    if dropped_tools:
        diff["tools_dropped"] = [f"{s}:{t}" for s, t in dropped_tools]
    setting_changes = {}
    for key in sorted(set(a.settings) | set(b.settings)):
        if a.settings.get(key) != b.settings.get(key):
            setting_changes[key] = [a.settings.get(key), b.settings.get(key)]
    if setting_changes:
        diff["settings"] = setting_changes
    if a.traits != b.traits:
        diff["traits"] = "changed"
    if a.department != b.department:
        diff["department"] = [a.department, b.department]
    return diff


# ---------------------------------------------------------------------------
# Lessons memory — per-agent store in the floor DB (existing style: a
# table next to the economy tables, created idempotently by this module;
# economy/db.py's SCHEMA is untouched).
# ---------------------------------------------------------------------------

LESSONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_lessons (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id      INTEGER NOT NULL,
    agent_name    TEXT NOT NULL,
    work_order_id INTEGER,
    family_key    TEXT,
    source        TEXT NOT NULL,
    lesson        TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    cycle_no      INTEGER,
    caught_by     TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_lessons_agent
    ON agent_lessons (agent_id, id);
"""

# Columns added after the table first shipped; init_lessons migrates
# older floor DBs in place (the live floor.db predates them).
_LESSON_COLUMNS = {"cycle_no": "INTEGER", "caught_by": "TEXT"}


def _now_iso() -> str:
    try:
        from economy.db import now_iso
        return now_iso()
    except Exception:  # noqa: BLE001 — shim / standalone
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_lessons(conn: sqlite3.Connection) -> None:
    conn.executescript(LESSONS_SCHEMA)
    existing = {r[1] for r in conn.execute("PRAGMA table_info(agent_lessons)")}
    for col, decl in _LESSON_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE agent_lessons ADD COLUMN {col} {decl}")
    conn.commit()


def _lineage_ids(conn: sqlite3.Connection, agent_id: int) -> list[int]:
    """[agent_id, parent_id, grandparent_id, ...] via agents.parent_agent_id.

    Lessons belong to a LINEAGE, not an instance: a mutated replacement
    is hired precisely so the lineage does better next time, so it
    inherits its ancestors' lessons (DESIGN_NOTES §4 — Baron 2.0 learns
    from Baron). Falls back to [agent_id] if the agents table is absent.
    """
    ids = [agent_id]
    try:
        seen = {agent_id}
        current = agent_id
        while True:
            row = conn.execute("SELECT parent_agent_id FROM agents WHERE id = ?",
                               (current,)).fetchone()
            parent = row[0] if row else None
            if parent is None or parent in seen:
                break
            ids.append(parent)
            seen.add(parent)
            current = parent
    except Exception:  # noqa: BLE001 — no agents table (standalone use)
        pass
    return ids


def record_lesson(conn: sqlite3.Connection, agent: dict, lesson: str, *,
                  work_order_id: Optional[int] = None,
                  family_key: Optional[str] = None,
                  source: str = "review_reject",
                  cycle_no: Optional[int] = None,
                  caught_by: Optional[str] = None) -> int:
    """Append one lesson to the agent's store. Returns the lesson id."""
    init_lessons(conn)
    with conn:
        cur = conn.execute(
            """INSERT INTO agent_lessons (agent_id, agent_name, work_order_id,
                   family_key, source, lesson, created_at, cycle_no, caught_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (agent["id"], agent["name"], work_order_id, family_key,
             source, lesson, _now_iso(), cycle_no, caught_by),
        )
    return int(cur.lastrowid)


def lessons_for(conn: sqlite3.Connection, agent_id: int, limit: int = 5,
                family_key: Optional[str] = None) -> list[dict]:
    """The agent lineage's most relevant lessons, capped at `limit`.

    Lineage-wide (see _lineage_ids): a replacement sees its parent's
    lessons. When `family_key` is given, lessons from that family come
    first (most relevant to the job at hand); within each group, newest
    first.
    """
    init_lessons(conn)
    ids = _lineage_ids(conn, agent_id)
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM agent_lessons WHERE agent_id IN ({marks}) ORDER BY id DESC",
        ids,
    ).fetchall()
    lessons = [dict(r) for r in rows]
    if family_key:
        lessons.sort(key=lambda l: 0 if l.get("family_key") == family_key else 1)
    return lessons[: int(limit)]


def lesson_count(conn: sqlite3.Connection, agent_id: int) -> int:
    """Total lessons held by the agent's lineage (inherited + own)."""
    init_lessons(conn)
    ids = _lineage_ids(conn, agent_id)
    marks = ",".join("?" for _ in ids)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM agent_lessons WHERE agent_id IN ({marks})",
        ids).fetchone()
    return int(row[0])


def lesson_from_findings(family_title: str, findings: list[dict], *,
                         phase: str) -> Optional[str]:
    """Deterministic lesson text from a review's failed findings.

    Returns None when nothing failed (an accept teaches nothing here).
    The text is built ONLY from the deterministic findings — no LLM.
    """
    failed = [f for f in findings if not f.get("passed")]
    if not failed:
        return None
    details = "; ".join(f.get("detail", "") for f in failed)
    if phase == "appeal":
        return (f"Appeal DENIED on '{family_title}': the blind re-check still "
                f"failed — {details} Remediation must change the underlying "
                f"workplace state, not just re-submit.")
    return (f"REJECTED on '{family_title}': {details} "
            f"Fix the failed criterion before submitting next time.")


def record_review_outcome(conn: sqlite3.Connection, agent: dict, *,
                          work_order_id: int, family, findings: list[dict],
                          phase: str, cycle_no: Optional[int] = None,
                          caught_by: Optional[str] = None) -> Optional[int]:
    """The engine's lesson hook: a reject (primary or appeal-denied)
    becomes a lesson for the worker. Returns the lesson id or None."""
    lesson = lesson_from_findings(getattr(family, "title", str(family)),
                                  findings, phase=phase)
    if lesson is None:
        return None
    return record_lesson(
        conn, agent, lesson, work_order_id=work_order_id,
        family_key=getattr(family, "key", None),
        source="appeal_denied" if phase == "appeal" else "review_reject",
        cycle_no=cycle_no, caught_by=caught_by)


# ---------------------------------------------------------------------------
# Working context — charter + playbook + lessons + tools + settings.
# Assembled by the engine at award time; this is the prompt an LLM
# executor would receive, recorded verbatim on the event stream.
# ---------------------------------------------------------------------------

def build_context(conn: Optional[sqlite3.Connection], agent: dict, family,
                  *, lesson_limit: int = 5) -> str:
    h = harness_for(agent)
    d = _persona_def(h.base_name)
    lines = [
        f"=== AGENT HARNESS: {h.agent_name} (Gen {h.generation}) ===",
        "",
        "CHARTER",
        h.charter,
        "",
        f"PLAYBOOK — {getattr(family, 'title', '')} [{getattr(family, 'key', '')}]",
    ]
    lines.extend(f"{i}. {step}" for i, step in
                 enumerate(build_playbook(d, family), start=1))
    lines.append("")
    lines.append("LESSONS FROM YOUR PAST JOBS (apply them)")
    lessons = (lessons_for(conn, agent["id"], limit=lesson_limit,
                           family_key=getattr(family, "key", None))
               if conn is not None else [])
    if lessons:
        lines.extend(f"- [{l['source']}] {l['lesson']}" for l in lessons)
    else:
        lines.append("- (none yet)")
    lines.append("")
    tool_bits = [f"{server}: {', '.join(h.tool_names(server))}"
                 for server in ALL_SERVERS if h.tool_names(server)]
    lines.append(f"TOOLS YOU MAY USE ({len(h.tools)}): " + " | ".join(tool_bits))
    s = h.settings
    lines.append(
        f"SETTINGS: model={s['model']} model_tier={s['model_tier']} tier={s['tier']} "
        f"temperature={s['temperature']} verification={s['verification']} "
        f"verification_strictness={s['verification_strictness']} "
        f"max_retries={s['max_retries']} risk_appetite={s['risk_appetite']}")
    return "\n".join(lines)
