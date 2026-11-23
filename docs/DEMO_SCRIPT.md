# THE FLOOR — Demo Video Script (≈3.5–4 minutes)

**Format:** screen recording of the mission-control UI, with terminal cutaways. One presenter, voiceover throughout.
**Narrative rule:** the audience should be able to retell this as a story about *employees*, not about prompts. Every beat names the agent like a person and shows a number changing.
**Before recording:** run the reset so the factory is in the exact seeded start state; TicketDesk running on :8101; StockRoom code open in an editor tab; a terminal open in the StockRoom directory. Record one full backup take before polishing anything.

---

## Beat 1 — Cold open: zero human employees (0:00–0:20)

- **On screen:** the mission control, still. Org chart: Manager, 4 workers (model tiers and upkeep costs visible on their cards), Reviewer, CFO. Every balance reads ₡0. The job board is empty.
- **Voiceover:** "This support company has zero human employees. This is its entire staff — a manager, four workers, a reviewer, and a CFO. All of them are AI agents. And every one of them can be fired."
- **Presenter action:** slow pan across the org chart; hover a worker card so the tier, model, and upkeep show.

## Beat 2 — Synapse flashback: how the workplace was built (0:20–0:40)

- **On screen:** terminal flashback (pre-recorded clip is fine): `synapse build --local --auto` running against the TicketDesk codebase → the MCP server file generated → the tool list appearing in the factory.
- **Voiceover:** "We didn't integrate this legacy helpdesk app. Synapse read its codebase and turned it into tools. Those tools are the only hands our agents have — no database access, no HTTP client, nothing else. And notice what is *not* in the tool list: there is no delete tool. Exposure is a safety decision, and we made it at build time."
- **Presenter action:** cut back to the live UI; point at the ticket list in TicketDesk (the real, messy backlog: duplicates, breaches, unassigned P1s).

## Beat 3 — Jobs drop and the sealed-bid auction (0:40–1:15)

- **On screen:** the Manager scans the backlog and posts J1 (SLA breach sweep), J2 (duplicate collapse), J3 (backlog triage) with budget caps. Job cards hit the board. Sealed bids fly in from all four workers — price, confidence, one-line plan — scrolling across the bid ticker. Award scores compute live under the visible formula: `0.5·(1 − price/cap) + 0.3·(reputation/100) + 0.2·(confidence/100)`.
- **Voiceover:** "Work arrives as jobs, and nobody is simply assigned. Every worker bids — a price and a confidence — and the award formula is on screen, not in a prompt. Watch the cheapest worker underbid everyone on the duplicate job. Remember that bid."
- **Presenter action:** click **Run Shift** (if not already running); let the ticker and bid stacks fill before moving on. Pause two seconds on the award score breakdown.

## Beat 4 — Work happens, through real MCP calls (1:15–1:45)

- **On screen:** workers execute. Tool calls stream in the narration log; the TicketDesk ticket list updates in a side view as assignments, priorities, and comments land. A write action pauses at the confirmation gate and is approved. Two jobs pass review; escrow releases; balances and reputations tick up on the org chart.
- **Voiceover:** "Every action you see is a real MCP tool call against the real helpdesk — reads are free, writes pass a confirmation gate. Two jobs pass review, and the ledger pays out. Money on this floor is code, not vibes: the ledger is append-only, and every credit is accounted for."
- **Presenter action:** approve the confirmation prompt when it appears — do not rush it; the gate is a feature, show it.

## Beat 5 — GASP 1: the appeal overturns the Reviewer (1:45–2:15)

- **On screen:** the cheap worker's J2 is **rejected, P1** — the deterministic check fires first (duplicates never got linked). No payment. The worker **appeals**: 15 credits deducted from its balance, shown live. The blind second Reviewer runs on the spec and the work product alone. **OVERTURNED** — the worker is paid in full, and **Reviewer A's reputation drops −10** on the org chart.
- **Voiceover:** "The cheap worker's job is rejected — a deterministic check caught it before any reviewer opinion. Unpaid, it does something employees do: it appeals. That costs fifteen credits, win or lose. The second reviewer sees the work, not the first verdict… and overturns it. The worker is paid in full — and the first reviewer's reputation takes the hit. On this floor, even the judges get judged."
- **Presenter action:** keep the org chart in frame for the reputation drop; that number changing is the beat.
- **Fallback:** if the natural failure in a given run lands differently and the appeal is *upheld* instead, narrate that: the worker loses the fee and reputation — still a story, same point about consequences. The overturn is the stronger beat; the seed is engineered toward it, but never fake the outcome on camera.

## Beat 6 — GASP 2: payroll, a firing, and a mutated hire (2:15–2:45)

- **On screen:** "End of day." The payroll banner fires; the payroll table counts through each worker — earnings vs token cost + upkeep. The mid-tier worker posts its **second consecutive negative cycle** → **FIRED**: the card shakes, stamps TERMINATED, and slides to the Graveyard; a PinkSlip lands in the feed. A replacement fades in at the top of the org chart: **"Dev 2.0 — mutation: verify-before-acting"**, reputation 50 — and it is already bidding on the next job.
- **Voiceover:** "End of day. The CFO runs payroll — earnings against cost, per worker, in the open. Two negative cycles in a row, and the rule is the rule: fired. And the floor does not stay short-staffed. Its replacement is a mutated variant of the worker it lost — same playbook, one trait changed: verify before acting. This is why the product is called THE FLOOR."
- **Presenter action:** let the firing animation and the new-hire pulse finish before speaking over them. This is the screenshot moment — hold the frame.

## Beat 7 — GASP 3: the factory learns a new capability live (2:45–3:20)

- **On screen:** J4 lands — a VIP save that needs warranty data from the second system, StockRoom. The Manager flags it **UNSTAFFABLE: no tool exists**. The presenter switches to the StockRoom codebase, adds the warranty endpoint (`GET /assets/{serial}/warranty`) live, and runs `synapse build --discover` in the terminal. Back in the UI, the new tool lights up in the registry. The Manager re-posts J4; **Dev 2.0 — the mutated replacement, in its first job — wins the bid and completes it**, cross-checking the warranty through the brand-new tool.
- **Voiceover:** "One last job — and the factory cannot staff it. The capability does not exist. So we teach it, live: one new endpoint in the second codebase, one command — `synapse build --discover` — and the factory has a new hand. And who picks up the job? The replacement. Hired ninety seconds ago, already justifying its existence with a capability this factory did not have three minutes ago."
- **Presenter action:** type/paste the pre-written endpoint snippet (do not hand-type code live), run the discover command, wait for the tool to appear before re-posting J4.
- **Fallbacks:** if `--discover` is slow, cut the terminal wait in editing (the recorded take uses the genuine live path). If it fails outright on recording day, ship StockRoom pre-onboarded, show the tool registry already containing the warranty tool, and narrate the onboarding as the flashback in Beat 2 — never claim a live run that did not happen.

## Beat 8 — The only human gate, and the cost summary (3:20–3:40)

- **On screen:** the results batch — tickets resolved, duplicates collapsed, the VIP answered. The presenter clicks **Approve**. A cost summary card: total credits spent this shift vs the estimated cost of a human support shift covering the same backlog.
- **Voiceover:** "Everything until now was autonomous — hiring, bidding, reviewing, appealing, firing. The one thing the floor never does alone is close the batch. A human approves the results. Total cost of this shift: on screen — against the cost of a human support shift doing the same work."
- **Presenter action:** click Approve deliberately, on camera. Let the cost card sit for three full seconds.

## Close (3:40–3:55)

- **On screen:** the org chart, end of day two: balances, reputations, one card in the Graveyard, one new hire mid-work. Tagline full-screen.
- **Voiceover:** "Every agent has a price. Every price has a consequence. This is THE FLOOR."

---

## Fallback notes (recording day)

- **Pre-recorded run is the insurance policy.** Record one clean full take first. If a live take later fails (network, rate limits, a stuck tool call), publish the clean take — no debate, no heroics.
- **Reset is one click.** The Reset Demo button restores the exact seeded start state; TicketDesk also has `python3 reset.py` / `POST /admin/reset`. Between takes, reset and re-check balances (₡0) and the ticket count before rolling.
- **Pacing beats:** the three moments that must not be rushed are the confirmation-gate approval (Beat 4), the Reviewer reputation drop (Beat 5), and the firing → new-hire animation (Beat 6). If the run is long, trim Beat 4's tool-call stream, never the gasps.
- **If a beat does not land:** no rejection in the run → lean on the seeded weak worker's deterministic miss (Beat 5's check failure); if there is genuinely no appeal, extend Beat 6's payroll narration and move the appeal explanation into the Beat 5 slot over the review panel. Do not script or fake an outcome the system did not produce.
- **Live judging:** the same script runs live on request; keep the recorded video ready to play the moment anything in the live path stalls.
