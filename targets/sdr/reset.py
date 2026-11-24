#!/usr/bin/env python3
"""Reset the SDR workplace to the exact seeded demo state.

Deletes sdr.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    counts = seed.seed()
    print(f"SDR workplace reset: {counts['accounts']} accounts and "
          f"{counts['leads']} leads restored in {seed.DB_PATH}")
