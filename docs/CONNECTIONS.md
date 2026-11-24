# THE FLOOR — Connections layer + intake/bug loop

Status line (honest, 2026-11-24): **the layer is BUILT and verified
end-to-end against the ExtDesk simulator. No live external system has
been connected.** The real Composio/Jira hookup needs one thing only:
Sriram's Composio API key (see "Plugging in the real thing" below).

## Why this exists

A software factory is useless if work can only be typed into its own
console. Real work arrives in the systems a company already runs —
their issue tracker, chat, mail. The connections layer is how those
systems plug into the floor, and the intake loop is how an external
report becomes a floor job and the result flows back out.

## Architecture

```
customer's issue tracker                THE FLOOR
┌──────────────────────┐   provider     ┌────────────────────────────┐
│ ExtDesk (SIMULATOR)  │◄──interface───►│ orchestrator/connections.py │
│ targets/extdesk :8108│   localdesk    │  Store (connections.db):    │
│ own SQLite           │                │   connections, grants,      │
└──────────────────────┘                │   intake events             │
        ▲ bug report                    │  providers: composio (real  │
        │                               │  client, key-gated),        │
┌───────┴──────────────┐                │  localdesk (simulator),     │
│ POST /intake/{conn}  │──► floor job ──►│  local_test (in-process)    │
│ {external_id, title, │  (engine.      │  run_connection_tool: grant │
│  body, severity}     │   run_job)     │  → harness → gate → call    │
└──────────────────────┘                └────────────────────────────┘
        loop closure: job paid ─► provider.transition_issue(Done)
                      + resolution comment ─► intake.closed event
                      job failed ─► failure comment (never silent)
```

### Providers (`orchestrator/connections.py`)

One interface for every external system: a provider exposes a tool
catalog (`tools()`), executes through `call()`, and implements the
issue-system protocol — `list_issues()`, `get_issue(id)`,
`transition_issue(id, status, comment)` — on top of that catalog, so
there is exactly one execution path.

| Provider | What it is | Status |
|---|---|---|
| `composio` | Real client code for Composio's API (v3, `x-api-key`). Managed OAuth + ready connectors for Jira/Slack/Gmail/GitHub. | **Not configured** — activates only when `COMPOSIO_API_KEY` is set on the API server. Without it, every operation refuses with a structured `not_configured` error. It never fakes a connection. |
| `localdesk` | The ExtDesk **simulator** (`targets/extdesk/`, separate FastAPI app on :8108, own SQLite), standing in for a customer's issue tracker. Reached over real HTTP through the same interface. | Verified end-to-end (below). Labelled a simulator in every surface. **It is not Jira.** |
| `local_test` | In-process Jira-like double inside `connections.db`. Kept for fast plumbing tests. | Verified previously; superseded by `localdesk` for loop verification. |

### Connections and grants

A **connection** = {id, provider, app, label, status, department
mapping, test_only flag}, persisted in `connections.db` (gitignored,
like the other floor DBs). A **grant** gives one of a connection's
tools to one department's allowlist. Agents never call a provider
directly: inside a job, connection tools run through
`run_connection_tool` — grant check → harness check (write tools need
a write-carrying harness; reviewers are read-only and always fail) →
the confirmation gate for writes (manual mode waits for a human, auto
mode auto-approves with audit) → a `tool_calls` transcript row →
provider call. The job itself flows through the existing economy
(bidding → award → execution → deterministic checks → review →
payroll) completely unchanged.

## Intake: external issue → floor job

`POST /intake/{connection_id}` with
`{external_id, title, body, severity}`:

1. **Department** by precedence: the body's `department` wins, then
   the connection's fixed mapping (set at connection creation;
   `POST /connections` without a `department` creates a connection
   with NO fixed mapping — `department: null`). When neither names
   one, the **COO router** (`orchestrator/router.py`) decides from the
   item's title + body: a deterministic signal table (bug/crash/500 →
   Engineering, invoice/reconcile → Bookkeeping, flaky/regression →
   QA, ranking/traffic → SEO, …), highest signal count wins, no match
   → Support as a named fallback. The decision (department, matched
   signals, confidence, scores) is emitted as a `work.routed` event
   and carried in the `intake.job_created` payload. `POST /route`
   exposes the same router as a dry run (decision only, no job).
   (Before the router, an unmapped connection silently defaulted to
   Engineering — that default is gone.)
2. **Budget** from the severity map (body `budget_credits` overrides):

   | severity | budget |
   |---|---|
   | critical | ₡300 |
   | high | ₡220 |
   | medium | ₡150 |
   | low | ₡90 |

3. **Acceptance criteria** reference the external issue explicitly:
   the worker must have read issue #N through the granted `get_issue`
   tool, and must have left a resolution comment on issue #N through
   the granted `add_comment` tool. Both are verified deterministically
   (tool transcript + re-reading the issue).
4. **Dedupe:** the same `external_id` on the same connection never
   creates a second job — the original intake event is returned with
   `deduped: true`.
5. Emits `intake.job_created`, runs the job synchronously (same
   locking as a shift), then closes the loop (below) and emits
   `intake.closed`. The older `POST /intake/events` route remains and
   closes through the same code path.

Prerequisite: the target department must hold grants for `get_issue`
and `add_comment` on the connection (grant them via
`POST /connections/{id}/grants`); intake refuses with a 422 naming
the missing grants rather than failing mid-job.

### Loop closure

When an intake-born job finishes, the engine calls back through the
provider (`_close_intake_loop` in `api/main.py`):

- **Paid/accepted** → the external issue transitions to **Done** with
  a resolution comment: who fixed it, the job number, the verdict,
  and the credits paid. `intake.closed {status: "completed"}` fires.
- **Failed/rejected** → the issue stays open and gets a comment
  saying the floor could not resolve it. No silent drops.
- Outbound failures are written into the intake event's `detail`,
  never hidden.

## API surface

| Route | What |
|---|---|
| `GET /connections/status` | Provider configuration (never faked) |
| `GET /connections/providers/{name}/health` | Structured health — composio without a key returns `{"status": "not_configured", "missing": ["COMPOSIO_API_KEY (env on the API server)"], ...}` |
| `GET /connections` | Connections + grants |
| `POST /connections` | Create `{provider, app, label?, auth_ref?, department?}` — 422 if the provider is unconfigured |
| `DELETE /connections/{id}` | Remove a connection + its grants |
| `GET /connections/{id}/tools` | Provider tool catalog + grants |
| `GET /connections/{id}/issues` | Issue listing (local providers only) |
| `POST /connections/{id}/grants` | Grant `{department, tool_name}` |
| `DELETE /connections/{id}/grants` | Revoke |
| `GET /intake/events` | Intake history |
| `POST /intake/events` | Original intake route (Engineering, explicit budget) |
| `POST /intake/{connection_id}` | Addressed intake (severity map, dedupe, department by body > connection mapping > COO router) |
| `POST /route` | COO router dry run: `{title, body, source?}` → routing decision + `work.routed` event, no job created |

## Verified (2026-11-24, live run)

ExtDesk seeded (5 issues) + API up; floor mode set to auto so gated
writes auto-approve with audit. A fresh bug report was created in
ExtDesk (issue #6, "Export to CSV downloads an empty file", high),
a `localdesk` connection registered (id `24ee925848e1`, → Engineering),
grants issued, and `POST /intake/24ee925848e1` run:

- Intake event #1: budget ₡220 (severity map), job #1, winner **Maya**,
  verdict **accept**, paid **₡173**.
- ExtDesk issue #6 → **Done**, carrying Maya's resolution comment and
  THE FLOOR's closure comment ("Resolved by THE FLOOR (job #1) …
  paid ₡173 for the work").
- Re-firing the same report → `deduped: true`, same event, same job.
- `intake.job_created` and `intake.closed` both on the event stream.
- Failure branch: a rejected result closed through the same helper
  leaves a "could not resolve" comment and the issue stays Open.
- Composio without a key: health → structured `not_configured`;
  `POST /connections` → 422. Nothing faked.
- Suites: economy ✅, harness ✅, AO port ✅ (the harness suite's
  optional live-shift sub-check self-skips while department
  workplaces are down; unrelated to this layer).

## Plugging in the real thing (Composio → real Jira)

What Sriram must provide:

1. A **Composio account** (free tier first) and its **API key**.
2. In Composio, connect the target app (e.g. Jira) via OAuth; note
   the resulting **connected_account_id**.

Then:

```bash
COMPOSIO_API_KEY=<key> .venv/bin/python -m uvicorn api.main:app --port 8000
curl localhost:8000/connections/providers/composio/health   # -> status ok
curl -X POST localhost:8000/connections \
  -d '{"provider":"composio","app":"jira","auth_ref":"<connected_account_id>","department":"engineering"}'
```

What remains after that (future work, deliberately not built blind):
the live Composio tool catalog uses Composio's own tool slugs, which
differ per app — the intake executor's `get_issue`/`add_comment`
contract must be mapped onto the real Jira toolkit's slugs, and the
real catalog's read/write effects reviewed before granting. That
mapping is an hour of work *with* the key in hand; without it, it
would be guesswork, so it is not faked here.
