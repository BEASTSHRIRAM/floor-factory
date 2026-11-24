---
name: floor-draft_qualified_outreach
description: Draft outreach for qualified accounts — THE FLOOR job family 'draft_qualified_outreach' (sdr, server sdr).
---

# Draft outreach for qualified accounts

Job family `draft_qualified_outreach` · department `sdr` · tool server `sdr` · budget ₡140.

## When to Use

For every lead in stage 'qualified' without a draft: draft a personalised outreach message via draft_outreach that references at least one stored, account-specific signal (funding, hiring, expansion, current CRM, web engagement, tech fit). Drafts only — nothing is sent; there is no send tool.

## Procedure

1. List the leads in stage 'qualified' that have no outreach draft.
2. Read each account's buying signals.
3. Draft a personalised outreach message that references a real signal from the account.
4. Confirm every qualified lead has a draft.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every qualified lead has a stored outreach draft
- The Reviewer rejects the job when this does not hold: Every qualified lead's draft references at least one account-specific signal (deterministic phrase match against the account's stored tech_signals)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every qualified lead has a stored outreach draft
- Every qualified lead's draft references at least one account-specific signal (deterministic phrase match against the account's stored tech_signals)
