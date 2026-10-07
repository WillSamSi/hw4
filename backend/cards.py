"""ProductCard building, shared by the agent (reply cards) and tools (suggest_alternatives).

Cards are always built from live DB data, never written by the model.
"""

from __future__ import annotations

from db import products_by_ids
from models import Product, ProductCard

MAX_CARDS = 8
SHORT_INFO_CHARS = 90


def short_info(description: str) -> str:
    """First sentence of the description, trimmed to ~90 chars on a word boundary."""
    first = description.split(". ")[0].rstrip(".")
    if len(first) <= SHORT_INFO_CHARS:
        return first
    return first[:SHORT_INFO_CHARS].rsplit(" ", 1)[0].rstrip(",;:-") + "…"


def to_card(p: Product) -> ProductCard:
    available = [s.size for s in p.sizes if s.in_stock]
    return ProductCard(
        product_id=p.product_id,
        name=p.name,
        price=p.price,
        image_url=p.image_url,
        short_info=short_info(p.description),
        garment_type=p.garment_type,
        stock_status="sold_out" if not available else "in_stock" if len(available) == len(p.sizes) else "partly_sold_out",
        in_stock_sizes=available,
        out_of_stock_sizes=[s.size for s in p.sizes if not s.in_stock],
    )


def product_cards(product_ids: list[str]) -> list[ProductCard]:
    """Turn structured matches (IDs) into cards from live DB data; unknown IDs are dropped."""
    wanted = list(dict.fromkeys(product_ids))[:MAX_CARDS]
    return [to_card(p) for p in products_by_ids(wanted)]
