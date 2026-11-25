---
name: floor-schedule_interviews
description: Schedule interviews for screening passers — THE FLOOR job family 'schedule_interviews' (hr, server hrdesk).
---

# Schedule interviews for screening passers

Job family `schedule_interviews` · department `hr` · tool server `hrdesk` · budget ₡120.

## When to Use

For every candidate whose screening verdict is recommend_interview and who has no interview yet, schedule a panel interview. Never schedule for a candidate whose screening recommends hold — HRDesk refuses those calls, and the check verifies none exist.

## Procedure

1. List the candidates who passed screening above the rubric threshold.
2. Schedule an interview for each of them.
3. Confirm every above-threshold candidate has an interview scheduled.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every candidate whose rubric score meets the role threshold has at least one scheduled interview, and no candidate below the threshold has any interview

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every candidate whose rubric score meets the role threshold has at least one scheduled interview, and no candidate below the threshold has any interview
