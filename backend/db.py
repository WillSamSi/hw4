"""SQLite access for the Campus Customs API."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from config import CACHE_TTL_SECONDS
from models import Product, SizeStock

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CAMPUS_DB", ROOT / "data" / "campus_customs.db"))
MODEL_PHOTOS_DIR = ROOT / "data" / "model_photos"  # AI on-model photos + manifest.json (Problem 10)
SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]

# Tables added for accounts. The seed tables (catalogue, inventory, users,
# chat_messages) are left as they are.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,          -- SHA-256 of the cookie token, never the token itself
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS cart_items (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id  TEXT NOT NULL REFERENCES catalogue(product_id),
    size        TEXT NOT NULL,
    qty         INTEGER NOT NULL CHECK (qty > 0),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, product_id, size)
);
"""


def connect(readonly: bool = True) -> sqlite3.Connection:
    """Catalogue reads use a read-only connection; accounts and carts need writes."""
    uri = f"file:{DB_PATH}?mode={'ro' if readonly else 'rw'}"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate() -> None:
    with closing(connect(readonly=False)) as conn:
        conn.executescript(SCHEMA)
        # chat_messages (seed table) gets one optional column for the "View all" search spec.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "search_json" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN search_json TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")
        conn.commit()


# ---------- Catalogue access with caching ----------
#
# Both the parsed catalogue rows and the inventory (stock per size) are cached in memory for
# CACHE_TTL_SECONDS (default 60, set in hw4/.env). Trade-off: stock shown can be up to a
# minute old. Call invalidate_cache() after editing the catalogue or inventory tables.

CACHE_TTL = float(CACHE_TTL_SECONDS)

_cache: dict[str, tuple[float, object]] = {}
cache_stats = {"catalogue_hits": 0, "catalogue_misses": 0, "inventory_hits": 0, "inventory_misses": 0, "model_photos_hits": 0, "model_photos_misses": 0}


def invalidate_cache() -> None:
    _cache.clear()


def _cached(name: str, load):
    hit = _cache.get(name)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        cache_stats[f"{name}_hits"] += 1
        return hit[1]
    cache_stats[f"{name}_misses"] += 1
    value = load()
    _cache[name] = (time.monotonic(), value)
    return value


def _load_catalogue() -> list[dict]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
    return [
        {
            "product_id": r["product_id"],
            "name": r["name"],
            "garment_type": r["garment_type"],
            "description": r["description"],
            "colors": json.loads(r["colors"]),
            "search_tags": json.loads(r["search_tags"]),
            "price": r["price"],
            "image_url": "/images/" + Path(r["image_file_path"]).name,
        }
        for r in rows
    ]


def _load_inventory() -> dict[str, dict[str, int]]:
    stock: dict[str, dict[str, int]] = {}
    with closing(connect()) as conn:
        for r in conn.execute("SELECT product_id, size, quantity FROM inventory"):
            stock.setdefault(r["product_id"], {})[r["size"]] = r["quantity"]
    return stock


def _catalogue_rows() -> list[dict]:
    return _cached("catalogue", _load_catalogue)


def _live_stock() -> dict[str, dict[str, int]]:
    return _cached("inventory", _load_inventory)


def _load_model_photos() -> dict[str, str]:
    """product_id -> URL for on-model photos that passed review (reviewed: true in manifest.json)."""
    manifest = MODEL_PHOTOS_DIR / "manifest.json"
    try:
        entries = json.loads(manifest.read_text()) if manifest.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        pid: f"/images/on-model/{e['file']}"
        for pid, e in entries.items()
        if e.get("reviewed") and (MODEL_PHOTOS_DIR / e.get("file", "")).is_file()
    }


def _model_photos() -> dict[str, str]:
    return _cached("model_photos", _load_model_photos)


def _build(row: dict, by_size: dict[str, int]) -> Product:
    # Out-of-stock sizes are kept (quantity 0) so the UI can grey them out.
    sizes = [SizeStock(size=s, quantity=by_size[s], in_stock=by_size[s] > 0) for s in SIZE_ORDER if s in by_size]
    return Product(
        **row,
        sizes=sizes,
        in_stock=any(s.in_stock for s in sizes),
        total_in_stock=sum(s.quantity for s in sizes),
        model_image_url=_model_photos().get(row["product_id"]),
    )


def all_products() -> list[Product]:
    """Every product (sorted by name): cached catalogue text + live stock."""
    stock = _live_stock()
    return [_build(row, stock.get(row["product_id"], {})) for row in _catalogue_rows()]


def products_by_ids(ids: list[str] | tuple[str, ...]) -> list[Product]:
    """The requested products (unknown IDs are skipped), in the order given."""
    wanted = list(dict.fromkeys(ids))
    by_id = {row["product_id"]: row for row in _catalogue_rows() if row["product_id"] in wanted}
    if not by_id:
        return []
    stock = _live_stock()
    return [_build(by_id[i], stock.get(i, {})) for i in wanted if i in by_id]


def get_product(product_id: str) -> Product | None:
    found = products_by_ids([product_id])
    return found[0] if found else None
