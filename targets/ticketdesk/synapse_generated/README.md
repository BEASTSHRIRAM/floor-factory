# Synapse-generated MCP server — TicketDesk

`synapse_auto_server.py` in this folder is a **real generated artefact**: it was
produced on 2026-11-24 by an actual Synapse run against the real TicketDesk
codebase in this repo:

```bash
synapse build --local --auto --all-endpoints
# Synapse CLI 0.1.9, codegen on Groq (openai/gpt-oss-120b)
# Session: sess_9058bbd4_mwut91e0_ddd338
```

It exposes 13 tools, one per TicketDesk endpoint: `list_tickets`,
`find_duplicates`, `get_ticket`, `create_ticket`, `assign_ticket`,
`set_priority`, `add_comment`, `set_status`, `merge_tickets`, `sla_breaches`,
`stats_summary`, `health`, `admin_reset`.

## Verified live (2026-11-24)

The generated file was run **unmodified** against the live TicketDesk service
(`ENDPOINT_BASE_URL=http://localhost:8101`):

- `list_tools` returned exactly the 13 tools above.
- Reads returned real data (`health`, `list_tickets`, `stats_summary` — 21 tickets).
- A real write succeeded: `add_comment` created comment id 37 on ticket 1,
  read back from the service via `get_ticket`.

## Runtime note

The generated code targets the **MCP v1 SDK** (`mcp.server.fastmcp`). The
floor's own environment currently carries MCP 2.x, so the generated server was
verified in a pinned environment:

```bash
pip install "mcp<2" httpx requests
ENDPOINT_BASE_URL=http://localhost:8101 python synapse_auto_server.py
```

## Status

This server is **not yet wired in as the production TicketDesk server** — the
floor still runs the generated-style `../mcp_server.py`. Swapping it in is a
documented follow-up: it needs the MCP version decision above and the
`read_`/`write_` prefix mapping the floor's confirmation gate expects. It is
committed as proof that Synapse generation works end-to-end against a real
workplace in this repo, not as a pattern or a mock.
