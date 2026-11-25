---
name: floor-cluster_failures
description: Cluster the overnight failures — THE FLOOR job family 'cluster_failures' (qa, server qa).
---

# Cluster the overnight failures

Job family `cluster_failures` · department `qa` · tool server `qa` · budget ₡120.

## When to Use

Group every failure from the overnight CI run by its error signature using the cluster tool, so each failure belongs to exactly one signature cluster. Then leave a short triage note on each cluster summarising what it looks like.

## Procedure

1. List the test runs and take the latest run.
2. List that run's failures.
3. Cluster the failures by signature.
4. Leave a triage note on each cluster recording its size and signature.
5. Confirm every failure in the run belongs to a cluster whose signature matches.

## Pitfalls

- The Reviewer rejects the job when this does not hold: Every failure in the target run has a cluster assignment (cluster_id set), and each assigned cluster's signature equals the failure's own error signature

## Verification

The Reviewer runs deterministic checks against live workplace state — one finding per acceptance criterion below; a failed check is an automatic reject, and the failed findings become the worker's next lesson.

- Every failure in the target run has a cluster assignment (cluster_id set), and each assigned cluster's signature equals the failure's own error signature
