# TicketDesk (target system #1)

A deliberately ordinary FastAPI support-ticket API — the kind of internal
tool every company has. THE FLOOR's agents never touch this code; they only
call its API through a Synapse-generated MCP server.

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create ticketdesk.db with the messy dataset
uvicorn app:app --port 8101      # serve on :8101
python3 reset.py                 # restore the exact seeded state at any time
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist — see ARCHITECTURE §6.1)

| Method & path | Effect |
|---|---|
| `GET /tickets?status=&assignee=&priority=&category=` | read |
| `GET /tickets/{id}` | read |
| `GET /tickets/duplicates` | read |
| `POST /tickets` | write |
| `POST /tickets/{id}/assign` | write |
| `POST /tickets/{id}/priority` | write |
| `POST /tickets/{id}/comment` | write |
| `POST /tickets/{id}/status` | write |
| `POST /tickets/merge` | write |
| `GET /sla/breaches` | read |
| `GET /stats/summary` | read |

Deliberately NOT exposed: any delete endpoint — exposure is a safety decision.

## Seed data

25 tickets with planted messiness (see `seed.py`): 6 unassigned (2 P1),
4 duplicates of 2 originals, 5 stale resolved-never-closed, 3 SLA-breached,
inconsistent categories (`billing` / `Billing` / `billng`), 2 angry customers.
