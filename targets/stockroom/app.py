"""StockRoom — a tiny internal inventory API.

THE FLOOR's second target system (ARCHITECTURE §6.2). Plain FastAPI + its
own SQLite file. THE FLOOR never modifies this code; agents only reach it
through Synapse-generated MCP tools.

Run:   uvicorn app:app --port 8102
Seed:  python3 seed.py     (creates stockroom.db with the demo dataset)
Reset: python3 reset.py    (deletes stockroom.db and reseeds)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import seed as seed_module

DB_PATH = seed_module.DB_PATH

app = FastAPI(title="StockRoom", version="1.0.0")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_item_or_404(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"item {item_id} not found")
    return row


# --------------------------------------------------------------------------
# request bodies
# --------------------------------------------------------------------------

class AdjustBody(BaseModel):
    delta: int                      # +ve = stock in, -ve = stock out
    reason: str = ""


# --------------------------------------------------------------------------
# exposed API (the Synapse Auto allowlist — ARCHITECTURE §6.2)
# NOTE: /items/low-stock is declared BEFORE /items/{item_id} so FastAPI
# does not swallow "low-stock" as an item id. In the live demo this
# endpoint is the one added on stage before `synapse build --discover`
# (see README) — it ships in the code so the finale is rehearsable.
# --------------------------------------------------------------------------

@app.get("/items")
def list_items(
    category: Optional[str] = Query(default=None),
    location: Optional[str] = Query(default=None),
):
    """List inventory items, optionally filtered by category or location."""
    sql = "SELECT * FROM items WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if location:
        sql += " AND location = ?"
        params.append(location)
    sql += " ORDER BY id"
    conn = _conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        return {"items": [dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


def _low_stock(threshold: int) -> dict:
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT * FROM items WHERE quantity < ? ORDER BY quantity, id",
            (threshold,),
        ).fetchall()
        items = []
        for r in rows:
            d = dict(r)
            d["shortfall"] = threshold - d["quantity"]
            items.append(d)
        return {"items": items, "count": len(items), "threshold": threshold}
    finally:
        conn.close()


@app.get("/items/low-stock")
def low_stock(threshold: int = Query(default=seed_module.DEFAULT_THRESHOLD, ge=0)):
    """Items whose quantity is below the given threshold (reorder list)."""
    return _low_stock(threshold)


@app.get("/items/{item_id}")
def get_item(item_id: int):
    """Fetch one inventory item by id."""
    conn = _conn()
    try:
        return dict(_get_item_or_404(conn, item_id))
    finally:
        conn.close()


@app.post("/items/{item_id}/adjust")
def adjust_item(item_id: int, body: AdjustBody):
    """Adjust an item's quantity by delta (stock in/out). Never below zero."""
    conn = _conn()
    try:
        row = _get_item_or_404(conn, item_id)
        new_qty = row["quantity"] + body.delta
        if new_qty < 0:
            raise HTTPException(
                status_code=422,
                detail=f"adjustment {body.delta} would take quantity below zero "
                       f"(current {row['quantity']})",
            )
        conn.execute(
            "UPDATE items SET quantity = ?, updated_at = ? WHERE id = ?",
            (new_qty, seed_module._iso(_now()), item_id),
        )
        conn.commit()
        return dict(_get_item_or_404(conn, item_id))
    finally:
        conn.close()


@app.get("/orders/pending")
def pending_orders():
    """Purchase orders still pending, joined with their item details."""
    conn = _conn()
    try:
        rows = conn.execute(
            """SELECT o.id AS order_id, o.item_id, o.quantity, o.supplier,
                      o.status, o.created_at, o.expected_at,
                      i.sku, i.name AS item_name, i.quantity AS item_quantity
               FROM orders o JOIN items i ON i.id = o.item_id
               WHERE o.status = 'pending' ORDER BY o.id"""
        ).fetchall()
        orders = [dict(r) for r in rows]
        return {"orders": orders, "count": len(orders)}
    finally:
        conn.close()


@app.get("/stats/summary")
def stats_summary():
    """Aggregate counts for intake scans and verification."""
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        total_units = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM items").fetchone()[0]
        out_of_stock = conn.execute(
            "SELECT COUNT(*) FROM items WHERE quantity = 0").fetchone()[0]
        categories = [r["category"] for r in conn.execute(
            "SELECT DISTINCT category FROM items ORDER BY category").fetchall()]
        pending = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]
    finally:
        conn.close()
    low = _low_stock(seed_module.DEFAULT_THRESHOLD)
    return {
        "total_items": total,
        "total_units": total_units,
        "low_stock_count": low["count"],
        "low_stock_threshold": low["threshold"],
        "out_of_stock": out_of_stock,
        "pending_orders": pending,
        "categories": categories,
    }


# --------------------------------------------------------------------------
# internal routes (NOT part of the Synapse allowlist)
# --------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/admin/reset")
def admin_reset():
    """Restore the exact seeded demo state."""
    n = seed_module.seed(DB_PATH)
    return {"reset": True, "items": n}
