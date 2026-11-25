---
name: floor-flag_duplicates
description: Flag the duplicate transactions — THE FLOOR job family 'flag_duplicates' (bookkeeping, server bookkeeping).
---

# Flag the duplicate transactions

Job family `flag_duplicates` · department `bookkeeping` · tool server `bookkeeping` · budget ₡90.

## When to Use

Find every set of transactions that are exact duplicates of each other (same account, date, payee and amount) and flag each later copy as a duplicate of the earliest (canonical) one. Flagging marks rows only — nothing is deleted.

## Procedure

1. Scan the transactions for duplicate pairs.
2. Flag every duplicate transaction as a duplicate of its original.
3. Re-scan and confirm every duplicate pair is flagged.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Flagged duplicate ids exactly match the seeded duplicate set, and GET /transactions/duplicates returns no open groups

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Flagged duplicate ids exactly match the seeded duplicate set, and GET /transactions/duplicates returns no open groups
