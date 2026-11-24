# ExtDesk — SIMULATED external issue system

**This is a simulator, not Jira.** ExtDesk is a small standalone
FastAPI + SQLite app that plays the role of *a customer's own issue
tracker* so THE FLOOR's connections layer and intake/bug loop can be
verified end-to-end against a genuinely separate system (own process,
own database) with no external account and no credentials.

The floor never talks to ExtDesk directly. It reaches it through the
`localdesk` provider in `orchestrator/connections.py` — the same
provider interface (`list_issues` / `get_issue` / `transition_issue` /
`tools`) that a real Composio connection will implement once Sriram
provides a `COMPOSIO_API_KEY`. Swapping the simulator for the real
thing is a provider swap, not a redesign.

Run:

```bash
cd targets/extdesk
python3 seed.py                                   # create extdesk.db
../../.venv/bin/python -m uvicorn app:app --port 8108
```

Endpoints: `GET /health`, `GET /issues`, `GET /issues/{id}`,
`POST /issues`, `POST /issues/{id}/transition` `{status, comment?}`,
`POST /issues/{id}/comments`, `POST /admin/reset`.

Seed: 5 issues (ids 1–5) — a critical checkout 500 (Open), a high
password-reset bug (Open), a low cosmetic bug (Open), a medium stale-
badge bug (In Progress), and one low typo bug already Done.
