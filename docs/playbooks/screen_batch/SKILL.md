---
name: floor-screen_batch
description: Screen the new applicant batch — THE FLOOR job family 'screen_batch' (hr, server hrdesk).
---

# Screen the new applicant batch

Job family `screen_batch` · department `hr` · tool server `hrdesk` · budget ₡150.

## When to Use

Screen every candidate still in the 'applied' stage. For each one, record a screening through the screen tool (the rubric score and verdict are computed by HRDesk from the role's stated required skills) with notes that cite which required skills are present and which are absent. Screening is a recommendation only — the hiring decision stays human.

## Procedure

1. List the candidates awaiting screening.
2. Screen each candidate against the role rubric.
3. Record the screening outcome for every candidate.
4. Confirm the whole batch is screened.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every candidate has a screening record whose stored score and verdict exactly match a recomputation of the role's rubric (required skills present/absent) — off-rubric verdicts fail

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every candidate has a screening record whose stored score and verdict exactly match a recomputation of the role's rubric (required skills present/absent) — off-rubric verdicts fail
