# QA triage (department `qa`) — QADesk workplace

A deliberately ordinary internal CI-triage API — test runs and failures as
state, the way every engineering org's flaky-test dashboard works. THE
FLOOR's agents never touch this code; they only call its API through a
Synapse-generated MCP server. Mirrors the TicketDesk workplace pattern
(`targets/ticketdesk/`) exactly.

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create qa.db with the CI failure dataset
uvicorn app:app --port 8103      # serve on :8103
python3 reset.py                 # restore the exact seeded state at any time
python3 verify_qa.py             # end-to-end self-check (direct mode + MCP stdio)
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist — exactly 7 tools)

| Method & path | Tool | Effect |
|---|---|---|
| `GET /runs?status=&branch=` | `read_list_runs` | read |
| `GET /failures?run_id=&suite=&status=&signature=&test_name=&cluster_id=` | `read_list_failures` | read |
| `GET /failures/{id}` | `read_get_failure_detail` | read |
| `POST /failures/cluster` | `write_cluster_failures` | write |
| `POST /tests/quarantine` | `write_quarantine_test` | write |
| `POST /runs/{id}/regression-verdict` | `write_set_regression_verdict` | write |
| `POST /triage-notes` | `write_add_triage_note` | write |

Deliberately NOT exposed: any delete endpoint — exposure is a safety
decision. Writes are confirm-gated by the factory, exactly like
TicketDesk's. Internal-only routes: `GET /health`, `POST /admin/reset`.

## Seed data

6 nightly runs, 25 failures across 5 suites (checkout, auth, search,
payments, notifications), planted so the Reviewer's deterministic checks
have exactly one right answer (see `seed.py`): 3 genuinely flaky tests
(≥3 failures with a pass after the first failure), 3 hard regressions
(fail from some run on, never pass again), 1 brand-new signature in the
overnight run (run 6), and 2 intermittent tests below the flaky threshold
that must NOT be quarantined.

## Jobs pack & checks

`jobs.json` — the three job templates the Manager can post (cluster the
overnight failures · quarantine the flaky tests · regression verdict for
the overnight run), each with its credit budget and deterministic
acceptance criterion. `checks.py` implements the checks in the same
finding shape as the TicketDesk verifier. `department.json` is the
manifest the integration step consumes (tool specs for the direct-mode
layer, reset behaviour, integration notes).
