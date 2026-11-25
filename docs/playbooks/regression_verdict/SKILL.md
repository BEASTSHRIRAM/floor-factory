---
name: floor-regression_verdict
description: Regression verdict for the overnight run — THE FLOOR job family 'regression_verdict' (qa, server qa).
---

# Regression verdict for the overnight run

Job family `regression_verdict` · department `qa` · tool server `qa` · budget ₡110.

## When to Use

Decide whether the overnight CI run introduced a regression: compare its failures' error signatures against all earlier runs, count the failures whose signature is brand-new in this run, record the verdict with the verdict tool, and leave a triage note on the run explaining the call.

## Procedure

1. Take the latest run and list its failures.
2. Count the failures whose signature is new in this run.
3. Record the regression verdict the count implies (any new signature means regression).
4. Confirm the recorded verdict is consistent with the new-failure count.

## Pitfalls

- The Reviewer rejects the job when this does not hold: A regression verdict is recorded for the target run and is consistent with its new-failure count ('regression' iff new-failure count > 0, else 'no_regression')

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- A regression verdict is recorded for the target run and is consistent with its new-failure count ('regression' iff new-failure count > 0, else 'no_regression')
