---
name: floor-audit_top_pages
description: Audit the top landing pages — THE FLOOR job family 'audit_top_pages' (seo, server seo).
---

# Audit the top landing pages

Job family `audit_top_pages` · department `seo` · tool server `seo` · budget ₡120.

## When to Use

Run the deterministic on-page audit over every landing page of the site and save one audit report (scope 'landing_pages') recording each page's issues exactly as the audit rules derive them.

## Procedure

1. List the site's landing pages.
2. Run the deterministic audit on each landing page and collect its issues.
3. Save one audit report (scope 'landing_pages') recording every page's issues exactly as audited.
4. Re-read the saved reports and confirm the latest covers exactly the landing pages.

## Pitfalls

- The Reviewer rejects the job when this does not hold: An audit report is saved covering exactly the site's landing pages
- The Reviewer rejects the job when this does not hold: The report's findings for every page exactly match the deterministic audit rules recomputed from live page data (missing title/meta/H1, thin content under 300 words, slow template over 2500 ms)

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- An audit report is saved covering exactly the site's landing pages
- The report's findings for every page exactly match the deterministic audit rules recomputed from live page data (missing title/meta/H1, thin content under 300 words, slow template over 2500 ms)
