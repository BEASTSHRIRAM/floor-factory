---
name: floor-categories
description: Normalise ticket categories — THE FLOOR job family 'categories' (support, server ticketdesk).
---

# Normalise ticket categories

Job family `categories` · department `support` · tool server `ticketdesk` · budget ₡130.

## When to Use

Audit ticket categories against the canonical set (billing, login, technical, product, account, general). TicketDesk exposes no category-edit tool, so normalisation is done by folding variants (case/typo aliases) and leaving a category-audit comment on every live ticket whose raw category is a variant.

## Procedure

1. List all tickets; skip closed ones.
2. Fold each raw category (case/typo variants) into the canonical set.
3. Leave a category-audit comment on every live ticket whose raw category is a variant.
4. Re-list and confirm the folded categories are a subset of the canonical set.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Distinct categories of live (non-closed, non-merged) tickets, folded case-insensitively with typo aliases, are a subset of the canonical set

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Distinct categories of live (non-closed, non-merged) tickets, folded case-insensitively with typo aliases, are a subset of the canonical set
