# Synapse-generated MCP server — StockRoom

`synapse_auto_server.py` in this folder is a **real generated artefact**: it was
produced on 2026-11-25 by an actual Synapse run against the real StockRoom
codebase in this repo:

```bash
synapse build --local --auto --all-endpoints
# Synapse CLI 0.1.9, codegen on Groq (openai/gpt-oss-120b)
# Session: sess_b4295cf5_mwv4ha6p_bd16ba
```

It exposes 8 tools, one per StockRoom endpoint: `list_items`, `low_stock`,
`get_item`, `adjust_item`, `pending_orders`, `stats_summary`, `health`,
`admin_reset` — matching the live service's OpenAPI operation count (8).

## Verified live (2026-11-25)

The generated file was run **unmodified** against the live StockRoom service
(`ENDPOINT_BASE_URL=http://localhost:8102`):

- `list_tools` returned exactly the 8 tools above.
- Reads returned real data (`list_items` — seeded inventory, e.g. item 1
  "Wireless Mouse", quantity 42; `stats_summary`; `get_item`).
- **Write defect found (as generated):** the one non-reset write tool,
  `adjust_item`, omits the request body's required `delta` field — it sends
  only `{"reason": ...}`. Calling it returns the service's 422, and a read-back
  confirms no state changed (quantity still 42). The write path therefore does
  **not** verify for StockRoom; fixing it would require editing the generated
  file, which this folder's rules forbid — the defect is recorded here instead.

## Runtime note

The generated code targets the **MCP v1 SDK** (`mcp.server.fastmcp`). The
floor's own environment currently carries MCP 2.x, so the generated server was
verified in a pinned environment:

```bash
pip install "mcp<2" httpx requests
ENDPOINT_BASE_URL=http://localhost:8102 python synapse_auto_server.py
```

## Status

This server is **not yet wired in as the production StockRoom server** — the
floor still runs the generated-style `../mcp_server.py`. Swapping it in is a
documented follow-up: it needs the MCP version decision above and the
`read_`/`write_` prefix mapping the floor's confirmation gate expects. It is
committed as proof that Synapse generation works against a real workplace in
this repo, not as a pattern or a mock.
