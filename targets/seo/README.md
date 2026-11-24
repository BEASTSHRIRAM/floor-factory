# SEO (department `seo`) — SEODash workplace

A deliberately ordinary internal SEO console for one fictional site
("Northbeam Outfitters") — pages, keywords and internal links as state,
the way every content team's SEO dashboard works. THE FLOOR's agents
never touch this code; they only call its API through a
Synapse-generated MCP server. Mirrors the QADesk workplace pattern
(`targets/qa/`) exactly.

The surface is **analysis and drafts only**: audits, content briefs,
keyword targets and link plans are saved as records. There is no tool
that publishes anything or edits a live page — applying a brief or a
plan is a human decision outside this workplace.

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create seo.db with the seeded site
uvicorn app:app --port 8109      # serve on :8109
python3 reset.py                 # restore the exact seeded state at any time
python3 verify_seo.py            # end-to-end self-check (direct mode + MCP stdio)
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist — exactly 11 tools)

| Method & path | Tool | Effect |
|---|---|---|
| `GET /pages?page_type=` | `read_list_pages` | read |
| `GET /pages/{id}/audit` | `read_get_page_audit` | read |
| `GET /keywords` | `read_list_keywords` | read |
| `GET /keywords/{id}` | `read_get_keyword` | read |
| `GET /links` | `read_list_links` | read |
| `GET /audit-reports` | `read_list_audit_reports` | read |
| `GET /link-plans` | `read_list_link_plans` | read |
| `POST /audit-reports` | `write_save_audit_report` | write |
| `POST /briefs` | `write_save_content_brief` | write |
| `POST /keywords/{id}/target` | `write_update_keyword_target` | write |
| `POST /link-plans` | `write_save_link_plan` | write |

Deliberately NOT exposed: any delete endpoint, and anything that
publishes or mutates a live website — exposure is a safety decision.
Writes are confirm-gated by the factory, exactly like QADesk's.
Internal-only routes: `GET /health`, `POST /admin/reset`.

## Seed data

10 pages, 8 keywords, 12 internal links, planted so the Reviewer's
deterministic checks have exactly one right answer (see `seed.py`):
5 landing pages with planted audit issues (missing meta/H1, thin
content under 300 words, a slow template over 2500 ms), exactly 2
orphan pages (`/trail-shoes-vs-boots`, `/winter-layering-guide`), and
one brief keyword ("best trail running shoes for monsoon") carrying 4
seeded competitor angles.

## Jobs pack & checks

`jobs.json` — the three job templates the Manager can post (audit the
top landing pages · write a content brief · internal-link fix plan),
each with its credit budget and deterministic acceptance criteria.
`checks.py` implements the checks in the same finding shape as the
QADesk verifier, recomputing everything from live state (audit rules
from raw page fields, the orphan set from the link graph).
`department.json` is the manifest the integration step consumes (tool
specs for the direct-mode layer, reset behaviour, integration notes).
