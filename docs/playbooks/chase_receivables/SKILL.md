---
name: floor-chase_receivables
description: Chase overdue receivables (+3/+15/+30) — THE FLOOR job family 'chase_receivables' (bookkeeping, server bookkeeping).
---

# Chase overdue receivables (+3/+15/+30)

Job family `chase_receivables` · department `bookkeeping` · tool server `bookkeeping` · budget ₡130.

## When to Use

Chase every open invoice that has crossed its chase threshold: record a reminder for each invoice 3+ days overdue. The system sets the reminder level from the band (+3 gentle, +15 firm, +30 final). Invoices not yet due — or less than 3 days overdue — must NOT be chased. Reminders are recorded drafts; no real email is sent.

## Procedure

1. List the outstanding receivables.
2. Send a payment reminder for each overdue invoice.
3. Confirm every overdue receivable has been reminded.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Reminders are recorded for exactly the open invoices past their chase thresholds, each at the correct band level, and for no others

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Reminders are recorded for exactly the open invoices past their chase thresholds, each at the correct band level, and for no others
