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

If `repo/ui/index.html` exists it is served at `/` (mounted last; API routes win).

## Confirmation gate modes

`POLICY_AUTO_APPROVE_WRITES` (default `true`): writes auto-approve as
`confirmed_by='policy'` and are logged. Set it to `false` to require a human
decision per write via the approvals endpoints; unresolved writes are denied
after `FLOOR_CONFIRM_TIMEOUT_S` seconds (default 120).
