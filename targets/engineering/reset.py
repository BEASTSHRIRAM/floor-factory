#!/usr/bin/env python3
"""Reset Engineering to the exact seeded demo state.

Deletes engineering.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    n = seed.seed()
    print(f"Engineering reset: {n} issues restored in {seed.DB_PATH}")
