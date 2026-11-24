# api/

FastAPI single process (`api/main.py`, port 8000): REST snapshots, the SSE
event stream, shift/reset controls, and the write-confirmation approval
endpoints for the orchestrator's gate.

## Run

```bash
cd ~/workspace/vibeathon-floor/repo
# 1) target system (required for a shift to do real work)
.venv/bin/python -m uvicorn app:app --port 8101 --app-dir targets/ticketdesk &
# 2) this API
.venv/bin/python -m uvicorn api.main:app --port 8000
# 3) drive it
curl -X POST localhost:8000/reset
curl -X POST "localhost:8000/run/shift?cycles=2"          # background; watch /events
curl -X POST "localhost:8000/run/shift?cycles=2&wait=true" # blocking, returns summary
```

Headless alternative (no API): `python -m orchestrator.engine --cycles 2 --reset`.

## Endpoints

| Route | What |
|---|---|
| `GET /health` | status, agent count, last event seq, TicketDesk/StockRoom reachability |
| `GET /state/agents` | roster incl. fired agents, reputation, ledger balance |
| `GET /state/jobs` | jobs with acceptance criteria, bids, work orders |
| `GET /state/ledger?limit=100` | append-only ledger, newest first |
| `GET /state/events?after_seq=&limit=` | stored events (polling fallback) |
| `GET /events?from_seq=0` | SSE: replay from `from_seq`, then live events |
| `POST /run/shift?cycles=2&wait=false` | run a shift (409 if one is running) |
| `GET /run/status` | running flag + last summary/error |
| `POST /reset` | reset floor.db + roster; reseed TicketDesk (and StockRoom best-effort) |
| `GET /approvals` | pending write confirmations (manual gate mode) |
| `POST /approvals/{confirmation_id}` | `{"approved": bool, "by": "human"}` — resolves a gated write |
| `POST /confirmations/{confirmation_id}` | alias of the above |
| `GET /mode` | floor mode (`manual`\|`auto`), gate state, auto-run state, recent auto-approvals |
| `POST /mode` | `{"mode": "auto", "by": "human"}` — set the floor mode (emits `mode.changed`) |
| `POST /auto/start` | `{"budget_cap_credits": 1000, "by": "human"}` — start/resume auto-run (idempotent) |
| `POST /auto/pause` | pause auto-run at the next cycle boundary |
| `POST /auto/stop` | stop auto-run at the next cycle boundary |
| `GET /auto/status` | auto-run state only |
| `GET /connections` / `POST /connections` | connection registry (providers: composio — key-gated, never faked; localdesk — ExtDesk simulator; local_test) |
| `GET /connections/providers/{name}/health` | structured provider health (`not_configured` names what's missing) |
| `POST /connections/{id}/grants` | grant a connection tool to a department |
| `GET /connections/{id}/issues` | issues on a local-provider connection |
| `POST /intake/{connection_id}` | external issue event → floor job (severity→budget map, deduped) → issue Done + resolution comment (docs/CONNECTIONS.md) |
| `POST /intake/events` | original intake route (same loop closure) |

If `repo/ui/index.html` exists it is served at `/` (mounted last; API routes win).

## Floor modes (manual / auto)

Full semantics in `docs/MODES.md`. Short version: the gate branches on the
floor mode (`orchestrator/mode.py`, default **manual**). Manual: every
write waits for a human decision via the approvals endpoints; unresolved
writes are denied after `FLOOR_CONFIRM_TIMEOUT_S` seconds (default 120).
Auto: writes auto-approve as `confirmed_by='auto'`, each one audited with a
`confirmation.auto_approved` event, and the auto-run loop runs cycle after
cycle inside a human-set budget cap until it is paused/stopped, the mode
switches back to manual, or the cap is reached. Boot seeding: `FLOOR_MODE`
env, else an explicitly set `POLICY_AUTO_APPROVE_WRITES` (`true` → auto,
`false` → manual), else manual.
