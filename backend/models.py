"""Pydantic / PydanticAI structured types shared by the API, tools, and agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from config import MAX_HISTORY_TURN_CHARS, MAX_HISTORY_TURNS_ACCEPTED, MAX_MESSAGE_CHARS

# ---------- Catalogue ----------


class SizeStock(BaseModel):
    size: str
    quantity: int
    in_stock: bool


class Product(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    colors: list[str]
    search_tags: list[str]
    price: float
    image_url: str
    sizes: list[SizeStock]
    in_stock: bool
    total_in_stock: int = Field(default=0, description="Units on hand across all sizes (live inventory).")
    model_image_url: str | None = Field(
        default=None, description="AI-generated on-model photo (Problem 10); only set once reviewed against the real product."
    )


# ---------- Accounts ----------


class User(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str


# ---------- Chat API (website <-> FastAPI) ----------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_HISTORY_TURN_CHARS)


class PageContext(BaseModel):
    """What the shopper is looking at, sent by the website with every chat message.

    Client-supplied, so it is treated as untrusted data: product IDs are checked
    against the DB and text is length-limited before the agent sees any of it.
    """

    path: str = Field(default="/", max_length=200)
    page: Literal["home", "products", "search", "other"] = "other"
    viewing_product_id: str | None = Field(default=None, max_length=120, description="Product pop-up open right now.")
    last_viewed_product_id: str | None = Field(default=None, max_length=120, description="Most recently opened pop-up.")
    search_query: str | None = Field(default=None, max_length=100, description="Search shown on the Products page.")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # Recent turns from the widget, oldest first. Used for guests only; for logged-in
    # shoppers the server replays their saved history from the database instead.
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS_ACCEPTED)
    page: PageContext | None = None

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message is empty")
        return v


class ProductCard(BaseModel):
    """One product match rendered as a card on the website. Built from the DB, never by the model."""

    product_id: str
    name: str
    price: float
    image_url: str
    short_info: str = Field(description="One-line summary from the product description (≤ ~90 chars).")
    garment_type: str
    stock_status: Literal["in_stock", "partly_sold_out", "sold_out"]
    in_stock_sizes: list[str]
    out_of_stock_sizes: list[str]


class SearchSpec(BaseModel):
    """The catalogue search behind a reply, so the page can show *all* matches ("View all").

    Taken from the agent's actual search_products call (not from model text) and
    re-counted on the server. The front end replays it via GET /api/products.
    """

    query: str
    max_price: float | None = None
    size: str | None = None
    total_matches: int


class RouteInfo(BaseModel):
    """Which model tier answered (Problem 9 routing): for testing, logs, and the harness."""

    tier: Literal["fast", "smart"]
    model: str
    api: Literal["chat.completions", "responses"]
    reasoning_effort: str
    reason: str = Field(description="Why the router picked this tier.")
    fallback: bool = Field(default=False, description="True if the fast tier failed and the smart tier retried.")
    elapsed_ms: int = 0


class ChatReply(BaseModel):
    """API contract for POST /api/chat."""

    reply: str
    products: list[ProductCard] = Field(default_factory=list, description="Matches to show as cards, best first (≤ 8).")
    search: SearchSpec | None = Field(default=None, description="Present when the cards came from a catalogue search.")
    saved: bool = Field(default=False, description="True when this exchange was saved to the shopper's account.")
    route: RouteInfo | None = None


class ChatHistoryMessage(BaseModel):
    """One saved message, as returned by GET /api/chat/history (oldest first)."""

    id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: str = Field(description="UTC, 'YYYY-MM-DD HH:MM:SS'.")
    products: list[ProductCard] = Field(default_factory=list, description="Rebuilt from live DB data on load.")
    search: SearchSpec | None = None


# ---------- Agent (PydanticAI) ----------


class AgentReply(BaseModel):
    """The agent's structured output."""

    reply: str = Field(
        description="What to say to the shopper, in the Campus Customs voice. "
        "Short. Markdown **bold** and '- ' bullet lines are allowed."
    )
    product_ids: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Structured product matches: product_id values exactly as returned by tools, best first. "
        "The website renders them as product cards (image, name, price, short info). "
        "Up to 8 for 'what X do you have?' searches; 1-4 when discussing specific items; empty otherwise.",
    )


class ShopperProfile(BaseModel):
    """Who is chatting: read server-side from the logged-in account (users table), never from the browser."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_since: str = Field(description="Account creation date, YYYY-MM-DD.")


class PageProduct(BaseModel):
    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]


class ResolvedPage(BaseModel):
    """PageContext after validation: product IDs replaced by real catalogue entries (or dropped)."""

    path: str
    page: Literal["home", "products", "search", "other"]
    viewing: PageProduct | None = None
    last_viewed: PageProduct | None = None
    search_query: str | None = None


@dataclass
class AgentDeps:
    """Per-request context handed to the agent's instructions and tools."""

    shopper: ShopperProfile | None  # None = guest
    page: ResolvedPage | None = None

    @property
    def user_id(self) -> int | None:
        return self.shopper.user_id if self.shopper else None


StockStatus = Literal["in_stock", "low_stock", "sold_out"]
ProductStockStatus = Literal["in_stock", "partly_sold_out", "sold_out"]
LOW_STOCK_THRESHOLD = 3  # units; at or below this a size counts as "low_stock"


class ProductSummary(BaseModel):
    """Compact product view returned by search_products (discovery, not final facts)."""

    product_id: str
    name: str
    garment_type: str
    price: float
    colors: list[str]
    stock_status: ProductStockStatus
    in_stock_sizes: list[str]
    out_of_stock_sizes: list[str]
    description: str


class SearchResults(BaseModel):
    """What search_products returns to the agent."""

    query: str
    max_price: float | None
    size: str | None
    total_matches: int = Field(description="Every product matching the search (not just those returned).")
    results: list[ProductSummary] = Field(description="Best matches first, up to `limit`.")


class SizeAvailability(BaseModel):
    """Live stock for one size, straight from the inventory table."""

    size: str
    quantity: int = Field(description="Units on hand right now. 0 means sold out for now.")
    status: StockStatus


class ProductLookup(BaseModel):
    """Authoritative facts for one product: description, price, and stock (overall and per size)."""

    kind: Literal["found"] = "found"
    matched_by: Literal["product_id", "exact_name", "closest_name"]
    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    currency: Literal["USD"] = "USD"
    colors: list[str]
    stock_status: ProductStockStatus = Field(
        description="in_stock = every size available; partly_sold_out = some sizes at 0; sold_out = every size at 0"
    )
    total_in_stock: int = Field(description="Sum of units across all sizes.")
    sizes: list[SizeAvailability] = Field(description="Every size the product comes in (XS→XXL), including sold-out ones.")
    available_sizes: list[str]
    sold_out_sizes: list[str]
    requested_size: SizeAvailability | None = Field(
        default=None, description="Filled when the shopper asked about one size."
    )


class ProductCandidate(BaseModel):
    product_id: str
    name: str
    price: float


class ProductAmbiguous(BaseModel):
    """Several products match the name; the agent should ask which one the shopper means."""

    kind: Literal["ambiguous"] = "ambiguous"
    query: str
    candidates: list[ProductCandidate]


class ProductNotFound(BaseModel):
    """No product matches; we don't carry it (or the name is off). Suggestions come from search."""

    kind: Literal["not_found"] = "not_found"
    query: str
    suggestions: list[ProductCandidate]


ProductLookupResult = ProductLookup | ProductAmbiguous | ProductNotFound


class AlternativesResult(BaseModel):
    """suggest_alternatives' answer when a size (or a whole product) is sold out.

    `cards` is the same ProductCard list the website renders, so whatever the tool finds
    appears as cards on the page (the server also adds them to the reply if the agent forgets).
    """

    kind: Literal["alternatives"] = "alternatives"
    original_product_id: str
    original_name: str
    requested_size: str | None
    requested_size_quantity: int | None = Field(description="Live units of the requested size on the original (0 = sold out).")
    original_stock_status: Literal["in_stock", "partly_sold_out", "sold_out"]
    other_sizes_in_stock: list[SizeAvailability] = Field(
        description="(a) The same product in other sizes that are in stock, nearest to the requested size first."
    )
    similar_in_size: list[str] = Field(
        description="(b) product_ids of up to 3 similar products in the same category that have the requested size."
    )
    why: dict[str, str] = Field(description="product_id → short reason it's similar (e.g. 'navy · same price').")
    cards: list[ProductCard] = Field(
        description="Ready-to-show cards: the original first (if it has other sizes in stock), then the similar products."
    )
    has_alternative: bool = Field(description="False only when nothing in stock fits; then say so honestly.")


class StoreHours(BaseModel):
    days: str
    hours: str


class StoreInfo(BaseModel):
    name: str
    address: str
    hours: list[StoreHours]
    notes: list[str]


class CartLineView(BaseModel):
    name: str
    product_id: str
    size: str
    qty: int
    unit_price: float
    currently_in_stock: bool


class SavedChatMessage(BaseModel):
    date: str = Field(description="UTC date-time the message was sent, YYYY-MM-DD HH:MM.")
    role: Literal["user", "assistant"]
    content: str


class SavedChats(BaseModel):
    """The logged-in shopper's own saved conversation (chat_messages), oldest first."""

    logged_in: bool
    total_saved: int = 0
    first_saved_at: str | None = None
    messages: list[SavedChatMessage] = Field(default_factory=list)


class AccountView(BaseModel):
    logged_in: bool
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = Field(default=None, description="The shopper's own email. Share only if they ask about their account.")
    member_since: str | None = None
    cart: list[CartLineView] = Field(default_factory=list)
    cart_subtotal: float = 0.0
