---
name: floor-research_score_new_leads
description: Research and score the new-lead batch — THE FLOOR job family 'research_score_new_leads' (sdr, server sdr).
---

# Research and score the new-lead batch

Job family `research_score_new_leads` · department `sdr` · tool server `sdr` · budget ₡120.

## When to Use

For every lead in stage 'new': research its account over the stored CRM signals (research_account), compute the ICP score strictly by the department rubric, and record score + reasons via score_lead.

## Procedure

1. List the leads in stage 'new'.
2. Research each lead's account (signals, firmographics).
3. Compute the rubric score for the account.
4. Record the score and its reasons on the lead.
5. Confirm every new lead carries a rubric score.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every lead in the new batch has a score with reasons
- The Reviewer rejects the job when this does not hold: Every recorded score follows the ICP rubric (recomputed from account data)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every lead in the new batch has a score with reasons
- Every recorded score follows the ICP rubric (recomputed from account data)
