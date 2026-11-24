#!/usr/bin/env python3
"""Reset Bookkeeping to the exact seeded demo state.

Deletes bookkeeping.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    n = seed.seed()
    print(f"Bookkeeping reset: {n} transactions restored in {seed.DB_PATH}")
