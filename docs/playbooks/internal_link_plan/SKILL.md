---
name: floor-internal_link_plan
description: Internal-link fix plan for orphan pages — THE FLOOR job family 'internal_link_plan' (seo, server seo).
---

# Internal-link fix plan for orphan pages

Job family `internal_link_plan` · department `seo` · tool server `seo` · budget ₡110.

## When to Use

Compute the site's orphan pages (non-root pages with zero inbound internal links) from the link graph and save an internal-link fix plan that links every orphan from the home page, using each orphan's H1 as the anchor text. The plan is a record; the site's links do not change.

## Procedure

1. List the site's pages and its existing internal links.
2. Compute the orphan set: non-root pages with zero inbound links.
3. Save a link plan linking every orphan from the home page, anchored on each orphan's H1.
4. Re-read the saved plans and confirm the latest plan's targets equal the orphan set.

## Pitfalls

- The Reviewer rejects the job when this does not hold: A link plan is saved whose target set is exactly the computed orphan set (non-root pages with zero inbound internal links)
- The Reviewer rejects the job when this does not hold: Every page referenced by the plan exists in the seeded site and no planned link points a page at itself

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- A link plan is saved whose target set is exactly the computed orphan set (non-root pages with zero inbound internal links)
- Every page referenced by the plan exists in the seeded site and no planned link points a page at itself
