"""Tools the shop agent can call. Every fact the agent states should come from here."""

from __future__ import annotations

import re
from contextlib import closing

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

import history
from cards import to_card
from cart import read_cart
from db import SIZE_ORDER, all_products, connect
from models import (
    AccountView,
    AlternativesResult,
    AgentDeps,
    CartLineView,
    LOW_STOCK_THRESHOLD,
    Product,
    ProductAmbiguous,
    ProductCandidate,
    ProductLookup,
    ProductLookupResult,
    ProductNotFound,
    ProductStockStatus,
    ProductSummary,
    ResolvedPage,
    SavedChatMessage,
    SavedChats,
    SearchResults,
    SizeAvailability,
    StockStatus,
    StoreHours,
    StoreInfo,
)

# Physical store facts (kept in sync with frontend/src/store.ts).
# Result limits (Safety rules, harness §12): keep every tool result small, whatever the model asks for.
MAX_QUERY_CHARS = 100  # search text / product name the model passes in
MAX_SEARCH_RESULTS = 12  # search_products results per call (default 8)
MAX_ALTERNATIVES = 3  # similar products from suggest_alternatives
MAX_CANDIDATES = 6  # "which one did you mean?" options
MAX_SUGGESTIONS = 3  # "we don't carry that, but…" options
MAX_SAVED_CHATS = 50  # saved messages get_saved_chats returns
MAX_SAVED_CHAT_CHARS = 400  # characters per saved message


STORE = StoreInfo(
    name="Campus Customs",
    address="57 Broadway, New Haven, CT 06511",
    hours=[
        StoreHours(days="Monday – Friday", hours="10 AM – 7 PM"),
        StoreHours(days="Saturday – Sunday", hours="10 AM – 2 PM"),
        StoreHours(days="Holidays & celebrations", hours="12 PM – 7 PM"),
    ],
    notes=[
        "No phone number or holiday calendar is on file; suggest confirming holiday hours with the store.",
        "Custom merchandise (our products as your canvas) is arranged in store.",
        "Online checkout is coming soon; shoppers can already save items with Put Into Cart.",
    ],
)

# Shopper words -> words used in the catalogue, so "tee" finds "t-shirt", etc.
SYNONYMS: dict[str, list[str]] = {
    "tee": ["t-shirt", "t shirt"],
    "tshirt": ["t-shirt"],
    "shirt": ["t-shirt"],
    "hoody": ["hoodie"],
    "hoodies": ["hoodie"],
    "sweater": ["sweatshirt", "crewneck", "fleece"],
    "sweatshirt": ["crewneck", "hoodie"],
    "crew": ["crewneck"],
    "quarter": ["1/4 zip", "quarter-zip", "quarter zip"],
    "jacket": ["jacket", "fleece", "bomber"],
    "coat": ["jacket", "fleece"],
    "warm": ["fleece", "hoodie", "crewneck", "jacket", "sweatshirt"],
    "winter": ["fleece", "hoodie", "crewneck", "jacket"],
    "grey": ["gray"],
    "navy": ["navy", "blue"],
    "blue": ["navy", "blue"],
}
STOPWORDS = {
    "a", "an", "the", "do", "you", "have", "any", "for", "me", "i", "want", "some", "with", "in", "of", "and", "or",
    "my", "show", "is", "are", "looking", "something", "what", "which", "kind", "kinds", "type", "types", "all",
    "got", "your", "available", "stock", "sell", "carry", "options", "shop", "buy", "find", "need", "like", "please",
    "see", "under", "below", "over", "less", "than", "cheap", "cheaper", "price", "priced", "budget", "size", "sizes",
    "that", "this", "there", "can", "get", "it", "on", "to", "at", "by", "from", "yale", "campus", "customs",
}


def _size_status(qty: int) -> StockStatus:
    if qty <= 0:
        return "sold_out"
    return "low_stock" if qty <= LOW_STOCK_THRESHOLD else "in_stock"


def _product_status(p: Product) -> ProductStockStatus:
    available = sum(s.in_stock for s in p.sizes)
    if available == 0:
        return "sold_out"
    return "in_stock" if available == len(p.sizes) else "partly_sold_out"


def _summary(p: Product) -> ProductSummary:
    return ProductSummary(
        product_id=p.product_id,
        name=p.name,
        garment_type=p.garment_type,
        price=p.price,
        colors=p.colors,
        stock_status=_product_status(p),
        in_stock_sizes=[s.size for s in p.sizes if s.in_stock],
        out_of_stock_sizes=[s.size for s in p.sizes if not s.in_stock],
        description=p.description,
    )


def _score(p: Product, terms: list[str]) -> float:
    name, kind = p.name.lower(), p.garment_type.lower()
    tags = " ".join(p.search_tags).lower()
    colors = " ".join(p.colors).lower()
    desc = p.description.lower()
    score = 0.0
    for term in terms:
        score += 3 * (term in name) + 2 * (term in kind) + 2 * (term in tags) + 1.5 * (term in colors) + 1 * (term in desc)
    return score


def _terms(query: str) -> list[str]:
    # Numbers/prices are dropped: budgets go through max_price, not text matching.
    words = [w for w in re.findall(r"[a-z0-9/$.-]+", query.lower()) if w not in STOPWORDS and not re.fullmatch(r"\$?[\d.]+", w)]
    terms: list[str] = []
    for w in words:
        terms.append(w.rstrip("s") if len(w) > 3 and w.endswith("s") else w)
        terms.extend(SYNONYMS.get(w, []))
    return terms


# Category words in a query act as a filter on name + garment_type, so "what hoodies do
# you have?" returns every hoodie and nothing else. Values are patterns on _norm() text.
CATEGORIES: dict[str, tuple[str, ...]] = {
    "hoodie": ("hood",),
    "crewneck": ("crewneck",),
    "t-shirt": ("t shirt",),
    "quarter-zip": ("1 4 zip", "quarter zip"),
    "jacket": ("jacket", "fleece"),
    "long sleeve": ("long sleeve",),
}
CATEGORY_TRIGGERS: dict[str, str] = {
    "hoodie": "hoodie", "hoodies": "hoodie", "hoody": "hoodie", "hooded": "hoodie",
    "crewneck": "crewneck", "crewnecks": "crewneck", "crew": "crewneck",
    "tee": "t-shirt", "tees": "t-shirt", "tshirt": "t-shirt", "tshirts": "t-shirt", "t-shirt": "t-shirt", "t-shirts": "t-shirt",
    "quarter": "quarter-zip", "quarter-zip": "quarter-zip", "1/4": "quarter-zip",
    "jacket": "jacket", "jackets": "jacket", "fleece": "jacket", "coat": "jacket", "coats": "jacket", "outerwear": "jacket",
    "long-sleeve": "long sleeve",
}


def _categories(query: str) -> set[str]:
    q = query.lower()
    found = {CATEGORY_TRIGGERS[w] for w in re.findall(r"[a-z0-9/-]+", q) if w in CATEGORY_TRIGGERS}
    if "long sleeve" in q:
        found.add("long sleeve")
    return found


def _in_category(p: Product, cats: set[str]) -> bool:
    haystack = _norm(f"{p.name} {p.garment_type}")
    return any(pattern in haystack for c in cats for pattern in CATEGORIES[c])


def _rank(products: list[Product], query: str) -> list[Product]:
    cats = _categories(query)
    terms = _terms(query)
    if cats:
        products = [p for p in products if _in_category(p, cats)]
        # Extra words ("navy", "Berkeley", "bulldog") narrow the category when they match something.
        extra = [t for t in terms if t not in CATEGORY_TRIGGERS and t not in CATEGORIES and not any(t in pats for pats in CATEGORIES.values())]
        narrowed = [p for p in products if _score(p, extra) > 0] if extra else []
        if narrowed:
            products = narrowed
    # With a category filter, every product left is a match; the other words only order them.
    scored = [((_score(p, terms) if terms else 1.0) + (1 if cats else 0), sum(s.quantity for s in p.sizes), p) for p in products]
    scored = [x for x in scored if x[0] > 0]
    scored.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return [p for _, _, p in scored]


def find_products(query: str, max_price: float | None = None, size: str | None = None) -> list[Product]:
    """The one search engine: used by the agent's tool, GET /api/products, and the page's "View all"."""
    wanted_size = _clean_size(size)
    products = [
        p
        for p in all_products()
        if (max_price is None or p.price <= max_price)
        and (not wanted_size or any(s.size == wanted_size and s.in_stock for s in p.sizes))
    ]
    return _rank(products, query)


def search_products(
    ctx: RunContext[AgentDeps],
    query: str,
    max_price: float | None = None,
    size: str | None = None,
    limit: int = 8,
) -> SearchResults:
    """Search the catalogue. Use for "what X do you have?", browsing, and recommendations.
    The website shows the products you return in `product_ids` as cards, and offers a
    "View all" link that re-runs this exact search on the Products page.

    Args:
        query: What the shopper wants, in plain words, e.g. "hoodies", "navy crewneck", "Berkeley college", "gift".
        max_price: Only return products at or below this price in USD.
        size: Only return products with this size in stock (XS, S, M, L, XL, XXL).
        limit: Max results to return (1-12). total_matches always counts every match.
    """
    query = query[:MAX_QUERY_CHARS]
    matches = find_products(query, max_price, size)
    shown = matches[: max(1, min(limit, MAX_SEARCH_RESULTS))]
    return SearchResults(
        query=query,
        max_price=max_price,
        size=_clean_size(size),
        total_matches=len(matches),
        results=[_summary(p) for p in shown],
    )


def _clean_size(size: str | None) -> str | None:
    if not size:
        return None
    s = size.strip().upper().replace("EXTRA ", "X").replace("XX-LARGE", "XXL")
    aliases = {"SMALL": "S", "MEDIUM": "M", "MED": "M", "LARGE": "L", "XLARGE": "XL", "X-LARGE": "XL", "2XL": "XXL", "XXLARGE": "XXL", "XSMALL": "XS", "X-SMALL": "XS"}
    s = aliases.get(s, s)
    if s not in SIZE_ORDER:
        raise ModelRetry(f"Unknown size {size!r}. Use one of {SIZE_ORDER}.")
    return s


def _norm(text: str) -> str:
    """Lower-case, unify 1/4 and t-shirt spellings, drop punctuation."""
    text = text.lower().replace("1/4", "1 4").replace("quarter", "1 4").replace("t-shirt", "t shirt")
    text = re.sub(r"\btees?\b", "t shirt", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _candidate(p: Product) -> ProductCandidate:
    return ProductCandidate(product_id=p.product_id, name=p.name, price=p.price)


def _resolve(product: str, catalogue: list[Product]) -> tuple[Product, str] | ProductAmbiguous | ProductNotFound:
    """product_id → exact name → closest name (shared by lookup_product and suggest_alternatives)."""
    product = product[:MAX_QUERY_CHARS]
    by_id = {p.product_id: p for p in catalogue}
    if product.strip() in by_id:
        return by_id[product.strip()], "product_id"
    q = _norm(product)
    exact = [p for p in catalogue if _norm(p.name) == q]
    if len(exact) == 1:
        return exact[0], "exact_name"
    # Closest names: share of the query's words found in the product name.
    q_words = set(q.split()) - STOPWORDS
    scored = sorted(
        ((len(q_words & set(_norm(p.name).split())) / max(len(q_words), 1), p) for p in catalogue),
        key=lambda x: x[0],
        reverse=True,
    )
    top = [p for score, p in scored if score >= 0.6 and score == scored[0][0]]
    if len(top) == 1:
        return top[0], "closest_name"
    if top:
        return ProductAmbiguous(query=product, candidates=[_candidate(p) for p in top[:MAX_CANDIDATES]])
    return ProductNotFound(query=product, suggestions=[_candidate(p) for p in _rank(catalogue, product)[:MAX_SUGGESTIONS]])


def lookup_product(ctx: RunContext[AgentDeps], product: str, size: str | None = None) -> ProductLookupResult:
    """Authoritative lookup in campus_customs.db: description, price, and live stock (total and per size).

    ALWAYS call this before stating a price, a stock count, or whether a size is available.

    Args:
        product: A product_id from search results (best), or the product's name as the shopper said it.
        size: Optional single size the shopper asked about (XS, S, M, L, XL, XXL).
    """
    wanted_size = _clean_size(size)
    resolved = _resolve(product, all_products())  # stock is re-read on every call (db.py caches only catalogue text)
    if not isinstance(resolved, tuple):
        return resolved  # ambiguous / not found
    match, how = resolved

    sizes = [SizeAvailability(size=s.size, quantity=s.quantity, status=_size_status(s.quantity)) for s in match.sizes]
    requested = None
    if wanted_size:
        # A size the product doesn't come in is reported as 0 / sold out rather than invented.
        requested = next((s for s in sizes if s.size == wanted_size), SizeAvailability(size=wanted_size, quantity=0, status="sold_out"))
    return ProductLookup(
        matched_by=how,
        product_id=match.product_id,
        name=match.name,
        garment_type=match.garment_type,
        description=match.description,
        price=match.price,
        colors=match.colors,
        stock_status=_product_status(match),
        total_in_stock=sum(s.quantity for s in sizes),
        sizes=sizes,
        available_sizes=[s.size for s in sizes if s.quantity > 0],
        sold_out_sizes=[s.size for s in sizes if s.quantity <= 0],
        requested_size=requested,
    )


PRICE_TIERS = [32.0, 45.0, 58.0, 68.0, 72.0, 88.0, 98.0]
GENERIC_NAME_WORDS = {"yale", "hoodie", "crewneck", "t", "shirt", "1", "4", "zip", "jacket", "fleece", "sweater", "left", "chest", "the", "of"}


def _color_words(colors: list[str]) -> set[str]:
    return {w for c in colors for w in c.lower().replace("grey", "gray").split() if w not in {"heather", "dark", "light"}}


def _product_categories(p: Product) -> set[str]:
    return {c for c in CATEGORIES if _in_category(p, {c})}


def suggest_alternatives(
    ctx: RunContext[AgentDeps], product: str, size: str | None = None, limit: int = 3
) -> AlternativesResult | ProductAmbiguous | ProductNotFound:
    """Call this whenever a requested size (or a whole product) is out of stock. Finds
    (a) the same product in other sizes that are in stock and (b) up to 3 similar products in
    the SAME category that DO have the requested size. Ranked from live DB data; results come
    back as ProductCards that the website shows.

    Args:
        product: product_id (best) or the product's name.
        size: The size the shopper wants (S, M, L, XL, ...). Omit if they didn't give one;
            then similar products just need to be in stock in some size.
        limit: Max similar products (1-3).
    """
    wanted = _clean_size(size)
    catalogue = all_products()
    resolved = _resolve(product, catalogue)
    if not isinstance(resolved, tuple):
        return resolved
    orig, _ = resolved

    req_qty = next((s.quantity for s in orig.sizes if s.size == wanted), 0) if wanted else None
    # (a) Same product: in-stock sizes, nearest to the requested size first.
    anchor = SIZE_ORDER.index(wanted) if wanted else 0
    other_sizes = sorted(
        (s for s in orig.sizes if s.in_stock and s.size != wanted),
        key=lambda s: (abs(SIZE_ORDER.index(s.size) - anchor), SIZE_ORDER.index(s.size)),
    )

    # (b) Similar products: same category only, and the requested size must be in stock.
    cats = _product_categories(orig)
    same_kind = (lambda p: bool(cats & _product_categories(p))) if cats else (lambda p: _norm(p.garment_type) == _norm(orig.garment_type))
    colors = _color_words(orig.colors)
    tags = {t.lower() for t in orig.search_tags} - {"yale", "campus customs", "yale merch", "college merch"}
    name_words = set(_norm(orig.name).split()) - GENERIC_NAME_WORDS
    tier = PRICE_TIERS.index(orig.price) if orig.price in PRICE_TIERS else None

    ranked = []
    for p in catalogue:
        if p.product_id == orig.product_id or not same_kind(p):
            continue
        size_stock = next((s.quantity for s in p.sizes if s.size == wanted), 0) if wanted else sum(s.quantity for s in p.sizes)
        if size_stock <= 0:
            continue  # never suggest something that's also sold out in their size
        shared_colors = colors & _color_words(p.colors)
        shared_topic = name_words & set(_norm(p.name).split())
        price_gap = abs(PRICE_TIERS.index(p.price) - tier) if tier is not None and p.price in PRICE_TIERS else abs(p.price - orig.price) / 15
        score = (
            1.5 * min(len(shared_colors), 3)
            + 2 * min(len(shared_topic), 2)
            + 0.5 * min(len(tags & {t.lower() for t in p.search_tags}), 4)
            - 1.5 * price_gap
        )
        why = [f"also a {p.garment_type}"]
        if shared_topic:
            why.append("same theme (" + ", ".join(sorted(shared_topic))[:30] + ")")
        if shared_colors:
            why.append(", ".join(sorted(shared_colors))[:30])
        why.append("same price" if p.price == orig.price else f"${p.price:.0f}")
        if wanted:
            why.append(f"{size_stock} in {wanted}")
        ranked.append((score, size_stock, p, " · ".join(why)))
    ranked.sort(key=lambda r: (r[0], r[1]), reverse=True)
    similar = ranked[: max(1, min(limit, MAX_ALTERNATIVES))]

    cards = ([to_card(orig)] if other_sizes else []) + [to_card(p) for _, _, p, _ in similar]
    return AlternativesResult(
        original_product_id=orig.product_id,
        original_name=orig.name,
        requested_size=wanted,
        requested_size_quantity=req_qty,
        original_stock_status=_product_status(orig),
        other_sizes_in_stock=[SizeAvailability(size=s.size, quantity=s.quantity, status=_size_status(s.quantity)) for s in other_sizes],
        similar_in_size=[p.product_id for _, _, p, _ in similar],
        why={p.product_id: w for _, _, p, w in similar},
        cards=cards,
        has_alternative=bool(other_sizes or similar),
    )


def get_store_info(ctx: RunContext[AgentDeps]) -> StoreInfo:
    """The physical store's address, opening hours, and notes."""
    return STORE


def get_my_account(ctx: RunContext[AgentDeps]) -> AccountView:
    """Who is chatting (name, email, member since) and their saved cart, for the logged-in shopper.

    Data comes from the shopper's own account only, never another customer's.
    """
    shopper = ctx.deps.shopper
    if shopper is None:
        return AccountView(logged_in=False)
    with closing(connect()) as conn:
        lines = read_cart(conn, shopper.user_id)
    cart = [
        CartLineView(
            name=line.name,
            product_id=line.product_id,
            size=line.size,
            qty=line.qty,
            unit_price=line.price,
            currently_in_stock=line.max_qty > 0,
        )
        for line in lines
    ]
    subtotal = sum(c.qty * c.unit_price for c in cart if c.currently_in_stock)
    return AccountView(
        logged_in=True,
        first_name=shopper.first_name,
        last_name=shopper.last_name,
        email=shopper.email,
        member_since=shopper.member_since,
        cart=cart,
        cart_subtotal=round(subtotal, 2),
    )


def get_saved_chats(ctx: RunContext[AgentDeps], limit: int = 30) -> SavedChats:
    """The logged-in shopper's own saved chat history with dates (oldest first), for questions like
    "what did I ask about last time?". Only the most recent messages are in the conversation already.

    Args:
        limit: How many of the most recent saved messages to return (1-50).
    """
    uid = ctx.deps.user_id
    if uid is None:
        return SavedChats(logged_in=False)
    total, first = history.stats(uid)
    msgs = history.load(uid, max(1, min(limit, MAX_SAVED_CHATS)))
    return SavedChats(
        logged_in=True,
        total_saved=total,
        first_saved_at=first,
        messages=[SavedChatMessage(date=m.created_at[:16], role=m.role, content=m.content[:MAX_SAVED_CHAT_CHARS]) for m in msgs],
    )


def get_current_page(ctx: RunContext[AgentDeps]) -> ResolvedPage | None:
    """What the shopper is looking at right now: the product pop-up open (if any), the last
    product they viewed, and any search on the Products page. Use it to resolve "this", "it",
    or "this one". Then call lookup_product with that product_id for facts."""
    return ctx.deps.page


shop_toolset = FunctionToolset[AgentDeps](
    tools=[search_products, lookup_product, suggest_alternatives, get_store_info, get_my_account, get_saved_chats, get_current_page]
)
