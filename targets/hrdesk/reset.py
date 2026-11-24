#!/usr/bin/env python3
"""Reset HRDesk to the exact seeded demo state.

Deletes hrdesk.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    n = seed.seed()
    print(f"HRDesk reset: {n} candidates restored in {seed.DB_PATH}")
