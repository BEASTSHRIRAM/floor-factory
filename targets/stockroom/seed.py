"""Seed data for StockRoom — the demo inventory dataset.

15 items, exactly 4 of them below the default reorder threshold of 10
(ids 3, 6, 9, 14 — quantities 3, 5, 0, 8), plus 4 pending purchase orders
(3 of them for low-stock items, so a reorder job has something to check).

All timestamps are computed relative to seed time so the dataset is
reproducible whenever seed.py / reset.py runs.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stockroom.db")

DEFAULT_THRESHOLD = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sku               TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    category          TEXT NOT NULL DEFAULT 'general',
    quantity          INTEGER NOT NULL DEFAULT 0,
    reorder_threshold INTEGER NOT NULL DEFAULT 10,
    unit              TEXT NOT NULL DEFAULT 'pcs',
    location          TEXT NOT NULL DEFAULT '',
    updated_at        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL REFERENCES items(id),
    quantity    INTEGER NOT NULL,
    supplier    TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',  -- pending | received | cancelled
    created_at  TEXT NOT NULL,
    expected_at TEXT
);
"""

# Each item: sku, name, category, quantity, reorder_threshold, unit, location
ITEMS = [
    ("SKU-001", "Wireless Mouse", "peripherals", 42, 10, "pcs", "A1"),
    ("SKU-002", "Mechanical Keyboard", "peripherals", 27, 10, "pcs", "A1"),
    ("SKU-003", "USB-C Cable 1m", "cables", 3, 10, "pcs", "A2"),          # LOW
    ("SKU-004", "HDMI Cable 2m", "cables", 64, 10, "pcs", "A2"),
    ("SKU-005", "Laptop Stand", "accessories", 18, 10, "pcs", "B1"),
    ("SKU-006", "AA Batteries (4-pack)", "consumables", 5, 10, "packs", "B2"),  # LOW
    ("SKU-007", "Printer Paper A4", "consumables", 120, 10, "reams", "B2"),
    ("SKU-008", "27-inch Monitor", "displays", 11, 10, "pcs", "C1"),
    ("SKU-009", "Webcam 1080p", "peripherals", 0, 10, "pcs", "A1"),       # LOW (out of stock)
    ("SKU-010", "Noise-cancelling Headphones", "audio", 15, 10, "pcs", "C2"),
    ("SKU-011", "USB Hub 7-port", "peripherals", 33, 10, "pcs", "A3"),
    ("SKU-012", "Ergonomic Chair", "furniture", 12, 10, "pcs", "D1"),
    ("SKU-013", "Standing Desk Frame", "furniture", 20, 10, "pcs", "D1"),
    ("SKU-014", "Ethernet Cable 5m", "cables", 8, 10, "pcs", "A2"),       # LOW
    ("SKU-015", "External SSD 1TB", "storage", 25, 10, "pcs", "C3"),
]

# Each order: item index (1-based into ITEMS), quantity, supplier, status, days_ago, expected_in_days
ORDERS = [
    (3, 100, "CableWorld", "pending", 2, 3),      # restock for low USB-C cables
    (6, 200, "PowerPlus", "pending", 1, 5),       # restock for low batteries
    (9, 50, "CamSupply Co", "pending", 3, 2),     # restock for out-of-stock webcams
    (1, 25, "PeriphMart", "pending", 4, 6),       # routine top-up, item not low
    (8, 10, "DisplayHub", "received", 20, -13),   # already received — not pending
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def seed(db_path: str = DB_PATH) -> int:
    """(Re)create the database with the seeded dataset. Returns item count."""
    if os.path.exists(db_path):
        os.remove(db_path)
    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        for sku, name, category, qty, threshold, unit, location in ITEMS:
            conn.execute(
                """INSERT INTO items
                   (sku, name, category, quantity, reorder_threshold, unit,
                    location, updated_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (sku, name, category, qty, threshold, unit, location, _iso(now)),
            )
        for item_idx, qty, supplier, status, days_ago, expected_in in ORDERS:
            conn.execute(
                """INSERT INTO orders
                   (item_id, quantity, supplier, status, created_at, expected_at)
                   VALUES (?,?,?,?,?,?)""",
                (item_idx, qty, supplier, status,
                 _iso(now - timedelta(days=days_ago)),
                 _iso(now + timedelta(days=expected_in))),
            )
        conn.commit()
        return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"Seeded {n} items into {DB_PATH}")
