#!/usr/bin/env python3
"""Run ONE HR job end-to-end in direct mode (FLOOR_MCP_MODE=direct path).

Resets HRDesk to the seeded state, then runs the 'screen_batch' job
through direct_client.DirectToolClient (writes pass the confirmation
gate, policy auto-approve by default), verifies with the deterministic
Reviewer checks in jobs.py, and also runs the other two jobs so the
whole pack is exercised. Prints a JSON summary.

Usage:  python3 run_job.py [screen_batch|schedule_interviews|onboarding_paperwork|all]
The HRDesk app must be running on :8107 (or $HRDESK_URL).
"""
from __future__ import annotations

import json
import sys

import seed as seed_module
from direct_client import DirectToolClient
import jobs as jobs_module


def main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "screen_batch"
    n = seed_module.seed()
    print(f"HRDesk reset: {n} candidates restored")
    client = DirectToolClient()
    stats = client.call_tool("read_stats_summary", {})
    print(f"intake scan: {json.dumps(stats)}")
    keys = list(jobs_module.FAMILIES_BY_KEY) if which == "all" else [which]
    results = []
    for key in keys:
        result = jobs_module.run_job(client, key)
        results.append(result)
        print(json.dumps(result, indent=2))
    gate = client.confirmations
    print(f"confirmation gate: {len(gate)} write(s), "
          f"all approved by policy: {all(g['approved'] for g in gate)}")
    ok = all(r["verdict"] == "accept" for r in results)
    print("OVERALL:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
