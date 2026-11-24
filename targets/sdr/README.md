# SDR Department Workplace (target: CRM-lite)

THE FLOOR's SDR department workplace — a deliberately ordinary CRM-lite
API (accounts + leads), built in exactly the TicketDesk pattern: plain
FastAPI + its own SQLite file, a generated-style MCP server exposing an
allowlist of tools, seed/reset, and deterministic Reviewer checks.
THE FLOOR's agents never touch this code; they only call its API
through the department's MCP tools.

**DRAFTS ONLY.** There is no send endpoint in this API and no send tool
in the tool surface — an agent here *cannot* send outreach. Drafts are
stored on leads; sending is a human-gated promotion that happens outside
the agent tool surface (blueprint Phase 2).

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create sdr.db (15 accounts, 25 leads)
uvicorn app:app --port 8105      # serve on :8105
python3 reset.py                 # restore the exact seeded state at any time
python3 run_job_demo.py          # run jobs-pack Job 1 end-to-end (direct mode)
python3 checks.py all            # run the Reviewer's deterministic checks
```

(Or `POST /admin/reset` while the server is running.)

## Tool surface (the Synapse Auto allowlist — see department.json)

| Tool | Method & path | Effect |
|---|---|---|
| `list_accounts` | `GET /accounts` | read |
| `get_account` | `GET /accounts/{id}` | read |
| `list_leads` | `GET /leads?stage=&account_id=` | read |
| `research_account` | `GET /accounts/{id}/research` | read |
| `score_lead` | `POST /leads/{id}/score` | write (gated) |
| `draft_outreach` | `POST /leads/{id}/draft` | write (gated) |
| `qualify_lead` | `POST /leads/{id}/qualify` | write (gated) |
| `add_crm_note` | `POST /notes` | write (gated) |

Deliberately NOT present: any send/delete endpoint — exposure is a
safety decision, and sending is a human-gated promotion.

Research is over stored CRM data only — `research_account` returns the
account's stored firmographics and tech/buying signals; there is no
live web in this workplace.

## ICP rubric (rubric.py — shared by the job and the checks)

Size 50–500 → +30 (20–49 / 501–1000 → +15) · target industry
(saas/fintech/ecommerce/logistics/healthtech) → +25 (adjacent
edtech/manufacturing → +10) · stored signals → points each, capped +45.
Qualify threshold: score ≥ 60. The Reviewer's check **recomputes** every
score from account data — an off-rubric score fails review.

## Jobs pack (department.json → job_templates)

1. **Research and score the new-lead batch** — ₡120. Checks:
   `score_new_batch` (every new-batch lead scored with reasons; every
   score rubric-exact).
2. **Draft outreach for qualified accounts** — ₡140. Checks:
   `draft_qualified` (every qualified lead has a draft; every draft
   references ≥1 account-specific signal, phrase-matched against the
   account's stored signals).

## Seed data

15 accounts (size / industry / signals / last touch) and 25 leads:
10 `new` (unscored — Job 1's batch), 6 `researching` (rubric-scored),
4 `drafted` (scored + signal-referencing draft), 5 `qualified`
(2 with drafts; 3 without — Job 2's work).
