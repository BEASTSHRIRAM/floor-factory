---
name: floor-triage_unlabelled
description: Triage the unlabelled issues — THE FLOOR job family 'triage_unlabelled' (engineering, server engineering).
---

# Triage the unlabelled issues

Job family `triage_unlabelled` · department `engineering` · tool server `engineering` · budget ₡90.

## When to Use

Find every Engineering issue with no labels and assign each one sensible labels and a priority (P1-P4) from its title and body. Crashes and money/data mismatches are P1-P2; feature requests and cosmetic asks are P3-P4.

## Procedure

1. List the unlabelled issues.
2. Read each issue's title and body; classify its labels (bug/feature, area) and priority from the content.
3. Apply the labels and priority to each issue.
4. Confirm no unlabelled issues remain.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every issue has labels and a priority assigned (unlabelled queue empty, no null priorities)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every issue has labels and a priority assigned (unlabelled queue empty, no null priorities)
