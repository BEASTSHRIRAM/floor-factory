"""Seed data for SEODash — the deliberately realistic seeded website.

One fictional storefront ("Northbeam Outfitters") with 10 pages, 8
keywords and an internal-link graph, planted so the deterministic
checks in checks.py have exactly one right answer:

  - 5 LANDING pages (the audit job's scope), with planted issues:
        /trail-running-shoes   missing meta description
        /hiking-boots          slow template (2900 ms > 2500 ms)
        /waterproof-jackets    missing H1 + thin content (180 words)
        /gift-cards            missing meta + thin content (120 words)
        /sale                  missing meta + missing H1 + thin (90 words)
  - 2 ORPHAN pages (non-root, zero inbound internal links — the
    internal-link plan's exact target set):
        /trail-shoes-vs-boots  and  /winter-layering-guide
  - 1 BRIEF keyword ("best trail running shoes for monsoon") that is
    tracked but not yet ranking and has no target page, carrying 4
    seeded competitor angles the content brief must draw from.
  - The remaining pages/keywords are clean filler with realistic
    volumes, difficulties and ranks.

Deterministic audit rules (single source of truth, mirrored by app.py's
audit endpoint and recomputed independently by checks.py):
    missing_title   title is NULL/empty
    missing_meta    meta_description is NULL/empty
    missing_h1      h1 is NULL/empty
    thin_content    word_count < 300
    slow_template   load_ms > 2500

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seo.db")

THIN_CONTENT_WORDS = 300
SLOW_TEMPLATE_MS = 2500

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    url              TEXT NOT NULL UNIQUE,
    title            TEXT,
    meta_description TEXT,
    h1               TEXT,
    word_count       INTEGER NOT NULL DEFAULT 0,
    load_ms          INTEGER NOT NULL DEFAULT 0,
    page_type        TEXT NOT NULL DEFAULT 'landing',  -- home|landing|guide
    traffic          INTEGER NOT NULL DEFAULT 0        -- monthly visits
);
CREATE TABLE IF NOT EXISTS page_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_page_id INTEGER NOT NULL REFERENCES pages(id),
    to_page_id   INTEGER NOT NULL REFERENCES pages(id),
    anchor       TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS keywords (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    term          TEXT NOT NULL UNIQUE,
    volume        INTEGER NOT NULL DEFAULT 0,
    difficulty    INTEGER NOT NULL DEFAULT 0,
    current_rank  INTEGER,                            -- NULL = not ranking
    intent        TEXT NOT NULL DEFAULT 'informational',
    target_page_id INTEGER REFERENCES pages(id)
);
CREATE TABLE IF NOT EXISTS keyword_angles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id INTEGER NOT NULL REFERENCES keywords(id),
    angle      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scope        TEXT NOT NULL,
    author       TEXT NOT NULL,
    findings_json TEXT NOT NULL,   -- [{"page_id": int, "issues": [str]}]
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS briefs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id     INTEGER NOT NULL REFERENCES keywords(id),
    title          TEXT NOT NULL,
    intent         TEXT NOT NULL,
    outline_json   TEXT NOT NULL,  -- [section title, ...]
    angles_json    TEXT NOT NULL,  -- [competitor angle, ...]
    target_page_id INTEGER REFERENCES pages(id),
    author         TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS link_plans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    author     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS link_plan_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id     INTEGER NOT NULL REFERENCES link_plans(id),
    from_page_id INTEGER NOT NULL REFERENCES pages(id),
    to_page_id   INTEGER NOT NULL REFERENCES pages(id),
    anchor       TEXT NOT NULL DEFAULT ''
);
"""

# (url, title, meta_description, h1, word_count, load_ms, page_type, traffic)
PAGES = [
    ("/", "Northbeam Outfitters — Outdoor Gear for the Western Ghats",
     "Tents, boots, shoes and jackets for Ghats weather, shipped across India.",
     "Gear up for the Ghats", 850, 900, "home", 42000),
    ("/trail-running-shoes", "Trail Running Shoes — Northbeam",
     None,
     "Trail Running Shoes", 620, 1100, "landing", 18500),
    ("/hiking-boots", "Waterproof Hiking Boots — Northbeam",
     "Waterproof hiking boots with ankle support for multi-day treks.",
     "Waterproof Hiking Boots", 540, 2900, "landing", 15200),
    ("/waterproof-jackets", "Waterproof Jackets — Northbeam",
     "3-layer waterproof jackets rated for monsoon downpours.",
     None, 180, 1000, "landing", 9800),
    ("/beginner-hiking-guide", "Beginner Hiking Guide — Northbeam Journal",
     "Everything a first-time hiker needs: fitness, gear, routes and safety.",
     "The Beginner Hiking Guide", 1240, 800, "guide", 7600),
    ("/trail-shoes-vs-boots", "Trail Shoes vs Boots — Northbeam Journal",
     "Trail shoes or hiking boots? An honest comparison by terrain and season.",
     "Trail Shoes vs Boots: The Honest Comparison", 940, 1050, "guide", 3100),
    ("/monsoon-trekking-checklist", "Monsoon Trekking Checklist — Northbeam",
     "The printable checklist our trek leads actually use in the rains.",
     "Monsoon Trekking Checklist", 260, 950, "guide", 2900),
    ("/gift-cards", "Gift Cards — Northbeam",
     None,
     "Northbeam Gift Cards", 120, 700, "landing", 6700),
    ("/winter-layering-guide", "Winter Layering Guide — Northbeam Journal",
     "Base, mid and shell: how to layer for sub-zero Himalayan nights.",
     "How to Layer for Winter Treks", 780, 1000, "guide", 2100),
    ("/sale", "Sale — Northbeam",
     None,
     None, 90, 850, "landing", 12300),
]

# (from_url, to_url, anchor) — the existing internal-link graph.
# Orphans by construction: /trail-shoes-vs-boots and /winter-layering-guide
# receive no inbound link; every other non-root page receives at least one.
LINKS = [
    ("/", "/trail-running-shoes", "Shop trail running shoes"),
    ("/", "/hiking-boots", "Shop hiking boots"),
    ("/", "/waterproof-jackets", "Shop waterproof jackets"),
    ("/", "/gift-cards", "Buy a gift card"),
    ("/", "/sale", "This season's sale"),
    ("/trail-running-shoes", "/hiking-boots", "Prefer boots? See hiking boots"),
    ("/trail-running-shoes", "/beginner-hiking-guide", "New to trails? Start here"),
    ("/hiking-boots", "/trail-running-shoes", "Lighter option: trail shoes"),
    ("/beginner-hiking-guide", "/waterproof-jackets", "A waterproof jacket is essential"),
    ("/beginner-hiking-guide", "/monsoon-trekking-checklist", "Print the monsoon checklist"),
    ("/waterproof-jackets", "/hiking-boots", "Complete the kit: hiking boots"),
    ("/sale", "/trail-running-shoes", "Trail shoes on sale"),
]

# (term, volume, difficulty, current_rank, intent, target_url or None)
KEYWORDS = [
    ("trail running shoes", 18100, 42, 7, "commercial", "/trail-running-shoes"),
    ("waterproof hiking boots", 9900, 38, 12, "commercial", "/hiking-boots"),
    ("best trail running shoes for monsoon", 2400, 21, None, "commercial", None),
    ("hiking boots vs trail shoes", 3600, 18, 9, "informational", "/trail-shoes-vs-boots"),
    ("winter layering guide", 1900, 15, 14, "informational", "/winter-layering-guide"),
    ("monsoon trekking checklist", 2900, 12, 5, "informational", "/monsoon-trekking-checklist"),
    ("buy gift cards online", 8100, 10, 3, "transactional", "/gift-cards"),
    ("waterproof jackets for women", 6600, 29, 18, "commercial", "/waterproof-jackets"),
]

# Competitor angles per keyword term (the content brief draws from these).
ANGLES = {
    "best trail running shoes for monsoon": [
        "monsoon grip test: wet-rock traction scores for 8 shoes",
        "price comparison table across 6 retailers",
        "weight per shoe chart (size 9)",
        "beginner mistakes when buying first trail shoes",
    ],
    "trail running shoes": [
        "drop and stack-height explainer with diagrams",
    ],
}

BRIEF_KEYWORD = "best trail running shoes for monsoon"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def seed(db_path: str = DB_PATH) -> dict:
    """(Re)create the database with the seeded dataset.

    Returns {"pages": n, "keywords": n, "links": n}."""
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        page_ids: dict[str, int] = {}
        for url, title, meta, h1, words, load_ms, ptype, traffic in PAGES:
            cur = conn.execute(
                "INSERT INTO pages (url, title, meta_description, h1,"
                " word_count, load_ms, page_type, traffic)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (url, title, meta, h1, words, load_ms, ptype, traffic))
            page_ids[url] = cur.lastrowid
        for from_url, to_url, anchor in LINKS:
            conn.execute(
                "INSERT INTO page_links (from_page_id, to_page_id, anchor)"
                " VALUES (?,?,?)",
                (page_ids[from_url], page_ids[to_url], anchor))
        keyword_ids: dict[str, int] = {}
        for term, volume, difficulty, rank, intent, target_url in KEYWORDS:
            cur = conn.execute(
                "INSERT INTO keywords (term, volume, difficulty,"
                " current_rank, intent, target_page_id) VALUES (?,?,?,?,?,?)",
                (term, volume, difficulty, rank, intent,
                 page_ids[target_url] if target_url else None))
            keyword_ids[term] = cur.lastrowid
        for term, angles in ANGLES.items():
            for angle in angles:
                conn.execute(
                    "INSERT INTO keyword_angles (keyword_id, angle)"
                    " VALUES (?,?)", (keyword_ids[term], angle))
        conn.commit()
        return {"pages": len(PAGES), "keywords": len(KEYWORDS),
                "links": len(LINKS)}
    finally:
        conn.close()


if __name__ == "__main__":
    out = seed()
    print(f"Seeded {out['pages']} pages, {out['keywords']} keywords and "
          f"{out['links']} internal links into {DB_PATH}")
