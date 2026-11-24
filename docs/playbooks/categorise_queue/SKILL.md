---
name: floor-categorise_queue
description: Categorise the uncategorised queue — THE FLOOR job family 'categorise_queue' (bookkeeping, server bookkeeping).
---

# Categorise the uncategorised queue

Job family `categorise_queue` · department `bookkeeping` · tool server `bookkeeping` · budget ₡120.

## When to Use

Work the uncategorised queue: assign every transaction older than 7 days a category from the chart of accounts, using its payee and memo. Recent transactions (7 days or younger) may be left for next cycle, but nothing old may remain uncategorised.

## Procedure

1. List the uncategorised transactions.
2. Categorise each transaction against the chart of accounts.
3. Re-list and confirm no uncategorised transactions remain.

## Pitfalls

- The Reviewer rejects the job when this does not hold: No uncategorised transaction older than 7 days remains (GET /transactions/uncategorised ages all <= 7 days)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- No uncategorised transaction older than 7 days remains (GET /transactions/uncategorised ages all <= 7 days)
