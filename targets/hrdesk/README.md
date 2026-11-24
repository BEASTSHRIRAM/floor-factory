# HRDesk (THE FLOOR — HR department workplace)

A deliberately ordinary ATS-lite system of record — candidates, interview
schedules, onboarding checklists — onboarded as a department workplace the
same way TicketDesk is the Support workplace: one real system, exposed to
agents only through a Synapse-shaped MCP tool allowlist (the department
charter). Department manifest: `manifest.json` (id `hr`, port 8107).

**Platform rule — the hiring decision stays human.** There is deliberately
no hire/reject tool and no delete tool here. `screen_candidate` records a
rubric-scored *recommendation* (the score and verdict are computed by
HRDesk from the role's stated rubric — required skills present/absent —
never supplied by the caller). Whether anyone is hired is a human
decision, taken outside the agent flow.

## Run

```bash
pip install -r requirements.txt
python3 seed.py                  # create hrdesk.db with the seeded dataset
uvicorn app:app --port 8107      # serve on :8107
python3 reset.py                 # restore the exact seeded state at any time
python3 run_job.py all           # one+ jobs end-to-end in direct mode, with checks
```

(Or `POST /admin/reset` while the server is running.)

## Exposed API (the Synapse Auto allowlist)

| Tool (surface name) | Method & path | Effect |
|---|---|---|
| `list_candidates` | `GET /candidates?stage=&role=` | read |
| `get_candidate` | `GET /candidates/{id}` | read |
| `screen_candidate` | `POST /candidates/{id}/screen` | write, confirm-gated |
| `schedule_interview` | `POST /candidates/{id}/interviews` | write, confirm-gated; 422 unless screening passed the rubric threshold |
| `list_onboarding` | `GET /onboarding` | read |
| `complete_onboarding_step` | `POST /onboarding/{id}/steps/{step_key}/complete` | write, confirm-gated |
| `add_hr_note` | `POST /candidates/{id}/notes` | write, confirm-gated |
| `stats_summary` | `GET /stats/summary` | read (manager intake scan, mirrors TicketDesk) |

In the MCP server file the tools carry the factory's `read_`/`write_`
prefixes (`read_list_candidates`, `write_screen_candidate`, …) so the
confirmation gate can classify by name, exactly as with TicketDesk.

Deliberately NOT exposed: any hire/reject endpoint (the decision stays
human) and any delete endpoint — exposure is a safety decision.

## Jobs pack (`jobs.py`)

| Job | Budget | Deterministic Reviewer check |
|---|---|---|
| Screen the new applicant batch | ₡150 | Every candidate's stored screening score + verdict exactly match a recomputation of the role rubric — off-rubric verdicts fail |
| Schedule interviews for screening passers | ₡120 | Interviews exist exactly for rubric passers; none below threshold |
| Complete onboarding paperwork for this week's joiners | ₡130 | Each joiner's completed steps == exactly their required-documents list |

## Seed data

3 roles with stated rubrics (Support Engineer ≥60, Backend Developer ≥75,
QA Engineer ≥67) and 12 candidates: 5 `applied` (the unscreened batch),
2 `screening` (rubric-consistent: 1 pass, 1 hold), 2 `interview`
(pass + scheduled), 3 `onboarding` joiners whose required-document
checklists are partially done. See `seed.py`.

## Synapse onboarding status

`mcp_server.py` is a generated-style stand-in for
`synapse build --local --auto`, identical in shape to TicketDesk's — the
Synapse CLI is not installed on this VM (an npx install fails in
node-gyp-build), which is the same reason TicketDesk/StockRoom ship
stand-ins. The exact `synapse build` command to regenerate it is recorded
in `manifest.json` under `mcp.synapse_note`. The direct-mode tool layer
(`direct_client.py`, the `FLOOR_MCP_MODE=direct` path) works today and is
what `run_job.py` verifies against.
