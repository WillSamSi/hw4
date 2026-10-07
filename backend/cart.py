"""Saved carts: a logged-in user's cart lives in cart_items, so it survives logout."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import current_user
from db import connect
from models import User

router = APIRouter(prefix="/api/cart", tags=["cart"])


class CartLineIn(BaseModel):
    product_id: str
    size: str
    qty: int


class CartLine(BaseModel):
    product_id: str
    name: str
    price: float
    image_url: str
    size: str
    qty: int
    max_qty: int  # units in stock right now; 0 means this size sold out since it was saved


class CartUpdate(BaseModel):
    items: list[CartLineIn]


def read_cart(conn, user_id: int) -> list[CartLine]:
    rows = conn.execute(
        """SELECT c.product_id, c.size, c.qty, k.name, k.price, k.image_file_path,
                  COALESCE(i.quantity, 0) AS stock
           FROM cart_items c
           JOIN catalogue k ON k.product_id = c.product_id
           LEFT JOIN inventory i ON i.product_id = c.product_id AND i.size = c.size
           WHERE c.user_id = ? ORDER BY c.updated_at, c.product_id""",
        (user_id,),
    ).fetchall()
    return [
        CartLine(
            product_id=r["product_id"],
            name=r["name"],
            price=r["price"],
            image_url="/images/" + Path(r["image_file_path"]).name,
            size=r["size"],
            # Keep sold-out items (qty untouched) so the UI can flag them instead of silently dropping them.
            qty=min(r["qty"], r["stock"]) if r["stock"] > 0 else r["qty"],
            max_qty=r["stock"],
        )
        for r in rows
    ]


@router.get("", response_model=list[CartLine])
def get_cart(user: User = Depends(current_user)) -> list[CartLine]:
    with closing(connect()) as conn:
        return read_cart(conn, user.id)


@router.put("", response_model=list[CartLine])
def replace_cart(update: CartUpdate, user: User = Depends(current_user)) -> list[CartLine]:
    """Replace the whole saved cart. Unknown products/sizes and qty <= 0 are ignored."""
    with closing(connect(readonly=False)) as conn:
        valid = {
            (r["product_id"], r["size"]): r["quantity"]
            for r in conn.execute("SELECT product_id, size, quantity FROM inventory")
        }
        conn.execute("DELETE FROM cart_items WHERE user_id = ?", (user.id,))
        for line in update.items:
            stock = valid.get((line.product_id, line.size))
            if stock is None or line.qty <= 0:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO cart_items (user_id, product_id, size, qty) VALUES (?, ?, ?, ?)",
                (user.id, line.product_id, line.size, min(line.qty, stock) if stock > 0 else line.qty),
            )
        conn.commit()
        return read_cart(conn, user.id)
