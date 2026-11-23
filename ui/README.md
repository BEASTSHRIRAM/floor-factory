# UI — Mission Control

Single-page dark "trading floor" mission control. **No build step, no
framework** — plain HTML/CSS/JS (`index.html`, `style.css`, `app.js`).
Serve this folder from the same origin as the factory API (or let the API
serve it directly).

## Data flow

- On load: REST snapshots from `GET /state/agents`, `GET /state/jobs`,
  `GET /state/ledger`, `GET /state/events`.
- Live: one SSE connection to `GET /events` drives the org chart, job
  board, bid ticker, ledger and narration feeds.
- Actions: `POST /run/shift` (Run Shift button), `POST /reset`
  (Reset Demo button — restores the exact seeded start state).
- If the API is unreachable, the page shows a "Waiting for factory API"
  state and retries automatically; it never crashes on missing data.

## Panels

Header (cycle, treasury totals, Run Shift / Reset) · Org Chart with agent
cards, Graveyard strip for fired agents, new-hire pulse with mutation
notes · Job Board in five status columns with a live bid ticker · Ledger
feed and narration log · payroll overlay on cycle close.
