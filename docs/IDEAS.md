# THE FLOOR — Product Bible for Vibe-a-thon

**Event:** Vibe-a-thon (Geek Room × 2nd Brain Labs), online, $1,000 prize pool.
**Hard deadline:** Submission by **25 Nov 2026, 11:59 PM IST**. Today is 19 Nov. Six build days. No extensions, no excuses.
**Stack:** LangGraph + Groq for the agent workforce, Next.js for the org-chart UI, Synapse CLI as the factory's only hands.
**One-sentence pitch:** A software factory where AI agents are employees — they bid for work, get paid in compute credits, get reviewed, appeal bad reviews, and get fired by the CFO when they stop earning their keep — and the only way any of them can touch a real system is through a Synapse-generated MCP server.

---

## 1. Track recommendation: TRACK 4 (Open Innovation) — and how Synapse stays load-bearing

### The pick: Track 4. Not close.

**Why not Track 3:** Track 3's framing is "a copilot that answers questions needing both systems." Judges score it on *"whether answers combine both systems correctly."* THE FLOOR is not a Q&A copilot — it is an autonomous workforce that *does* work. Forcing it into Track 3 means the labour-market layer (bidding, payroll, firing — the entire original idea) reads as off-brief decoration, and we'd be graded on answer correctness, the one thing our demo doesn't centre on. We would be entering a knife fight with a orchestra.

**Why not Track 1:** Track 1 is one system, ≥3 tasks, judged on endpoint selection and task reliability. It's a fine brief and we'd satisfy it trivially — but the rubric has no room for a second system joining mid-demo, a reviewer appeals court, or a CFO. Everything that makes THE FLOOR unforgettable would be unscored extra. Also, Track 1 says "no changes to the original app's code" — our finale *adds an endpoint* to a codebase live, which is literally Track 3's signature move and would be a rule smell in Track 1.

**Why Track 4 wins:** Track 4 is judged on exactly four things — **originality, real-world value, how central Synapse is to the solution, technical execution, demo quality.** THE FLOOR maxes originality (nobody else will submit a labour market), and the guide's own Track 4 starting points include *"an agent that triages bugs using your team's issue tracker and codebase"* — our Manager does that as its day job. Best of all, Track 4 lets us **steal the other tracks' proof points without being graded on their rubrics**: we will still complete ≥3 real multi-step tasks through one system (Track 1's bar) and still do the live add-endpoint → `synapse build --discover` → agent uses it immediately moment (Track 3's bar). We present both as evidence inside an open-innovation entry. Judges get three tracks' worth of proof in one demo.

### How Synapse is load-bearing (this is the section judges will probe — it must be airtight)

Synapse is not "how we connected the demo app." Synapse is the factory's **only pair of hands**, in four concrete ways:

1. **Workers can only act through Synapse-generated MCP tools.** No worker ever gets a database handle, an HTTP client, or a shell. The LangGraph workers' tool list *is* the tool list of the Synapse-generated MCP server(s), loaded at runtime. If Synapse hasn't built it, the factory cannot touch it. Remove Synapse and the factory is a chatroom of unemployed agents — that is the definition of load-bearing.

2. **Onboarding a workplace = running `synapse build`.** The factory's "client onboarding" flow is literally: point Synapse at a legacy codebase (Auto mode), pick endpoints, get an MCP server. The Manager then reads that server's tool list to learn *what kinds of jobs can even exist* — job templates are derived from available tools, not hardcoded. A new capability in the target system automatically becomes a new possible job type.

3. **The finale is a Synapse command, not a code change in our system.** Mid-demo, a job appears that no current tool can complete. The presenter adds one endpoint to the target codebase and runs `synapse build --discover`. Synapse rescans (only changed files are parsed), the MCP server gains a tool, our tool registry hot-refreshes, the Manager re-posts the impossible job, and a worker completes it — all without restarting the factory. This is Track 3's prescribed live moment, transplanted.

4. **Tool quality is a judging lever we exploit deliberately.** We use `--smart-names` on the Auto build so tools get clear names/descriptions — the guide itself notes agents pick the right tool more often with good names, and endpoint selection "counts in judging." In the write-up we state which endpoints we exposed and which we deliberately did *not* (e.g. no delete endpoints exposed to workers — see the safety note in §2).

### What the submission must contain (Track 4, per the guide)

- [ ] **The repo** — factory code (LangGraph workforce + Next.js UI), both demo target apps, seed data, and a README with exact run instructions.
- [ ] **The MCP setup** — the generated MCP server files (`synapse_auto_server.py` from our `--local` Python builds), the MCP client config snippets Synapse printed, and the exact `synapse build` commands used per system, documented so a judge can reproduce them.
- [ ] **A short write-up** — the problem (legacy systems are unusable by agents; agent demos have no accountability) and why Synapse fits (it makes any existing codebase agent-operable in minutes, which is what makes a *general* agent workforce possible — the factory is only interesting because the workplace can be *any* legacy system Synapse can scan).
- [ ] **A demo video** of the agent system solving the problem end to end (script in §4).
- [ ] Submitted via the event form before **25 Nov 2026, 11:59 PM IST**. Build freeze: **24 Nov, 20:00 IST**. The last day is for video + form + buffer only.

---

## 2. Mechanics, tightened for a six-day build

Design rule: every mechanic must produce a **visible event on the org chart** and a **number that changes**. If a mechanic can't be seen, it's cut.

### The cast (7 agents, no more)

| Agent | Model tier | Job |
|---|---|---|
| **Manager** | Strong Groq model | Scans the workplace backlog via MCP read tools, posts jobs, runs the auction, assigns work |
| **Worker × 4** | Mixed on purpose: 2 strong, 1 mid, 1 cheap/weak | Bid, execute jobs through MCP tools, appeal rejections |
| **Reviewer A** | Strong | Audits every completed job, issues P0–P3 verdict |
| **Reviewer B** | Strong, different prompt/persona | Blind appeals court — never sees A's verdict or the worker's name |
| **CFO** | Mostly deterministic code + one LLM summary line | Runs payroll, fires, hires mutated replacements |

The mixed worker tiers are not an accident — they are the demo. A uniform workforce never gives the CFO anything to do.

### Currency and cost

- Unit: **credits**. Every worker LLM call and tool call is metered; a worker's *cost* on a job = actual Groq tokens consumed × a fixed credit rate (display real token counts in the UI tooltip — judges love real numbers).
- Each job has a **budget cap** set by the Manager from job type (e.g. triage job: 120 credits; resolution job: 300 credits).
- Workers start with a **balance of 0** and a **per-cycle upkeep** (their "salary": strong = 90 credits/cycle, mid = 55, cheap = 30 — strong models must earn their expensive keep).

### Bidding (one sealed round — that is the whole auction)

1. Manager posts a job: spec, budget cap, required tools, acceptance criteria.
2. Every available worker returns one sealed bid: `{price, confidence (0–100), one-line plan}`. Workers see the job and their own history, not each other's bids.
3. Manager's award score, shown live in the UI: **score = 0.5 × (1 − price/cap) + 0.3 × (reputation/100) + 0.2 × (confidence/100)**. Highest score wins. The formula is deliberately simple, visible, and defensible — judges can follow it in real time.
4. Winning bid's price goes into **escrow** from the job budget. Losing bidders get nothing and pay nothing.

### Execution

- The winning worker executes through MCP tools only, step by step, with every tool call streamed to the UI (tool name, args summary, result status).
- **Deterministic verification runs before the Reviewer ever sees the work**: scripted checks against the target system via MCP read tools (did the ticket's status actually change? is the stock figure actually updated? does the canonical update exist?). A failed deterministic check = automatic P1, no LLM opinion needed. This is what makes the demo reliable instead of vibes-based.
- **Safety gate (borrowed from Track 2's rule, stated proudly in the write-up):** any data-destroying action class (deletes, bulk closes) is simply **not exposed** in the Synapse endpoint selection. Workers *cannot* call what doesn't exist. The one human gate in the whole system: the presenter approves the final results batch at the end of the demo ("ship it").

### Review and appeal

- Reviewer A gets: job spec, acceptance criteria, deterministic check results, the worker's tool-call transcript. Verdict: **P0/P1 = reject, P2 = pass with warnings, P3 = clean pass**, plus a two-line rationale.
- **Pass** → escrow releases to the worker's balance; worker reputation **+4** (P3: +6).
- **Reject** → escrow returns to the factory; worker paid **0**; reputation **−8**.
- **Appeal:** a rejected worker may appeal once, costing 15 credits from its balance (skin in the game — prevents appeal spam and creates balance drama). Reviewer B receives the job spec and the work product **only** — not A's verdict, not the worker's identity, not the bid. B's verdict is final:
  - **Overturn** → worker gets paid in full, reputation +6; **Reviewer A's reputation drops −10** and A gets a visible "overruled" mark. Reviewers have reputations too — nobody is above the Floor.
  - **Upheld** → worker loses the 15-credit appeal fee and another −4 reputation.

### Payroll, firing, mutation (the signature loop)

- A **payroll cycle** = every 6 completed jobs, or the presenter pressing "End of Day." The CFO computes per worker: `net = earnings this cycle − (tokens consumed this cycle + upkeep)`.
- **Two consecutive cycles with net < 0 → FIRED.** The worker's card on the org chart greys out, a pink-slip event fires in the feed, its balance is zeroed, and it is removed from the bidding pool. No sentimentality. This is the moment the audience remembers.
- **Replacement hire:** the CFO spawns a mutated variant of the fired worker — exactly **one trait mutated** from a fixed mutation menu: (a) model tier swap, (b) system-prompt clause added/removed (e.g. "verify before acting" / "be terse"), (c) temperature shift, (d) tool-style directive (plan-first vs act-first). The replacement starts at reputation 50, balance 0, and is displayed as a lineage: *"Ravi → Ravi 2.0 (mutation: +verify-before-acting)"*. The workforce visibly evolves within a single demo run.
- Reviewer A is not fireable in the six-day version (the CFO only manages workers) — but A's reputation *can* crater via appeals, and the UI shows it. Cut-list insurance, see below.

### State and plumbing (keep it boring)

- Single-process LangGraph graph with a shared state object; persistence = one SQLite file (agents, jobs, bids, ledger, reputations, lineage). Ledger is append-only — every credit movement is a row. The UI reads state over a simple API/SSE feed from the Next.js app.
- MCP integration: the LangGraph workers load tools from the Synapse-generated server at runtime (MCP client over stdio for the `--local` Python server file). The tool registry is a hot-swappable list — after a `--discover` rebuild, the factory re-lists tools from the server and the new tool appears without a factory restart. **Build and test this refresh path on Day 1**; the finale depends on it.
- Demo mode: a seeded reset script restores the target apps' databases and the factory ledger to the exact demo-start state. One button. Rehearse with it.

### Cut list — in the order things die if time runs out

1. **Negotiated/multi-round bidding** — already cut. One sealed round, forever.
2. **Worker subcontracting / teaming** — cut. Workers are solo.
3. **Cross-run persistent memory** — cut. One run, one SQLite file, seeded reset.
4. **Real GitHub PR flow for worker output** — cut. Workers act on the demo systems through MCP; that *is* the work. (The Infer-a-Thon version can add PRs; Vibe-a-thon judges score Synapse centrality, not GitHub.)
5. **Reviewer firing** — cut (above). Reviewer reputation display stays; it's cheap and it's the appeal payoff.
6. **Org-chart animation polish** — cut to a clean live grid + event feed. Legibility beats flair.
7. **Second target system fully integrated from the start** — it joins *only* in the finale (§3). If the finale's live build wobbles in rehearsal, the fallback is a pre-built second server connected live on camera — still a real Synapse artefact, zero terminal risk.
8. **CFO as an LLM agent** — already mostly code. If needed, CFO becomes 100% deterministic with templated announcements. The firing must never depend on an LLM being in a good mood.

### Six-day build order (sketch)

- **Day 1 (19–20 Nov):** Synapse proof — install CLI, `--local` build with Groq on the ticket app, MCP tool list loading into a bare LangGraph agent, **tool-refresh-after-`--discover` test**. Get a hosted Synapse API key as insurance. This day decides whether the finale is real.
- **Day 2:** Factory core — Manager, job posting from backlog scan, sealed bidding, escrow ledger, worker execution loop.
- **Day 3:** Reviewer A, deterministic checks, appeal + Reviewer B, reputation updates.
- **Day 4:** CFO payroll/firing/mutation, org-chart UI (grid, balances, event feed, tool-call stream).
- **Day 5:** Finale integration (second system + live endpoint + `--discover`), seeded demo state, reset button, full rehearsal ×3.
- **Day 6 (24 Nov):** Freeze at 20:00. Record video, write-up, submission form. Buffer day is not a build day.

---

## 3. The demo target systems

Both targets are **small Python/FastAPI backends** — this is forced by Synapse, not taste: `--local` mode only writes a generated server file for **Python** projects, and plain JavaScript isn't scanned at all. Both apps stay tiny (well under 5k lines combined) so indexing is fast and quota is a non-issue. Both are seeded with realistic data and a reset script. Neither app's code is modified by the factory — workers only ever call its HTTP API through MCP tools. (We modify one app exactly once, live, in the finale — by adding an endpoint as its "developer," which is precisely the workflow Synapse is built for.)

### Primary workplace: **HelpDesk** — a legacy support-ticket backend

The natural home for THE FLOOR: a backlog *is* a job board. The Manager reads it the way a floor manager reads a ticket queue.

- **Endpoints exposed via Synapse (Auto, `--smart-names`):** list tickets (filter by status/priority/assignee), get ticket, search tickets, add comment, set priority, set status, assign ticket, get customer, list customers. **Deliberately NOT exposed:** delete ticket, bulk-close, anything destructive — stated in the write-up as the factory's safety model.
- **Seeded state:** ~40 tickets with planted patterns — an SLA-breach cluster, a set of duplicates about one outage, uncategorised tickets, one angry VIP customer.
- **Jobs the Manager posts on it:**

| Job | What the worker must do (multi-step, MCP only) |
|---|---|
| **J1 — SLA breach sweep** | List open tickets → identify those breaching SLA within 4 hours → raise priority → reassign to the right queue → post an internal comment on each explaining the action |
| **J2 — Duplicate collapse** | Search tickets for the shared outage → identify the duplicate set → pick the canonical ticket → comment on each duplicate linking the canonical one → set duplicates to "linked" status |
| **J3 — Backlog triage** | List uncategorised tickets → read each → set category + priority → assign to the correct queue (this is the guide's own Track 4 example, industrialised) |
| **J4 — VIP save** *(finale job, cross-system)* | A VIP customer's replacement device must be confirmed against AssetTrack stock **and** warranty status before a promise is made → check stock → check warranty (needs the finale endpoint) → update the ticket with a correct, evidence-backed commitment |

J1–J3 alone satisfy Track 1's "≥3 real multi-step tasks" bar inside our Track 4 entry. Script the demo so at least one J1/J2 job gets **rejected** (seed the weak worker's likely failure — e.g. it comments but forgets to reassign, failing a deterministic check) to set up the appeal beat. Do not fake the rejection with a rigged prompt; seed the *task* so the cheap model plausibly fails it, and rehearse until the failure is reliable. If it passes in a live run, the Manager's next job carries the appeal beat instead — the script has two rejection slots.

### Second system: **AssetTrack** — a small inventory/asset backend

- **Endpoints initially exposed:** list assets, get asset, check stock by SKU. Its MCP server is built (Auto, `--local`) but the factory's Manager treats AssetTrack jobs as out of scope at demo start — its tools sit visibly "locked" in the UI's toolbelt panel.
- **The finale:** J4 arrives needing a warranty lookup that **does not exist** in AssetTrack. The presenter, playing AssetTrack's developer, adds `GET /assets/{serial}/warranty` to the FastAPI app, runs **`synapse build --discover`**, the MCP server gains the tool, the factory's registry refreshes, the toolbelt unlocks, the Manager re-posts J4, and a worker completes it. One terminal command on camera; the whole room sees the factory *learn a new capability* without a restart.

---

## 4. Demo script (video ≈ 3.5–4 min; live judging follows the same beats)

Narrative rule: the audience should be able to retell this as a story about *employees*, not about prompts. Every beat names the agent like a person and shows a number changing.

| Time | Beat | What's on screen |
|---|---|---|
| 0:00 | **Cold open** | "This support company has zero human employees." The org chart: Manager, 4 workers (with model tiers and upkeep costs shown), Reviewer, CFO. Balances: all zero. |
| 0:20 | **The workplace (Synapse proof #1)** | 20-second terminal flashback: `synapse build` run on the HelpDesk codebase → MCP server generated → tool list appears in the factory's toolbelt panel. Voiceover: "We didn't integrate this legacy app. Synapse turned it into tools. It's the only way our agents can touch it." |
| 0:40 | **Jobs drop** | Manager scans the HelpDesk backlog via MCP, posts J1–J3 with budget caps. Job cards hit the board. |
| 0:55 | **The auction** | Sealed bids fly in from all 4 workers — price, confidence, one-line plan. Award scores compute live with the visible formula. The cheap worker underbids everyone on J2. |
| 1:15 | **Work happens** | Workers execute; tool calls stream (real MCP calls, real ticket data changing — show the HelpDesk ticket list updating in a side panel). Two jobs pass review, escrow releases, balances and reputations tick up. |
| 1:45 | **⚡ GASP 1 — The appeal** | The cheap worker's J2 is **rejected P1** (deterministic check: duplicates never got linked). Unpaid. It **appeals** — 15 credits deducted. Reviewer B's blind review runs… **OVERTURNED** (B finds the linking comment present but the status set on the wrong field — a spec ambiguity, ruled in the worker's favour) — worker paid in full, and **Reviewer A's reputation drops −10 on the org chart**. The judge of judges just got judged. *(If rehearsal shows the natural failure lands differently, swap: B upholds, worker loses the fee — still a story. The overturn is the stronger beat; engineer the seed toward it.)* |
| 2:15 | **⚡ GASP 2 — The firing** | "End of Day." CFO runs payroll: earnings vs token cost + upkeep, per worker, live ledger. The mid-tier worker posts its **second consecutive negative cycle** → **FIRED**. Card greys out, pink-slip event in the feed, balance zeroed. A replacement fades in: **"Dev 2.0 — mutation: verify-before-acting"**, reputation 50, already bidding on the next job. This is the screenshot moment. This is why the product is called THE FLOOR. |
| 2:45 | **⚡ GASP 3 — The factory learns (Synapse proof #2)** | J4 lands: VIP replacement — needs AssetTrack warranty data. Manager flags it **UNSTAFFABLE: no tool exists**. Presenter switches to the AssetTrack codebase, adds the warranty endpoint, runs `synapse build --discover` in the terminal. Toolbelt panel: new tool lights up. Manager re-posts J4; Dev 2.0 — the mutated replacement, in its first job — wins the bid and completes it. The new hire justifying its existence with a capability the factory didn't have three minutes ago. |
| 3:20 | **The only human gate** | Presenter reviews the results batch — tickets resolved, duplicates collapsed, VIP answered — and clicks **Approve**. Cost summary card: total credits spent vs the estimated cost of a human support shift. |
| 3:35 | **Close** | Org chart, end of day 2: balances, reputations, one pink slip, one new hire. Tagline on screen. "Every agent has a price. Every price has a consequence." |

**Live-judging notes:** run the same script live if asked; the seeded reset button restores the exact start state in seconds. Keep a pre-recorded run as the fallback for any live failure — no debate, just play it.

---

## 5. Name + tagline

**THE FLOOR** is a genuinely good working name — it's the factory floor, the trading floor (bidding, escrow, payroll), and the minimum standard ("the floor" you must earn above to survive). Alternatives, honestly assessed:

| Name | Tagline | Verdict |
|---|---|---|
| **THE FLOOR** | "Every agent has a price. Every price has a consequence." | **Recommended.** Triple meaning, sounds like a place, survives the demo. |
| PinkSlip | "Your agents' performance review is today." | Funniest name in the set, but it front-loads the firing joke and undersells bidding/review/appeals. Great *feature* name (the firing event is "a PinkSlip"), weak product name. |
| HEADCOUNT | "An org chart that edits itself." | Strong, corporate, memorable. Second choice. Loses the market/factory double meaning. |
| OrgForge | "We forge orgs, not chatbots." | Clear but generic — sounds like an HR SaaS from 2019. |
| The Assembly | "Agents bid. Agents build. Agents get fired." | Decent rhythm, but "Assembly" reads as a community/meetup product. |
| Staffing.exe | "Now hiring. Now firing." | Meme energy; judges at an enterprise-flavoured event (2nd Brain Labs sells to enterprises) may not reward it. |

**Recommendation: ship "THE FLOOR"** with the tagline **"Every agent has a price. Every price has a consequence."** Use "PinkSlip" as the in-product name for the firing event — the UI feed literally prints `PinkSlip issued: Dev (2 negative cycles)`. Two memorable words for the price of one.

---

## 6. Event-specific risks + mitigations

| Risk | Why it's real (from the guide) | Mitigation |
|---|---|---|
| **Synapse quota burn** | Free tier: **10 MCP servers, 100,000 indexed lines** per account. Hosted builds count; sloppy experimentation across two codebases + rebuilds could eat servers. | Default to **`--local` builds with Groq — they are never counted** and need no Synapse account. Keep both target apps tiny (<5k lines total). Run `synapse info` before any hosted build. Budget: at most 2 hosted servers ever, only as insurance. |
| **`--local` code generation fails** | Guide, verbatim warning: *"Small local models often fail"* — error `returned no emit_tool_plan call` means the model can't follow the strict schema. | Use Groq's **largest** available model for the Synapse build step (`synapse model set groq` + strong model id), never the small/fast one. The *workers* can run smaller models; the *build* cannot. Test the full build on Day 1, not Day 5. |
| **Local-mode language trap** | *"Only Python projects get a generated file"* in local mode; on TypeScript/Java/etc. local Auto "can name the tools but writes no file." Plain JavaScript is not scanned at all. | Both target apps are **Python/FastAPI**, non-negotiable. Next.js is used *only* for our own UI, which Synapse never scans. |
| **Hosted fallback needs a key we don't have yet** | Hosted builds need a Synapse console API key + `synapse init`. | **Day 1 task:** create the Synapse account and key as insurance, even if local works. If local generation fails on demo day, hosted is a 10-minute pivot, not a crisis. |
| **Tool list doesn't refresh after `--discover`** | MCP clients typically load tools at connect time; the guide's client instructions assume a restart ("restart the client"). Our finale needs the new tool *without* restarting the factory. | Build the tool registry as a re-listable MCP session and **prove the refresh on Day 1** with a toy endpoint. If stdio re-listing misbehaves, the fallback is a scripted MCP-server subprocess restart inside the factory (invisible to the audience, still honest — the factory re-connects to the rebuilt server). Rehearse whichever path survives Day 1. |
| **Reviewer flakiness kills the demo story** | An LLM judge can pass what should fail (or vice versa) on the day. | Deterministic checks gate first (status fields, links, stock numbers — code, not opinion). The Reviewer only judges what code can't. Seed tasks so the cheap worker's failure mode is a *deterministic* miss. Two rejection slots in the script. Pre-recorded backup run. |
| **Groq rate limits mid-demo** | 7 agents × multi-step jobs × live audience = bursty calls. | Meter everything (we already do — it's the product). Cap tool steps per job. Keep worker prompts tight. Run the full demo twice in rehearsal on the same account to surface limits *before* judges do. |
| **Demo state drift between rehearsals** | Tickets get resolved, balances move, workers get fired — run 2 starts from run 1's ashes. | Seeded reset script for both app databases + the factory SQLite. One button, tested. Reset is part of the rehearsal loop, not an afterthought. |
| **Scope creep toward the Infer-a-Thon version** | THE FLOOR's full vision (GitHub PRs, SIE, weeks of payroll history) belongs to a bigger build. | The cut list in §2 is law. If it isn't needed for the 4-minute story, it doesn't exist this week. Freeze 24 Nov 20:00; Day 6 is video + write-up + form only. |
| **Deadline mechanics** | Submission is a form + repo + video by **25 Nov 23:59 IST**; a perfect build submitted late scores zero. | Video recorded from the *rehearsed* build on Day 5 evening if Day 6 gets tight — a good video of a working system beats a live-only system with a rushed upload. Submit the form by 24 Nov night if the form allows it; treat 25 Nov as buffer, never as a workday. |

---

## Appendix — the one-paragraph write-up draft (for the submission)

*Companies run on legacy systems no agent can operate, and agent demos have no accountability — nobody bids, nobody is reviewed, nobody is fired. THE FLOOR is a software factory where AI agents are employees: a Manager posts jobs from a real support backlog, workers bid in compute credits, a Reviewer audits every job with P0–P3 severity, workers can appeal to a blind second Reviewer, and a CFO fires agents who stop covering their cost, replacing them with mutated variants. The factory can work on any legacy system because Synapse turns that system's codebase into an MCP server in minutes — our agents hold no database handles and no HTTP clients; the Synapse-generated tools are their only hands, and when the factory needs a capability that doesn't exist, one new endpoint and `synapse build --discover` teach it live. Synapse is what makes the workforce general; the Floor is what makes it accountable.*
