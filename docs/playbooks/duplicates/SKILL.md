---
name: floor-duplicates
description: Merge the duplicates — THE FLOOR job family 'duplicates' (support, server ticketdesk).
---

# Merge the duplicates

Job family `duplicates` · department `support` · tool server `ticketdesk` · budget ₡140.

## When to Use

Collapse every duplicate ticket group into its canonical ticket via the merge tool; duplicates must not remain.

## Procedure

1. Fetch the duplicate groups.
2. For each group, keep the lowest ticket id as the canonical ticket.
3. Merge every other ticket in the group into the canonical one.
4. Re-fetch duplicate groups and confirm none remain.

## Pitfalls

- The Reviewer rejects the job when this does not hold: GET /tickets/duplicates returns no groups

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- GET /tickets/duplicates returns no groups
