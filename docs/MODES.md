# THE FLOOR — Manual / Auto mode

The floor has one trust dial: **mode**. It is held server-side
(`orchestrator/mode.py`, owned by the API process), defaults to **manual**,
and is readable/settable over the API (`GET`/`POST /mode`). Every change
emits a `mode.changed` event (`{mode, previous_mode, by}`).

## What the mode changes — and what it never changes

The mode changes **only the write-confirmation flow** (ARCHITECTURE §4.3):

| | Manual (default) | Auto |
|---|---|---|
| Write tool calls | Wait at the confirmation gate for a human decision (`POST /approvals/{id}`); unresolved writes are **denied** after `FLOOR_CONFIRM_TIMEOUT_S` (default 120s) | Auto-approved instantly, `confirmed_by='auto'` |
| Audit of approvals | `tool_calls` row (`confirmed_by='human'`, or `'policy'` on timeout-deny) + `tool.confirmation_requested` event | `tool_calls` row (`confirmed_by='auto'`) + `tool.confirmation_requested` event + a dedicated **`confirmation.auto_approved`** event per approval (tool name, args, work order, confirmation id) — nothing is silently approved |
| Who posts jobs | A human starts each shift (`POST /run/shift`) | The auto-run loop posts cycle after cycle itself (below) |

**Hard limits that hold in BOTH modes** — mode is an approval-flow switch,
never a capability switch:

- **Tool allowlists are unchanged.** Tools that do not exist stay
  nonexistent: there is no money-movement tool, no merge tool, and no
  hire/reject decision tool anywhere on this floor. Auto mode cannot
  invent them.
- **The deterministic Reviewer checks are unchanged.** Auto mode approves
  writes; it does not grade work. Rejection, appeal, and reputation rules
  are exactly as in manual mode.
- **Money math stays code.** Payroll, firing (PinkSlip), mutated hiring,
  and the auto budget cap are deterministic economy logic. The LLM never
  computes any of it.

## Auto-run loop

`POST /auto/start {"budget_cap_credits": N, "by": "human"}` starts the loop
(idempotent while running; starting also switches the mode to `auto`,
emitting `mode.changed`). The loop runs one full cycle at a time through
the ordinary engine path — Manager posts the next jobs from the registered
job families (`orchestrator.engine.JOB_FAMILIES` today; any family
registered with the engine joins automatically), workers bid, the award
formula picks a winner, the winner works through tools, deterministic
checks run, the Reviewer grades, the appeal window runs, the CFO closes
payroll, firing/hiring follows the standing rules — then the next cycle
starts. Per cycle it emits `auto.cycle_started`; the engine's own
`cycle.closed` marks completion.

### The budget cap (deterministic, enforced in code)

- **Spend** = credits the floor *paid out* in completed cycles of this
  run: the sum of positive ledger rows (earnings + review fees) per cycle.
  Salaries and appeal fees are charged against agent balances, not paid
  out, so they do not consume the cap.
- **Projection** of the next cycle = the previous cycle's actual payout.
  For the first cycle (no history) it is the worst case: the sum of the
  budgets of the families about to be posted (a bid can never exceed its
  job's budget) plus maximum review fees (primary + appeal per job).
- **Stop rule:** at a cycle boundary, if `spent + projected > cap`, the
  loop does not start the cycle and stops with
  `auto.stopped {reason: "budget_cap_reached", ...}`.

### Pause, stop, and switching to manual

- `POST /auto/pause` — takes effect at the **next cycle boundary**. An
  in-flight cycle always completes in full (jobs → review → payroll):
  a half-finished cycle is the unsafe state, so the cycle boundary is
  the safe boundary. Emits `auto.paused`. Resume with `POST /auto/start`
  (spend and cycle count carry over; the cap may be replaced).
- `POST /auto/stop` — same boundary semantics; emits
  `auto.stopped {reason: "human_stop"}`.
- **Switching to manual mid-run** (`POST /mode {"mode": "manual"}`) is
  the immediate lever: the gate reads the mode on every call, so
  auto-approvals stop for the very next write, and the loop stops at the
  next boundary with `auto.stopped {reason: "switched_to_manual"}`. (A
  cycle caught mid-flight by the switch will gate its remaining writes
  manually — expect it to stall at the gate and end as an error stop;
  use pause when you want the graceful finish.)

### Auto lifecycle events

| Event | Payload highlights |
|---|---|
| `mode.changed` | `mode`, `previous_mode`, `by` |
| `confirmation.auto_approved` | `confirmation_id`, `work_order_id`, `tool_name`, `args`, `mode: "auto"` |
| `auto.started` | `budget_cap_credits`, `by`, `resumed` |
| `auto.cycle_started` | `cycle_no`, `projected_spend_credits`, `spent_credits`, `budget_cap_credits` |
| `auto.paused` | `cycles_completed`, `spent_credits`, `budget_cap_credits` |
| `auto.stopped` | `reason`: `budget_cap_reached` \| `switched_to_manual` \| `human_stop` \| `error`, plus spend/cycle totals |

## Boot seeding

The mode at process start comes from the environment: `FLOOR_MODE`
(`manual`|`auto`) wins; else an explicitly set legacy
`POLICY_AUTO_APPROVE_WRITES` seeds it (`true` → auto, `false` → manual);
else **manual**. Note the deliberate change: previously an *unset*
`POLICY_AUTO_APPROVE_WRITES` meant auto-approve; the unset default is now
the safe one. Deployments that relied on the old implicit default should
set `FLOOR_MODE=auto` (or set the policy env explicitly). On restart the
mode returns to its env-seeded value; `mode.changed` events in the log
are the durable record of runtime changes.

## API contract (for the console)

```
GET  /mode
  -> { "mode": "manual" | "auto",
       "changed_by": "human" | "system",
       "gate": { "writes_require_human_confirmation": bool, "auto_approve": bool },
       "auto_run": { "status": "stopped" | "running" | "paused",
                     "budget_cap_credits": int | null,
                     "spent_credits": int, "cycles_completed": int,
                     "current_cycle": int | null,
                     "last_cycle_spend_credits": int | null,
                     "stop_reason": str | null, "started_by": str | null,
                     "last_error": str | null },
       "recent_auto_approvals": [ {confirmation_id, work_order_id,
                                   tool_name, args, mode, approved_by} ] }

POST /mode            {"mode": "auto" | "manual", "by": "human"}  -> GET /mode shape
POST /auto/start      {"budget_cap_credits": 1000, "by": "human"} -> auto_run object
                      (422 without a positive cap on a fresh run; no-op 200 while running;
                       switches mode to "auto" first if needed)
POST /auto/pause      {"by": "human"}  -> auto_run object (boundary semantics, above)
POST /auto/stop       {"by": "human"}  -> auto_run object
GET  /auto/status                      -> auto_run object
GET  /health          now also carries "mode" and "auto_run"
```

While auto-run is active, `POST /run/shift` and `POST /reset` answer 409.
