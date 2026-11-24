# THE FLOOR — Vibe-a-thon Submission

**Event:** Vibe-a-thon (Geek Room × 2nd Brain Labs) · **Track:** 4 — Open Innovation
**Tagline:** *Every agent has a price. Every price has a consequence.*

---

## The problem

Two things are broken about AI agents at work today:

1. **Agents cannot operate the software companies actually run on.** Real work lives in legacy internal systems — ticket desks, inventory tools, admin panels — that have no agent interface. Every demo rebuilds a toy version of the system instead of touching the real one.
2. **Agent demos have no accountability.** An agent does a task, a human says "looks good", and that is the whole story. Nobody bids for the work, nobody is audited, bad work has no cost, and no agent ever gets fired. There is no economy — so there is no pressure to be good, cheap, or careful.

## The solution

**THE FLOOR is a software factory where AI agents are employees.**

- A **Manager** agent scans a real support backlog and posts jobs with credit budgets.
- **Workers** (deliberately mixed model tiers) place **sealed bids** — price + confidence. The Manager awards by a visible, deterministic formula:
  `score = 0.5·(1 − price/cap) + 0.3·(reputation/100) + 0.2·(confidence/100)`
- The winner does the work **only through Synapse-generated MCP tools** — real tool calls against the real target system.
- A **Reviewer** audits the work product (the full tool-call transcript) with **P0–P3 severity**. Deterministic verification checks run *before* the LLM Reviewer ever sees the work; a failed check is an automatic P1.
- A rejected worker may **appeal** to a blind second Reviewer — who sees the job spec and the work product only, never the first verdict. An overturn pays the worker in full and **drops the first Reviewer's reputation**.
- A mostly-deterministic **CFO** runs payroll. Money math is code, not LLM: an append-only SQLite ledger, per-cycle upkeep, and a hard rule — **two consecutive negative cycles and the worker is fired** (a PinkSlip event in the feed) and replaced by a **mutated hire** whose lineage is shown in the UI ("Ravi 2.0 — mutation: verify-before-acting").
- The **only human gate** is final approval of the results batch.

The demo workplace is **TicketDesk**, an ordinary FastAPI support-ticket API seeded with ~40 messy tickets (duplicates, SLA breaches, unassigned P1s, inconsistent categories). Job families: SLA breach sweep, duplicate collapse, backlog triage, and a cross-system VIP save in the finale. A second system, **StockRoom** (inventory), joins live in the finale.

**Six departments are live, not one.** The same market loop runs across six workplaces, each its own real system of record with its own Synapse-shaped tool surface and its own deterministic acceptance checks: **Support** (TicketDesk + StockRoom), **QA triage** (failure clustering, flaky-test quarantine, regression verdicts), **Bookkeeping** (categorisation, duplicate flagging, reconciliation, receivables — the tools move no money), **SDR** (rubric-scored lead research, outreach *drafts only* — no send tool exists), **Engineering** (issue work + PRs with CI as the check; humans merge), and **HR** (rubric screening, interview scheduling, onboarding paperwork — no hire/reject tool exists). One roster bids across every department; every job clears the same review → blind appeal → payroll machinery. In the verified integration shift, a single cycle posted 19 jobs across all six departments and every one was accepted and paid.

**Two trust modes.** The confirmation gate has two settings, switchable live from the console: **Manual** — every write waits for a human at the gate; **Auto** — writes are auto-approved, each one written to the audit log as a `confirmation.auto_approved` event, and the floor runs itself cycle after cycle until a human-set budget cap stops it (the loop projects the next cycle's spend and stops *before* crossing the cap).

## Why Synapse is central — Synapse is the factory's only hands

Synapse is not a component of THE FLOOR; it is the precondition for it. Four ways:

1. **Workers hold nothing else.** A worker agent has no database handle, no HTTP client, no shell. Its entire tool list *is* the tool list of the Synapse-generated MCP server for that workplace. Remove Synapse and the workforce cannot touch anything.
2. **Onboarding a workplace *is* a Synapse command.** Point `synapse build` at a codebase and it becomes a workplace; the job types the Manager can post are derived from the tools that build produces. New system, new capabilities — no integration project.
3. **The finale is a Synapse command.** A job arrives that no existing tool can do. The presenter adds one endpoint to the second codebase and runs `synapse build --discover`; the tool registry hot-refreshes, the new tool lights up, and the previously impossible job gets staffed and completed — live.
4. **Exposure is deliberate, and Synapse is where that decision lives.** The endpoint allowlist passed to the build is the factory's safety boundary: read and work endpoints are exposed; delete and bulk-close endpoints are never turned into tools at all. `--smart-names` is used where clearer tool names improve agent reliability.

Although we enter Track 4, THE FLOOR is deliberately built to also clear the other tracks' bars: at least three real multi-step tasks completed through an Auto-mode MCP server with zero changes to the target app's code (Track 1), and a live `--discover` moment where a factory learns a new capability mid-shift (Track 3).

**Build mode:** `synapse build --local` with Groq is the primary path — it never counts against quota, needs no Synapse account, and generates a real Python MCP server file we can inspect and version. One hosted Auto build of TicketDesk is kept as a documented hot spare.

## Architecture

```
ui-next/       Mission-control console — agent-orchestrator's own frontend
               (vendored with attribution, Apache-2.0), recoloured to a
               warm-dark palette; job board with department filter, roster,
               inspector, ledger + event stream, payroll dialog, Manual/Auto
               trust-mode controls, and a recorded-demo replay for hosted
               viewing — REST snapshots + SSE event stream
api/           FastAPI — REST state endpoints, SSE event bus, run/reset,
               mode + auto-run endpoints (cap, start/pause/stop)
orchestrator/  Shift loop, worker, reviewer, blind appeal; department
               registration from each workplace's own jobs pack; the
               agent-orchestrator lifecycle state machine + supervised
               worker runner ported in (ao_lifecycle.py, ao_runner.py)
economy/       Ledger, payroll/CFO, reputation — deterministic Python, no LLM
mcp_manager/   Spawns & supervises Synapse MCP servers, tool registry,
               read/write classification, confirmation enforcement
onboarder/     Wraps `synapse build` / `synapse build --discover` runs
targets/
  ticketdesk/  Support — FastAPI support-ticket API (:8101)
  stockroom/   Support — inventory API (:8102, joins in the finale)
  qa/          QA triage — test-run results API (:8103)
  bookkeeping/ Bookkeeping — accounting API (:8104)
  sdr/         SDR — CRM API (:8105)
  engineering/ Engineering — repo/issues API (:8106)
  hrdesk/      HR — candidates/onboarding API (:8107)
```

Key invariants:

- **Ledger is append-only.** Every credit movement is a row; balances are derived, never edited.
- **Every action is an auditable record.** A job's tool-call transcript is the work product the Reviewer grades.
- **Reputation is a real, losable asset** — for workers *and* reviewers (an overturned verdict costs the first Reviewer reputation).

## Safety: the confirmation gate and deliberate exposure

- **Exposure is the first safety decision.** Delete and bulk-close endpoints are never exposed as tools, so no prompt, bug, or confused agent can invoke them — the capability does not exist on the Floor.
- **Writes pass a confirmation gate.** Read tools execute immediately; write tools require confirmation before dispatch, and the MCP manager independently refuses any write call that arrives without a confirmation. Denials are fed back to the worker as an observation it must adapt to.
- **The gate has two trust modes, and Auto is not "ungated".** In Manual mode a human approves each write. In Auto mode the floor runs unattended, but every auto-approval is emitted as an auditable `confirmation.auto_approved` event (tool, args, work order), the run is bounded by a budget cap the loop will not cross, and switching back to Manual re-gates the very next write. Human-only powers are enforced by *absent tools*, not policy text: Bookkeeping cannot move money, SDR cannot send, Engineering cannot merge, HR cannot hire or reject.
- **Deterministic checks before LLM judgement.** Machine-checkable acceptance criteria (e.g. "zero unassigned tickets remain", "every breached ticket has an escalation comment") are verified in code before the Reviewer reads anything.
- **The human gate is small and final:** a person approves the results batch. Hiring, firing, payroll, and appeals are autonomous — that is the product's point — but no batch of real-world changes is closed without a human signature.

## Setup and run instructions

Prerequisites: Python 3.11+, Node 20+ (for the Synapse CLI), a Groq API key.

```bash
# 1. Configure
cp .env.example .env        # fill in GROQ_API_KEY

# 2. Build the workplace with Synapse (primary path: --local + Groq)
npm install -g @2ndbrainlabs-ai/synapse-cli
synapse model set groq
cd targets/ticketdesk
synapse build --local --auto --endpoints "GET /tickets,GET /tickets/{id},GET /tickets/duplicates,GET /sla/breaches,GET /stats/summary,POST /tickets,POST /tickets/{id}/assign,POST /tickets/{id}/priority,POST /tickets/{id}/comment,POST /tickets/{id}/status,POST /tickets/merge"

# 3. Run the target system (the legacy app agents will operate)
pip install -r requirements.txt
python3 seed.py             # create ticketdesk.db with the messy dataset
uvicorn app:app --port 8101
python3 reset.py            # restore the exact seeded state at any time

# 4. Run the factory API (serves the mission-control UI on the same origin)
#    from the repo root, per repo/README.md layout:
#    uvicorn api:app  (see api/README.md for the exact module/entrypoint)

# 5. Open the mission control, click "Run Shift", watch the floor work.
#    "Reset Demo" restores the exact demo-start state in seconds.
```

## What was built vs what was cut

**Built (the demo path):**

- TicketDesk target system with the seeded messy dataset and a one-command reset.
- The market loop end to end: Manager posting → sealed bids → visible award formula → execution through Synapse-generated MCP tools → Reviewer audit (deterministic checks first, P0–P3 severity) → payment from the append-only ledger.
- Blind appeal with Reviewer-reputation consequences.
- CFO payroll: firing on two consecutive negative cycles (PinkSlip) and mutated replacement hires with visible lineage.
- Confirmation gate on write tools; deliberate endpoint exposure (no delete/bulk-close tools exist).
- Mission-control UI: live org chart, job board with bid ticker, ledger and narration feeds, payroll/firing highlights.
- **Six live departments** (Support, QA triage, Bookkeeping, SDR, Engineering, HR) — 20 job families, one roster bidding across all of them, each department verified by its own deterministic checks.
- **Manual/Auto trust modes** in the console: a topbar toggle, an auto-run panel (budget cap, start/pause/stop, spent-vs-cap), and auto-approvals surfaced in the audit stream.
- **agent-orchestrator adoption, twice:** its frontend is the console (vendored with attribution), and its orchestration core — the work-order lifecycle state machine and the supervised worker runner — is ported into the engine, emitting lifecycle events alongside the economy's own.
- **The Foreman**, the floor's mascot (clay-orange robot foreman), across the landing page and console, with dedicated poses for payroll and PinkSlip moments.
- The StockRoom `--discover` finale: one new endpoint + `synapse build --discover` teaches the factory a capability it did not have minutes earlier.

**Cut or reduced, per the pre-agreed cut order** (appeal → mutation lineage → live `--discover` → custom composed tool → UI theatre → backlog-scan intake → multi-cycle payroll):

- **Custom composed tool** (`resolve_ticket_end_to_end` as a single Custom-mode tool, with a one-tool-vs-many comparison) — first stretch goal if time remains; the confirmation gate alone carries the Track 2 safety story.
- **Backlog-scan intake** — the Manager posts seeded job families rather than free-form backlog discovery.
- **Hosted hot spare** — documented and configured, but the demo runs the `--local` build; the spare depends on a Synapse console API key and is insurance, not the primary path.
- If the live `--discover` moment misbehaves on the day, StockRoom ships **pre-onboarded** and the two-system story is unchanged; the recorded demo uses the genuine live path.

**Never cut, by design:** the confirmation gate, the append-only ledger, and real MCP execution against the real target app. The moment tool results are faked, the submission's core claim dies — so they never are.
