---
name: floor-sla_breach
description: SLA breach sweep + escalation — THE FLOOR job family 'sla_breach' (support, server ticketdesk).
---

# SLA breach sweep + escalation

Job family `sla_breach` · department `support` · tool server `ticketdesk` · budget ₡160.

## When to Use

Find every SLA-breached ticket and post an ESCALATION comment on each one (kind='escalation'), so the breach is formally escalated.

## Procedure

1. Fetch the SLA breach list.
2. Open each breached ticket and check for an existing escalation comment.
3. Post a comment with kind='escalation' on each breached ticket — a plain comment does NOT count.
4. Re-fetch the breaches and confirm every one carries an escalation comment.

## Pitfalls

- From the procedure itself: Post a comment with kind='escalation' on each breached ticket — a plain comment does NOT count.
- The Reviewer rejects the job when this does not hold: Every ticket returned by GET /sla/breaches has at least one comment with kind='escalation'

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every ticket returned by GET /sla/breaches has at least one comment with kind='escalation'
