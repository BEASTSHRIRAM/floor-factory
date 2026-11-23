# THE FLOOR — Project Brief (synthesis, 19 Nov 2026)

**Event:** Vibe-a-thon (Geek Room × 2nd Brain Labs) · **Deadline: Wed 25 Nov 2026, 11:59 PM IST** · Submission target: 25 Nov, 17:00 IST.
**Source docs:** IDEAS.md (product bible) · ARCHITECTURE.md (build plan) · SYNAPSE_NOTES.md (verified Synapse research) — all in this folder.

## The product

A software factory where AI agents are employees. A Manager posts jobs from a real support backlog with credit budgets → 4 workers (mixed model tiers on purpose) place sealed bids (price + confidence) → Manager awards by a visible formula → the winner does the work **only through Synapse-generated MCP tools** → a Reviewer audits with P0–P3 severity → rejected workers can appeal to a blind second Reviewer (overturn = Reviewer A's reputation drops) → a mostly-deterministic CFO runs payroll, **fires** workers with 2 consecutive negative cycles, and hires **mutated replacements** (lineage shown: "Ravi 2.0 — mutation: verify-before-acting"). Only human gate: final approval.

Tagline: **"Every agent has a price. Every price has a consequence."** The firing event is called a **PinkSlip** in the UI feed.

## Locked decisions

- **Track 4 (Open Innovation).** Judged on originality, real-world value, Synapse centrality, execution, demo. We still satisfy Track 1's bar (≥3 multi-step tasks, one system) and steal Track 3's live `--discover` moment as evidence — without being graded on their rubrics.
- **Synapse is the factory's only hands, in 4 ways:** (1) workers hold no DB handle/HTTP client/shell — their tool list IS the Synapse MCP server's tool list; (2) onboarding a workplace = running `synapse build`, and job types derive from available tools; (3) the finale is a Synapse command — add one endpoint, `synapse build --discover`, tool registry hot-refreshes, the impossible job gets done; (4) endpoint exposure is deliberate (no delete/bulk-close endpoints exposed — the safety story), `--smart-names` where useful.
- **Build mode: `--local` with Groq is primary** (never counted against quota, no Synapse account needed, generates a real Python server file). One hosted Auto build of the primary target as a hot spare (needs Sriram's free Synapse console API key — Day 1 insurance task).
- **Targets are Python/FastAPI, non-negotiable** (local mode only writes server files for Python; plain JS is never scanned). Next.js is only our own UI.
  - **HelpDesk/TicketDesk** (primary): support-ticket API, ~40 seeded messy tickets. Jobs: J1 SLA breach sweep, J2 duplicate collapse, J3 backlog triage, J4 VIP save (finale, cross-system).
  - **AssetTrack/StockRoom** (second): small inventory API, joins in the finale — presenter adds `GET /assets/{serial}/warranty` live, runs `--discover`, the factory learns the new capability.
- **Money math is code, not LLM.** Ledger is append-only SQLite; deterministic verification checks run before the LLM Reviewer ever sees work (a failed check = automatic P1). Award formula visible in UI: score = 0.5·(1 − price/cap) + 0.3·(reputation/100) + 0.2·(confidence/100).
- **Safety gate:** destructive action classes are never exposed as tools; writes pass a confirmation gate. Human gate = final results approval only.
- **Demo determinism:** seed the weak worker's likely failure (a deterministic miss, not a rigged prompt); two rejection slots in the script; seeded one-button reset restores exact demo-start state; pre-recorded run as fallback.

## Demo beats (video ≈ 3.5–4 min)

Cold open (zero human employees) → Synapse flashback (build on HelpDesk) → jobs drop → sealed-bid auction → work streams via real MCP calls → **GASP 1: appeal overturned, Reviewer A −10 rep** → **GASP 2: CFO fires the negative-cycle worker, mutated replacement hired and bids** → **GASP 3: `--discover` teaches the factory warranty lookup; the new hire completes the impossible job** → human approves the batch → cost summary vs a human support shift.

## Timeline (from ARCHITECTURE.md §8)

- **Day 0 — Thu 19 Nov:** Synapse smoke test (THE gate) + TicketDesk skeleton + repo scaffold.
- **Day 1 — Fri 20 Nov:** economy/ledger + MCP manager + one worker end-to-end, headless. Hosted spare build.
- **Day 2 — Sat 21 Nov:** market loop — Manager, bidding, Reviewer, payment. All job families.
- **Day 3 — Sun 22 Nov:** appeal + CFO/firing/mutation + Custom composed tool + UI v1 on live SSE.
- **Day 4 — Mon 23 Nov:** second system + `--discover` set piece + UI polish. **Demo script locked EOD.**
- **Day 5 — Tue 24 Nov:** hardening, 3 dry runs, **record demo video**. **Feature freeze 18:00** (IDEAS says 20:00 — earlier wins).
- **Day 6 — Wed 25 Nov:** clean-clone verification, **submit by 17:00**, buffer only.

## Cut order (pre-agreed, from the top)

Appeal flow → mutation lineage → live `--discover` (ship pre-onboarded) → Custom composed tool → UI theatre → backlog-scan intake → multi-cycle payroll. **Never cut:** confirmation gate, ledger, real MCP execution (no faked tool results — the core claim dies).

## Open items / asks

- **Sriram (2 min, Day 1 insurance):** create a free Synapse account at synapse.2ndbrainlabs.ai and generate an API key (Console → API Keys → Create — shown only once) so we can build the hosted hot spare. NOT a blocker for Day 0 — the `--local` path needs no account.
- **Day 0 gate risk:** local Auto behaviour conflicts between Synapse docs and README — the smoke test settles it empirically. If local codegen fails (`emit_tool_plan`), primary flips to hosted the same day; architecture unchanged.
