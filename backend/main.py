"""Campus Customs API.

Serves the product catalogue (with per-size stock) and product images from
data/campus_customs.db, accounts (auth.py), saved carts (cart.py), and the
shop chatbot (agent.py, a PydanticAI agent).

Run from this backend/ folder (with the venv active):
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import numpy as np
from PIL import Image

import agent
import db
import auth
import cart
import config
import history
import tools
from db import ROOT, all_products, cache_stats, get_product as db_get_product, migrate
from models import ChatHistoryMessage, ChatReply, ChatRequest, Product, User

log = logging.getLogger("campus_customs")

IMAGES_DIR = ROOT / "data" / "products"
IMAGE_CACHE = Path(__file__).resolve().parent / ".image_cache"

# garment_type values are inconsistent (22 labels), so "warm" is matched by keyword.
WARM_KEYWORDS = ("hood", "sweatshirt", "crewneck", "fleece", "jacket", "zip", "mockneck")


# The data pack is local-only (not in git): hw4/data/campus_customs.db + hw4/data/products/.
_missing = [str(p) for p in (db.DB_PATH, IMAGES_DIR) if not p.exists()]
if _missing:
    raise SystemExit(f"Data pack not found: {', '.join(_missing)}. Put campus_customs.db and products/ in hw4/data/ (see README.md).")

migrate()  # adds the sessions / cart_items tables if they don't exist yet

app = FastAPI(title="Campus Customs API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/images/original", StaticFiles(directory=IMAGES_DIR), name="original-images")
db.MODEL_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
# Reviewed AI on-model photos (Problem 10); must be mounted before the /images/{filename} route.
app.mount("/images/on-model", StaticFiles(directory=db.MODEL_PHOTOS_DIR), name="on-model-photos")
app.include_router(auth.router)
app.include_router(cart.router)


def _edge_span(is_bar: np.ndarray) -> tuple[int, int]:
    """First/last index that is not a dark bar (bars only removed from the edges)."""
    keep = np.flatnonzero(~is_bar)
    return (int(keep[0]), int(keep[-1]) + 1) if keep.size else (0, is_bar.size)


def clean_image(src: Path, dest: Path) -> None:
    """Trim black bars/frames baked into many catalogue photos, then pad back to a
    square using the photo's own background colour. Originals are never modified."""
    rgb = np.asarray(Image.open(src).convert("RGB"))
    dark = rgb.mean(axis=2) < 40
    # A row/column counts as a bar when it is almost entirely dark (tolerates JPEG noise).
    top, bottom = _edge_span(dark.mean(axis=1) > 0.97)
    left, right = _edge_span(dark.mean(axis=0) > 0.97)
    rgb = rgb[top:bottom, left:right]

    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = tuple(int(v) for v in np.median(border, axis=0))

    h, w = rgb.shape[:2]
    side = int(max(w, h) * 1.08)  # small breathing room around the garment
    canvas = Image.new("RGB", (side, side), bg)
    canvas.paste(Image.fromarray(rgb), ((side - w) // 2, (side - h) // 2))
    dest.parent.mkdir(exist_ok=True)
    canvas.save(dest, "JPEG", quality=90)


@app.get("/images/{filename}")
def product_image(filename: str) -> FileResponse:
    src = IMAGES_DIR / Path(filename).name  # .name blocks path traversal
    if not src.is_file():
        raise HTTPException(status_code=404, detail="Image not found")
    dest = IMAGE_CACHE / src.name
    if not dest.exists() or dest.stat().st_mtime < src.stat().st_mtime:
        clean_image(src, dest)
    # no-cache = revalidate via ETag, so re-cleaned images show up immediately.
    return FileResponse(dest, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


SORTS = {
    "featured": None,  # search relevance for q, otherwise name with sold-out items last
    "price_asc": lambda p: (p.price, p.name),
    "price_desc": lambda p: (-p.price, p.name),
    "name": lambda p: p.name,
    "stock": lambda p: (-sum(s.quantity for s in p.sizes), p.name),
}


@app.get("/api/products", response_model=list[Product])
def list_products(
    q: str | None = Query(None, description="Search text, same engine as the agent's search_products"),
    category: str | None = Query(None, description="hoodie | crewneck | t-shirt | quarter-zip | jacket | long sleeve"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    size: str | None = Query(None, description="Only products with this size in stock"),
    in_stock: bool = Query(False, description="Only products with at least one size in stock"),
    sort: str = Query("featured", description="featured | price_asc | price_desc | name | stock"),
) -> list[Product]:
    """All products, or a filtered/sorted view of them (Products page filters, Problem 9).

    q/max_price/size use the agent's own search engine, so the chat's "View all matches"
    link lands on exactly the result set the agent searched; category uses the same
    category rules as the agent's search.
    """
    if category and category not in tools.CATEGORIES:
        raise HTTPException(status_code=422, detail=f"Unknown category. Use one of: {', '.join(tools.CATEGORIES)}.")
    if sort not in SORTS:
        raise HTTPException(status_code=422, detail=f"Unknown sort. Use one of: {', '.join(SORTS)}.")
    try:
        products = tools.find_products(q or "", max_price, size) if (q or max_price is not None or size) else all_products()
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid search (check the size: XS, S, M, L, XL, XXL).")
    if category:
        products = [p for p in products if tools._in_category(p, {category})]
    if min_price is not None:
        products = [p for p in products if p.price >= min_price]
    if in_stock:
        products = [p for p in products if p.in_stock]
    if SORTS[sort]:
        products = sorted(products, key=SORTS[sort])
    elif not q:
        products = sorted(products, key=lambda p: not p.in_stock)  # stable: name order, sold-out last
    return products


@app.get("/api/products/recommended", response_model=list[Product])
def recommended(limit: int = Query(12, ge=1, le=50)) -> list[Product]:
    """Cold-weather picks for the home page: warm garments with stock available."""
    groups: dict[str, list[Product]] = {}
    for p in all_products():
        kind = next((k for k in WARM_KEYWORDS if k in p.garment_type.lower()), None)
        if p.in_stock and kind:
            groups.setdefault(kind, []).append(p)
    for items in groups.values():
        items.sort(key=lambda p: sum(s.quantity for s in p.sizes), reverse=True)
    # Round-robin across garment kinds so the carousel isn't all one style.
    picks: list[Product] = []
    while len(picks) < limit and any(groups.values()):
        for items in groups.values():
            if items and len(picks) < limit:
                picks.append(items.pop(0))
    return picks


@app.get("/api/products/{product_id}", response_model=Product)
def get_product(product_id: str) -> Product:
    found = db_get_product(product_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return found


@app.post("/api/chat", response_model=ChatReply)
async def chat(req: ChatRequest, user: User | None = Depends(auth.current_user_optional)) -> ChatReply:
    """Website chat → PydanticAI shop agent.

    Guests: stateless (the widget sends recent turns). Logged-in shoppers: identity comes
    from the session's account, history is replayed from chat_messages, and the new
    exchange is saved there.
    """
    shopper = auth.shopper_profile(user.id) if user else None
    turns = history.recent_turns(user.id) if user else req.history
    try:
        reply = await agent.run_chat(req.message.strip(), turns, shopper, req.page)
    except agent.MissingApiKey as e:
        log.error("%s", e)
        raise HTTPException(status_code=503, detail="The assistant isn't configured yet (missing API key).")
    except Exception:
        log.exception("Agent run failed")
        raise HTTPException(status_code=502, detail="The assistant hit a snag. Please try again in a moment.")
    if user:
        history.save_exchange(user.id, req.message.strip(), reply)
        reply.saved = True
    return reply


@app.get("/api/chat/history", response_model=list[ChatHistoryMessage])
def chat_history(user: User = Depends(auth.current_user)) -> list[ChatHistoryMessage]:
    """The logged-in shopper's saved conversation (oldest first). Cards are rebuilt from live data."""
    return [
        ChatHistoryMessage(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            products=agent.product_cards(m.product_ids) if m.role == "assistant" else [],
            search=m.search,
        )
        for m in history.load(user.id)
    ]


@app.delete("/api/chat/history", status_code=204)
def clear_chat_history(user: User = Depends(auth.current_user)) -> None:
    """Start over: deletes the shopper's own saved messages."""
    history.clear(user.id)


@app.get("/api/chat/status")
def chat_status() -> dict:
    """Quick check that the agent can be loaded (never returns the key itself)."""
    return {
        "routing": {
            "fast": {"model": agent.FAST_MODEL, "api": "chat.completions", "reasoning_effort": "none"},
            "smart": {"model": agent.SMART_MODEL, "api": "responses", "reasoning_effort": agent.SMART_REASONING},
        },
        "limits": {
            "message_chars": config.MAX_MESSAGE_CHARS,
            "history_turn_chars": config.MAX_HISTORY_TURN_CHARS,
            "history_turns_accepted": config.MAX_HISTORY_TURNS_ACCEPTED,
            "history_messages": agent.MAX_HISTORY_MESSAGES,
            "tool_calls_per_turn": agent.MAX_TOOL_CALLS_PER_TURN,
            "model_requests_per_turn": config.MAX_MODEL_REQUESTS_PER_TURN,
            "tool_results": {
                "search_products": tools.MAX_SEARCH_RESULTS,
                "suggest_alternatives": tools.MAX_ALTERNATIVES,
                "lookup_candidates": tools.MAX_CANDIDATES,
                "not_found_suggestions": tools.MAX_SUGGESTIONS,
                "saved_chats": tools.MAX_SAVED_CHATS,
                "saved_chat_chars": tools.MAX_SAVED_CHAT_CHARS,
                "query_chars": tools.MAX_QUERY_CHARS,
            },
        },
        "cache": {"ttl_seconds": db.CACHE_TTL, **cache_stats},
        "audit_trail": str(agent.audit.AUDIT_TRAIL_PATH.relative_to(db.ROOT)),
        "model": agent.MODEL_NAME,
        "gateway": agent.PORTKEY_BASE_URL,
        "api_key_configured": agent.api_key_configured(),
        "prompt_file": str(agent.PROMPT_PATH.relative_to(agent.BACKEND)),
    }
