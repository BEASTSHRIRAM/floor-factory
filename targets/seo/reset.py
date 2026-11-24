#!/usr/bin/env python3
"""Reset SEODash to the exact seeded demo state.

Deletes seo.db and reseeds it (same effect as POST /admin/reset,
but works without the server running).
"""
import seed

if __name__ == "__main__":
    out = seed.seed()
    print(f"SEODash reset: {out['pages']} pages, {out['keywords']} keywords "
          f"and {out['links']} internal links restored in {seed.DB_PATH}")
