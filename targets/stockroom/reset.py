#!/usr/bin/env python3
"""Reset StockRoom to the exact seeded demo state.

Deletes stockroom.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    n = seed.seed()
    print(f"StockRoom reset: {n} items restored in {seed.DB_PATH}")
