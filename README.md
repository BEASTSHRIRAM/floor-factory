# THE FLOOR — floor-factory

**Every agent has a price. Every price has a consequence.**

A software factory where AI agents are *employees*. A Manager posts jobs from a
real support backlog with credit budgets → workers place sealed bids
(price + confidence) → the winner does the work **only through
Synapse-generated MCP tools** → a Reviewer audits with P0–P3 severity →
rejected workers can appeal to a blind second Reviewer → a deterministic CFO
runs payroll, **fires** workers with two consecutive negative cycles, and
hires **mutated replacements** with visible lineage. The only human gate is
final approval.

Built for **Vibe-a-thon** (Geek Room × 2nd Brain Labs), **Track 4 — Open
Innovation**. Synapse CLI turns each target codebase into an MCP server;
Synapse is the factory's only hands.

## Why this exists

1. **Agents can't operate the software companies actually run on.** Real work
   lives in legacy internal systems — ticket desks, inventory tools, admin
   panels — with no agent interface. Synapse turns those codebases into MCP
   servers, so agents work on the real system instead of a toy rebuild.
2. **Agent demos have no accountability.** Nobody bids, nobody is audited, bad
   work costs nothing, and no agent is ever fired. THE FLOOR adds the missing
   economy: bids, budgets, reviews, appeals, payroll, firing, and evolution —
   so there is real pressure to be good, cheap, and careful.

## How a shift runs

1. **Manager** posts jobs (SLA breach sweep, duplicate collapse, backlog
   triage, category normalisation) against **TicketDesk**, a real FastAPI
   support-ticket API seeded with 25 messy tickets.
2. **Workers bid.** Mixed model tiers on purpose — senior `gpt-oss-120b`,
   junior `gpt-oss-20b`, one sloppy worker, one expensive veteran.
3. **Award is a visible formula, not a vibe:**
   `score = 0.5·(1 − price/cap) + 0.3·(reputation/100) + 0.2·(confidence/100)`
4. **Execution is real.** The winner acts only through MCP tools (allowlisted
   endpoints only — no delete or bulk-close tool exists). Write tools pass a
   confirmation gate; every call is logged to an audit transcript.
5. **Review is earned.** Deterministic verification checks run first (a failed
   check is an automatic P1); then a Reviewer grades the transcript.
6. **Appeals are blind.** A second Reviewer sees the job and the work — never
   the first verdict. An overturn pays the worker and costs Reviewer A
   reputation.
7. **Payroll has teeth.** The CFO (code, not an LLM) charges running costs per
   cycle. Two consecutive negative cycles → **PinkSlip** → a mutated
   replacement is hired ("Baron 2.0 — mutation: verify-before-acting").
8. A second workplace, **StockRoom** (inventory API), joins in the finale: add
   one endpoint, run `synapse build --discover`, and the factory learns a
   capability it did not have minutes earlier.

## Architecture

```
ui-next/       Primary mission-control UI — Next.js + React + TypeScript
               (org chart, job board, bid ticker, ledger + narration feeds,
               payroll dialog) — REST snapshots + SSE events. GSAP motion,
               Lottie badges, and a lightweight Canvas floor strip (no heavy
               3D). Run: cd ui-next && npm install && npm run dev (:3000).
ui/            Zero-dependency fallback of the same UI. Vanilla JS, no
               build step; Modern Web Guidance applied (native <dialog>,
               Baseline-safe CSS with fallbacks, ARIA live regions,
               reduced-motion support). Served by the API on :8000.
api/           FastAPI — REST state endpoints, SSE event bus, run/reset.
orchestrator/  Shift loop: Manager, bidding, worker execution, review,
               blind appeal. LLM narration via Groq is optional — the
               loop runs deterministically without a key.
economy/       Ledger, payroll/CFO, reputation — deterministic Python,
               stdlib only. Money math is code, never an LLM.
mcp_manager/   MCP client layer: spawns the targets' MCP servers over
               stdio, enforces the endpoint allowlist, classifies
               read/write tools for the confirmation gate.
targets/
  ticketdesk/  Target system #1 — FastAPI support-ticket API (:8101)
               + mcp_server.py (11 allowlisted tools)
  stockroom/   Target system #2 — FastAPI inventory API (:8102)
               + mcp_server.py (6 allowlisted tools)
```

**Invariants:** the ledger is append-only (enforced by SQLite triggers);
payment happens only on acceptance; a write tool call cannot execute without
a confirmation; fired agents cannot bid; reputation is bounded and derived
from recorded events.

## Quick start

Prerequisites: Python 3.11+. Node 20+ and a Groq API key are only needed to
regenerate the MCP servers with Synapse (see below).

```bash
# 1. Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: GROQ_API_KEY for LLM narration

# 2. Start the workplaces (the real systems agents will operate)
cd targets/ticketdesk && python3 seed.py && uvicorn app:app --port 8101 &
cd ../stockroom      && python3 seed.py && uvicorn app:app --port 8102 &
cd ../..

# 3. Start the factory (API + mission-control UI on the same origin)
uvicorn api.main:app --port 8000

# 4. Open http://localhost:8000, click "Run Shift", watch the floor work.
#    "Reset Demo" restores the exact demo-start state.
#    Primary UI (optional): cd ui-next && npm install && npm run dev
#    → http://localhost:3000 (same API, richer mission-control).
```

Headless check of the economy core:

```bash
python3 -m economy.test_core
```

## Regenerating the MCP servers with Synapse

The `mcp_server.py` files in each target follow the exact shape of Synapse's
generated output (one tool per allowlisted endpoint, read/write in the tool
names) so the factory runs out of the box. To regenerate them with Synapse
itself — the intended path, and how the demo's `--discover` finale works:

```bash
npm install -g @2ndbrainlabs-ai/synapse-cli
export GROQ_API_KEY=gsk_…
synapse model set groq
cd targets/ticketdesk
synapse build --local --auto --endpoints "GET /tickets,GET /tickets/{id},GET /tickets/duplicates,GET /sla/breaches,GET /stats/summary,POST /tickets,POST /tickets/{id}/assign,POST /tickets/{id}/priority,POST /tickets/{id}/comment,POST /tickets/{id}/status,POST /tickets/merge"
# Later, after adding an endpoint:
synapse build --discover
```

Exposure is deliberate: the allowlist is the safety boundary. Delete and
bulk-close endpoints are never turned into tools, so no agent can invoke
them — the capability does not exist on the Floor.

## Safety design

- **Writes are gated, reads are free.** Every write tool call needs a
  confirmation before dispatch; denials are returned to the worker as an
  observation it must adapt to.
- **Deterministic checks before LLM judgement.** Machine-checkable
  acceptance criteria ("zero unassigned tickets remain", "every breached
  ticket has an escalation comment") are verified in code before any
  Reviewer sees the work.
- **One human gate, at the end.** A person approves the results batch.
  Hiring, firing, payroll and appeals are autonomous — that is the point.

## Submission

- Hackathon write-up: [`docs/SUBMISSION.md`](docs/SUBMISSION.md) (also
  submitted via the Vibe-a-thon form)
- Demo script: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)
- Design docs: [`docs/BRIEF.md`](docs/BRIEF.md),
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md),
  [`docs/SYNAPSE_NOTES.md`](docs/SYNAPSE_NOTES.md),
  [`docs/IDEAS.md`](docs/IDEAS.md)

## License

MIT — see [`LICENSE`](LICENSE). Open source, built in the open for
Vibe-a-thon.

## Status

Built in November 2026 for Vibe-a-thon (submission deadline 25 Nov 2026).
Demo path: full shift loop — jobs → bids → award → MCP execution → review →
appeal → payroll/firing — against the live TicketDesk and StockRoom APIs.
