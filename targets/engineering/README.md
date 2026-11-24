# Engineering (department workplace — repo-lite)

A deliberately ordinary repo-lite system of record: engineering issues,
pull-request records and CI results in one small FastAPI + SQLite service.
It stands in for a real code repository the way TicketDesk stands in for a
real helpdesk — the pattern that matters is **Synapse-shaped tools over a
system of record, with CI as the deterministic check**. THE FLOOR's agents
never touch this code; they only call its API through the MCP tool layer
(`mcp_server.py`, the generated-style stand-in for a Synapse Auto build).

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create engineering.db with the demo dataset
uvicorn app:app --port 8106      # serve on :8106
python3 reset.py                 # restore the exact seeded state at any time
python3 verify_e2e.py            # full verification (needs the server running)
```

(Or `POST /admin/reset` while the server is running.)

## The human-merge gate (platform rule)

**Agents prepare PRs; humans merge them.** This service has **no merge
endpoint and no delete endpoints**, and the tool surface has **no merge
tool**. A PR record can be opened, sent back (`changes_requested`), or
`approved` — approval requires a recorded green CI and a reviewer who is
not the author — and that is where the system's authority ends. Merging,
and marking the issue done, is a human action outside the tool surface.

## The deterministic CI rule

CI is computed **once, when a PR is opened**, by the service itself
(`seed.py: compute_ci`, the single source of truth):

> A PR passes CI iff **(a)** every keyword in the issue's
> `acceptance_keywords` appears in the PR's `change_summary`
> (case-insensitive), **and (b)** the PR's `files_touched` covers every
> file in the issue's `files` list.

The result is stored as an immutable `ci_results` row. A red PR is answered
by opening a **new** PR, never by editing the old one.

## Exposed API (the Synapse Auto allowlist — see department.json)

| Method & path | Tool | Effect |
|---|---|---|
| `GET /issues?status=&priority=&label=&unlabelled=&assignee=` | `read_list_issues` | read |
| `GET /issues/{id}` | `read_get_issue` | read |
| `GET /prs/{id}` | `read_get_pr` | read |
| `GET /prs/{id}/ci` | `read_get_ci_status` | read |
| `GET /stats/summary` | `read_stats_summary` | read |
| `POST /issues/{id}/claim` | `write_claim_issue` | write |
| `POST /issues/{id}/triage` | `write_triage_issue` | write |
| `POST /prs` | `write_open_pr` | write |
| `POST /prs/{id}/request-changes` | `write_request_changes` | write |
| `POST /prs/{id}/approve` | `write_approve_pr` | write |
| `POST /issues/{id}/note` | `write_add_eng_note` | write |

All writes are confirm-gated by the factory before dispatch. Deliberately
NOT exposed: merge, delete — exposure is a safety decision.

## Seed data

12 issues (see `seed.py`): 8 solvable with acceptance statements, keywords
and required files; **4 unlabelled with no priority** (the triage job's raw
material); 2 already claimed. 3 PR records — PR 1 open with green CI
(issue 3), PR 2 **changes-requested with red CI** (issue 11: the summary
never addresses the sunset requirement), PR 3 **approved with green CI**
(issue 5) and still unmerged, because merging is not the system's call.

## Jobs pack

`jobs.json` — templates with credit budgets and deterministic Reviewer
checks (`checks.py`): **Work issue #N and open a PR** (₡160),
**Triage the unlabelled issues** (₡90), **Answer changes-requested PR**
(₡140). Integration manifest for the department: `department.json`.
