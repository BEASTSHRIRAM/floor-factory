#!/usr/bin/env python3
"""Reset QADesk to the exact seeded demo state.

Deletes qa.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    out = seed.seed()
    print(f"QADesk reset: {out['runs']} runs and {out['failures']} failures "
          f"restored in {seed.DB_PATH}")
