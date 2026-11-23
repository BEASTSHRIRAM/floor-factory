#!/usr/bin/env python3
"""Reset TicketDesk to the exact seeded demo state.

Deletes ticketdesk.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    n = seed.seed()
    print(f"TicketDesk reset: {n} tickets restored in {seed.DB_PATH}")
