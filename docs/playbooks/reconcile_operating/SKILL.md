---
name: floor-reconcile_operating
description: Reconcile the operating account — THE FLOOR job family 'reconcile_operating' (bookkeeping, server bookkeeping).
---

# Reconcile the operating account

Job family `reconcile_operating` · department `bookkeeping` · tool server `bookkeeping` · budget ₡110.

## When to Use

Reconcile the Operating Account against its bank statement. Compute the delta between the recorded balance and the statement balance, work out what explains it, and record a reconciliation finance note stating the delta and its cause. Reconciliation explains differences — it never moves money.

## Procedure

1. Reconcile the operating account against its statement.
2. Investigate every discrepancy the reconciliation surfaces.
3. Leave a finance note explaining each discrepancy.
4. Confirm the reconciliation delta is fully explained.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Reconciliation delta computed correctly (statement - recorded = +751) and a reconciliation note recording the delta and its explanation exists for the account

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Reconciliation delta computed correctly (statement - recorded = +751) and a reconciliation note recording the delta and its explanation exists for the account
