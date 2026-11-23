# StockRoom (target system #2)

A tiny inventory API — the second "legacy system" THE FLOOR onboards.
THE FLOOR's agents never touch this code; they only call its API through
a Synapse-generated MCP server (`mcp_server.py` in this folder stands in
for that generated output).

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create stockroom.db with the demo dataset
uvicorn app:app --port 8102      # serve on :8102
python3 reset.py                 # restore the exact seeded state at any time
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist — see ARCHITECTURE §6.2)

| Method & path | Effect |
|---|---|
| `GET /items?category=&location=` | read |
| `GET /items/{id}` | read |
| `POST /items/{id}/adjust` | write |
| `GET /orders/pending` | read |
| `GET /stats/summary` | read |
| `GET /items/low-stock?threshold=` | read — **the `--discover` finale endpoint** |

Deliberately NOT exposed: any delete endpoint — exposure is a safety decision.

## The `--discover` finale endpoint

`GET /items/low-stock` is the demo's live-onboarding set piece
(ARCHITECTURE §4.5): in the live demo the presenter *adds this endpoint
on stage*, runs `synapse build --discover`, and the factory's tool
registry refreshes so a worker can immediately complete a job that was
impossible a minute earlier ("produce a reorder list for everything
below threshold"). The endpoint ships in this codebase so the finale is
rehearsable end-to-end; to stage the live version, comment the route out
before the demo, uncomment it on stage, restart uvicorn, and run the
discover build.

## Seed data

15 items across peripherals / cables / consumables / displays / audio /
accessories / furniture / storage. Exactly **4 are below the default
reorder threshold of 10**: USB-C Cable 1m (3), AA Batteries 4-pack (5),
Webcam 1080p (0 — out of stock), Ethernet Cable 5m (8). 4 purchase orders
are pending, 3 of them restocks for low-stock items.
