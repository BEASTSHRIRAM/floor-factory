---
name: floor-vip_save
description: VIP save: calm the angry customers — THE FLOOR job family 'vip_save' (support, server ticketdesk).
---

# VIP save: calm the angry customers

Job family `vip_save` · department `support` · tool server `ticketdesk` · budget ₡70.

## When to Use

Two customers are threatening to churn (the 'THIRD time I am writing' and 'Worst support ever' tickets). Post an ESCALATION comment on each so a senior human picks them up today.

## Procedure

1. List tickets; select the angry ones (subject contains '!!!' or 'NOW', not closed).
2. Open each and check for an existing escalation comment.
3. Post an ESCALATION comment on each angry ticket.
4. Re-check that no angry ticket lacks an escalation comment.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every angry open ticket (subject contains '!!!' or 'NOW') has at least one comment with kind='escalation'

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every angry open ticket (subject contains '!!!' or 'NOW') has at least one comment with kind='escalation'
