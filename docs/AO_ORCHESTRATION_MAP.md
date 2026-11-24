# AO Orchestration Map — Agent Orchestrator → THE FLOOR

What we studied in Agent Orchestrator's (AO) orchestration core, what maps to
THE FLOOR, what we ported, and what we deliberately skipped. Companion to
`ao_study.md` (frontend + borrow-list); this doc is backend-only.

- **Source:** `~/workspace/ref/agent-orchestrator` — OrchestratorInc/agent-orchestrator,
  Apache License 2.0, Copyright 2026 Untrivial. No `NOTICE` file ships in AO.
- **Target:** THE FLOOR — `orchestrator/engine.py` (`FloorEngine`, a deterministic
  Python shift loop: intake → bid → award → execute → review → appeal → cycle
  close), `economy/core.py` (money/rules), `orchestrator/tools.py` +
  `mcp_manager/client.py` (tool execution + confirmation gate), `api/main.py`
  (REST snapshots + SSE replay from `?from_seq=`).
- **Ported code:** `orchestrator/ao_lifecycle.py`, `orchestrator/ao_runner.py`
  (new files only; proof: `orchestrator/test_ao_runner.py`).

---

## 1. How AO orchestrates (study summary, with citations)

AO is a Go daemon on `127.0.0.1`; the Electron app and the `ao` CLI are thin
clients of its HTTP API (repo `AGENTS.md`: the CLI contains no storage/runtime
logic). Five mechanisms do the orchestrating:

1. **Single dispatch path — `session_manager.Manager.Spawn`**
   (`backend/internal/session_manager/manager.go:1119`, ~8,500-line manager).
   Order matters: resolve mode/harness and **preflight before any durable
   state exists** (an unknown harness is rejected *before* `CreateSession`,
   "so a failed spawn never leaves an orphan") → insert the session row
   (SQLite trigger → `change_log` → CDC → `session.created` reaches clients
   *before* the session physically exists) → provision workspace → launch the
   controller → `lifecycle.Manager.MarkSpawned` writes the first activity
   fact. Spawn failure funnels to `markSpawnFailedTerminated*` — even a
   failed run ends terminated, with cleanup.
2. **Canonical fact reducer — `lifecycle.Manager`**
   (`backend/internal/lifecycle/manager.go`, 2,016 lines). Nobody writes
   lifecycle facts except through it: `MarkSpawned`,
   `ApplyRuntimeObservation(ctx, id, ports.RuntimeFacts)`,
   `ApplyActivitySignal`, `MarkTerminated`. Durable facts are deliberately
   tiny (`backend/internal/domain/activity.go`, `domain/session.go`):
   `activity_state ∈ {active, idle, waiting_input, blocked, exited}`,
   `is_terminated`, controller generation, PR facts. `waiting_input` and
   `blocked` are **sticky** (`ActivityState.IsSticky`) — time never demotes
   them; both `NeedsInput`, but `blocked` (a pending *decision*) must never
   receive injected input, while `waiting_input` (an empty prompt) is safe to
   nudge. `MarkTerminated` is idempotent and funnels *every* terminal path
   through one cleanup hook (container reap — spare-on-ambiguity).
3. **Observers report; they never write.** The Runtime Reaper
   (`backend/internal/observe/reaper/reaper.go`, 5s tick =
   `DefaultTickInterval`) probes runtime handles and reports
   `ProbeAlive / ProbeDead / ProbeFailed` facts. **A failed probe is not
   proof of death** — it is recorded, never acted on as a kill. The SCM
   Observer (30s, ETag-cached) does the same for PR/check/comment facts.
4. **Derived status, never stored.** Display status and kanban column are
   computed at service read time from durable facts with a fixed precedence
   (`backend/internal/service/session/`, `domain.DisplayStatus`,
   `TestSessionListDerivesDisplayStatus`). AO's house rule (AGENTS.md):
   "Do not store derived/display session status."
5. **Process + run supervision.** `backend/pkg/agentruntime/process.go`:
   one process group per agent, **reaped exactly once**; cancel = graceful
   terminate → kill after `ShutdownGrace` (5s) + 2s kill-wait. Review runs
   get their own guarded lifecycle (`backend/internal/review/run_lifecycle.go`):
   `queued → launching → running → cancelling → completed/failed/cancelled/
   superseded` (`domain.ReviewRunStatus`), transitions only from explicit
   `from` sets (`transitionRun`), with launch/first-activity/idle/max-duration
   limits and a boot pass that settles runs a previous daemon left behind.
   Events: SQLite triggers → `change_log(seq, …)` → CDC poller with a seq
   watermark → broadcaster → SSE (`backend/internal/cdc/{event,poller,broadcast}.go`);
   `seq` is the ordering + idempotency key; clients resume from
   `Last-Event-ID`. Boundaries are hexagonal ports
   (`backend/internal/ports/*.go` — `session.go` `SpawnConfig`, `agent.go`,
   `runtime_observations.go`, …); adapters under `internal/adapters/` are
   leaves that never import core.

Concurrency model: sessions run in parallel by construction (each is its own
process + worktree); follow-up work is a **durable SQLite queue** claimed in
order at turn boundaries (user messages get their own turn, system messages
batch, a steer claims the whole queue, an uncertain provider result closes
receipts *without replaying* input).

---

## 2. The map — AO concept → FLOOR equivalent → decision

| # | AO concept (source) | THE FLOOR equivalent | Decision | Reason |
|---|---|---|---|---|
| 1 | Activity states `active/idle/waiting_input/blocked/exited`, sticky + needs-input semantics (`domain/activity.go`) | Worker presence (working / awaiting gate / idle / fired) | **PORT** — `WorkerActivity` in `ao_lifecycle.py` | 1:1 fit: our confirmation gate *is* AO's `blocked` (paused on a decision); stickiness prevents timeout UI from lying about a pending approval |
| 2 | Session lifecycle via one canonical reducer (`lifecycle/manager.go`) | Work-order lifecycle, today implicit in `engine.run_job` control flow | **PORT** — `WorkOrderLifecycle` in `ao_lifecycle.py` | One guarded write path makes job state auditable/replayable; states blend session + review-run lifecycles (see §3) |
| 3 | Review-run guarded transitions + limits (`review/run_lifecycle.go`, `domain.ReviewRunStatus`) | Job execution + review/appeal phases | **PORT** — transition table + `RunnerConfig` limits | The `from`-set guard is exactly what stops illegal jumps (e.g. queued → settled) in a demo that must never corrupt its own story |
| 4 | `session_manager.Spawn` ordering: preflight → row → workspace → launch → MarkSpawned (`session_manager/manager.go:1119`) | `WorkerRunner.run` sequence in `ao_runner.py` | **PORT (pattern)** | Preflight-before-state kills orphan work orders; spawn-failure → terminated funnel means failures still end cleanly |
| 5 | Reap-exactly-once process ownership (`pkg/agentruntime/process.go`) | Per-run cleanup (MCP client handles, temp state) | **PORT (pattern)** — cleanup-once in `WorkerRunner` | Our runs hold MCP stdio handles, not processes; the exactly-once discipline transfers, the process-group code does not |
| 6 | Reaper probes: Alive/Dead/**Failed ≠ death** (`observe/reaper/reaper.go`) | MCP-server / tool-call health during long shifts | **PORT (rule)** — `Probe` port + `runner.probe_failed` event | MCP stdio calls take ~5–7s and can hang; recording `probe_failed` as a fact keeps the UI honest instead of silently killing jobs |
| 7 | CDC event spine: `change_log` seq + watermark resume (`internal/cdc/*`) | `events` table + `emit_event` seq + SSE `?from_seq=` replay (already shipped, PR #3) | **ADOPT (already ours)** — ported events are shaped to match (`LifecycleEvent`, `to_floor_event()`) | We independently built the same spine; AO validates the design. No new code needed — just shape compatibility |
| 8 | Derived status at read time (`service/session`, AGENTS.md rule) | Job lane/phrase in API + console | **PORT** — `derive_display_status()` in `ao_lifecycle.py` | Kills the stored-status drift class (the payroll-dialog replay bug) at the root |
| 9 | Ports & adapters (`internal/ports/*.go`) | `WorkUnit` / `EventSink` / `Probe` protocols | **PORT (pattern)** | The runner core stays testable with fakes; engine/tools remain leaf adapters |
| 10 | Durable message queue, turn-boundary claiming (`session_manager/message_delivery.go`, arch §Feedback routing) | Human confirmations are synchronous today (`tools.request_confirmation`) | **SKIP (for now)** | Becomes necessary only when mid-shift human input goes async/multi-source; today's gate is synchronous by design |
| 11 | Hibernation + view leases (idle Chat sessions stopped, wake on work) | — | **SKIP** | Solves resource cost of long-lived idle sessions; floor shifts are short and batch |
| 12 | Controller generation fencing + detached ACP chat host (`cmd/ao-chat-host`) | — | **SKIP** | Daemon-restart-mid-turn survival for interactive sessions; a floor shift restarts from reset instead |
| 13 | Git worktree isolation per session (`adapters/workspace`) | Workers share target apps via MCP tools | **SKIP** | In FLOOR the tool allowlist *is* the isolation; worktrees solve a problem we don't have |
| 14 | SCM observer (PR/check polling) | Manager's TicketDesk/StockRoom scan at shift start | **SKIP** | The analogue already exists as the intake scan; there are no PRs in FLOOR's world |
| 15 | Per-project *orchestrator session* supervising workers | Floor Manager persona + `engine.run_shift` | **SKIP (code), KEEP (idea)** | AO's supervisor is itself an LLM session; ours is deterministic code — safer for a judged demo, and the economy rules must stay deterministic anyway |

---

## 3. The ported lifecycle (name mapping)

`orchestrator/ao_lifecycle.py` — `WorkOrderState`:

| FLOOR state | AO source |
|---|---|
| `queued` | session row created / `ReviewRunQueued` |
| `spawning` | `ReviewRunLaunching` / Spawn in flight |
| `working` | `ActivityActive` |
| `blocked` | `ActivityBlocked` — paused on the confirmation gate (sticky) |
| `waiting_input` | `ActivityWaitingInput` — submitted, awaiting review |
| `reviewing` | `ReviewRunRunning` |
| `remediating` | AO's "addressing comments" — appeal rework |
| `settled` | `ReviewRunCompleted` (accepted; payroll settles outside the machine) |
| `failed` / `cancelled` | `ReviewRunFailed` / `ReviewRunCancelled` |
| `terminated` | `ActivityExited` + `is_terminated` (absorbing; `terminate()` idempotent) |

`WorkerActivity` keeps AO's five activity values and `IsSticky`/`NeedsInput`
semantics verbatim. Events are `LifecycleEvent{seq, type, entity_id, payload,
created_at}` (AO `cdc.Event` shape); `to_floor_event()` flattens to our
`emit_event(conn, type, payload)` contract.

`orchestrator/ao_runner.py` — `WorkerRunner.run(work_order_id, worker, unit)`:
preflight (no durable state on failure) → QUEUED → SPAWNING → WORKING →
execute on a thread with a 5s heartbeat observer thread (facts only) →
WAITING_INPUT on success / FAILED on exception / CANCELLED on caller cancel →
cleanup exactly once → `terminate()`. `RunnerPool` adds bounded concurrency
(AO runs sessions in parallel; ours caps simultaneous work orders).

Proof: `orchestrator/test_ao_runner.py` — 24 checks, all passing under both
system `python3` and the repo venv (see the run report).

---

## 4. Licensing

AO is Apache-2.0 (root `LICENSE`, "Copyright 2026 Untrivial"; no `NOTICE`
file exists, so §4(d) propagates nothing). The ported files carry the §4(b)
modified-file notice + derivation comments naming their AO sources. Pattern
ports (no verbatim code) are used throughout; the Apache-2.0 text should sit
in the repo (e.g. `THIRD_PARTY_LICENSES/`) before public distribution, and
AO/Untrivial trademarks are not used as our branding (§6).

---

## 5. Integration note — how engine.py should adopt the runner

**Call sites (all inside `orchestrator/engine.py`):**

1. `FloorEngine.__init__` — construct once:
   `self.runner = WorkerRunner(self._emit, config=RunnerConfig())`.
   (`FloorEngine._emit(type_, payload)` already matches the `EventSink`
   protocol — it forwards to `economy.db.emit_event`.)
2. `FloorEngine.run_job` (line ~441) — wrap *only the execution segment*:
   the block from `executor(wo_id, winner)` through `ECO.submit_work(...)`
   becomes a `CallableWorkUnit(execute=lambda: (executor(wo_id, winner),
   ECO.submit_work(conn, wo_id)))` passed to
   `self.runner.run(wo_id, winner["name"], unit)`. Keep job creation,
   `persona_bid`, `ECO.award_job` **before** the runner call and `verify`,
   `ECO.review_work`, the appeal block and narration **after** it — the
   runner owns execution supervision, not the market.
3. Confirmation gate — when `FloorEngine.call` blocks on
   `tools.request_confirmation`, the *job's* machine (kept in a
   `dict[int, WorkOrderLifecycle]` on the engine, created at `run_job`
   start) transitions WORKING → BLOCKED on request and BLOCKED → WORKING on
   resolution. This is a two-line hook in `call()` around the existing gate
   call; the gate itself is untouched.
4. Review/appeal — after the runner returns, drive the same machine:
   WAITING_INPUT → REVIEWING before `verify`, → SETTLED on accept,
   → REMEDIATING on appeal, → FAILED on denied appeal; call
   `machine.terminate()` at job end. (The runner's own internal machine
   covers the execution window; the engine-level machine covers the whole
   job. Reconcile by having `run_job` own the machine and pass an
   `on_event` that emits `runner.*`-prefixed events today, plain event
   types once the console learns them.)
5. API/console — expose `derive_display_status(facts)` from the job facts
   the API already returns; do **not** add a status column anywhere.

**What changes when integrated:** every work order gets a legal, evented
lifecycle (the console can render state from events alone); a hung MCP call
surfaces as heartbeat silence + `probe_failed` facts instead of a frozen
shift; cleanup of tool clients becomes exactly-once even on exceptions.

**What must NOT change:** economy rules and money movement (`economy/core.py`
— bids, award formula, payroll, firing), the confirmation gate's semantics
(`orchestrator/tools.py` + `orchestrator/mode.py` — Manual/Auto behaviour),
and the deterministic acceptance checks (`engine.verify` + department
`checks.py`). The runner supervises execution; it never decides outcomes.
