---
name: floor-stale_close
description: Close the stale resolved tickets — THE FLOOR job family 'stale_close' (support, server ticketdesk).
---

# Close the stale resolved tickets

Job family `stale_close` · department `support` · tool server `ticketdesk` · budget ₡140.

## When to Use

Every ticket sitting in 'resolved' for over 7 days must be closed. A ticket may only be closed once a resolution comment exists on it; supply the missing resolution note where none exists.

## Procedure

1. List tickets in status 'resolved'.
2. For each ticket resolved 7+ days ago, open it and check for a resolution comment.
3. If no resolution comment exists, add one first.
4. Close the ticket.
5. Re-list resolved tickets and confirm no stale ones remain.

## Pitfalls

- The Reviewer rejects the job when this does not hold: No ticket remains in status 'resolved' with resolved_at older than 7 days

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- No ticket remains in status 'resolved' with resolved_at older than 7 days
