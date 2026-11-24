---
name: floor-work_issue
description: Work an engineering issue and open a PR — THE FLOOR job family 'work_issue' (engineering, server engineering).
---

# Work an engineering issue and open a PR

Job family `work_issue` · department `engineering` · tool server `engineering` · budget ₡160.

## When to Use

Claim an unclaimed solvable issue in the Engineering repo, do the work described by its acceptance criteria, and open a pull-request record whose change summary addresses every acceptance keyword and touches every file the issue lists. CI runs when the PR opens — a red CI means the summary or file set does not satisfy the issue. You prepare the PR; a human merges it.

## Procedure

1. List the issues; choose an unclaimed issue that carries acceptance keywords.
2. Claim the issue in your own name.
3. Open a pull request whose change summary addresses every acceptance keyword and touches every file the issue lists.
4. Read the CI result for the PR; a red CI means the summary or file set does not satisfy the issue.
5. Leave an engineering note on the issue linking the PR. A human merges — never merge yourself.

## Pitfalls

- From the procedure itself: Leave an engineering note on the issue linking the PR. A human merges — never merge yourself.
- The Reviewer rejects the job when this does not hold: The target issue is claimed by the awarded worker
- The Reviewer rejects the job when this does not hold: A PR record exists linked to the issue, authored by the worker
- The Reviewer rejects the job when this does not hold: The PR's change summary is non-empty
- The Reviewer rejects the job when this does not hold: A CI result is recorded for the PR
- The Reviewer rejects the job when this does not hold: CI status for the PR is pass (service CI rule)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- The target issue is claimed by the awarded worker
- A PR record exists linked to the issue, authored by the worker
- The PR's change summary is non-empty
- A CI result is recorded for the PR
- CI status for the PR is pass (service CI rule)
