---
name: floor-quarantine_flaky
description: Quarantine the flaky tests — THE FLOOR job family 'quarantine_flaky' (qa, server qa).
---

# Quarantine the flaky tests

Job family `quarantine_flaky` · department `qa` · tool server `qa` · budget ₡130.

## When to Use

Work out which tests are genuinely flaky from their recorded pass/fail history (failing intermittently — at least 3 failures with a pass after the first failure) and quarantine exactly those tests. Consistent regressions and one-off failures must NOT be quarantined; they are real signal.

## Procedure

1. Read the failure history across runs.
2. Derive the flaky set: tests with at least 3 failures and at least one pass after their first failure.
3. Quarantine exactly those tests, each with the flakiness reason recorded.
4. Leave a triage note on each quarantined test.
5. Confirm the quarantined set equals the derived flaky set — no more, no fewer.

## Pitfalls

- The Reviewer rejects the job when this does not hold: The set of quarantined tests is exactly the set of tests failing intermittently (>= 3 failures with at least one pass after the first failure) in the recorded history — none missing, none extra

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- The set of quarantined tests is exactly the set of tests failing intermittently (>= 3 failures with at least one pass after the first failure) in the recorded history — none missing, none extra
