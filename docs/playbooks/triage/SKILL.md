---
name: floor-triage
description: Triage the unassigned queue — THE FLOOR job family 'triage' (support, server ticketdesk).
---

# Triage the unassigned queue

Job family `triage` · department `support` · tool server `ticketdesk` · budget ₡150.

## When to Use

Assign every unassigned TicketDesk ticket to a support agent and make sure each carries a sane priority (P1-P4).

## Procedure

1. List tickets with assignee=none.
2. Assign each ticket round-robin to the support pool (ravi, meera, sana).
3. Re-list unassigned tickets and confirm the count is zero.

## Pitfalls

- The Reviewer rejects the job when this does not hold: GET /tickets?assignee=none returns 0 tickets

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- GET /tickets?assignee=none returns 0 tickets
