"""Fact-checker (harness §10, option E): every price and stock count stated in a reply must
come from this turn's tool results (or the shopper's own message, e.g. a budget).

Deterministic and LLM-free: extract claims with regexes, compare them with the numbers the
tools actually returned. agent.run_chat retries once on a mismatch, then falls back to a
reply built straight from the database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic_ai.messages import ModelMessage, ModelRequest, ToolReturnPart
from pydantic_core import to_jsonable_python

SIZES = r"(?:XXL|XL|XS|S|M|L)"
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")
# Patterns that state how many units are in stock (not counts of matching products).
STOCK_RES = [
    re.compile(r"\bonly\s+(\d+)\b", re.I),
    re.compile(r"\b(\d+)\s+(?:left|remaining|available|in stock|units?)\b", re.I),
    re.compile(rf"\b(\d+)\s+in\s+(?:size\s+)?{SIZES}\b"),
    re.compile(rf"\b{SIZES}\s*[:=–—-]\s*(\d+)\b"),
    re.compile(r"\((\d+)\s+(?:available|left|in stock)\)", re.I),
    re.compile(r"\b(\d+)\b[^.\n]{0,40}?\bin total\b", re.I),
]
PRICE_KEYS = {"price", "unit_price", "cart_subtotal", "max_price"}
STOCK_KEYS = {"quantity", "total_in_stock", "size_quantity", "qty", "requested_size_quantity", "max_qty"}


@dataclass
class Facts:
    prices: set[float] = field(default_factory=set)
    stock: set[int] = field(default_factory=lambda: {0})


@dataclass
class Claim:
    kind: str  # "price" | "stock"
    value: float
    text: str


def _walk(obj, facts: Facts) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in PRICE_KEYS and isinstance(v, (int, float)):
                facts.prices.add(round(float(v), 2))
            elif k in STOCK_KEYS and isinstance(v, int):
                facts.stock.add(v)
            else:
                _walk(v, facts)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, facts)


def collect(messages: list[ModelMessage], user_message: str) -> Facts:
    """Every price/stock number the tools returned this turn, plus numbers the shopper typed."""
    facts = Facts()
    for m in messages:
        if isinstance(m, ModelRequest):
            for part in m.parts:
                if isinstance(part, ToolReturnPart):
                    _walk(to_jsonable_python(part.content), facts)
    # Derived prices the agent may legitimately state: quantity × unit price (cart lines).
    facts.prices |= {round(p * k, 2) for p in list(facts.prices) for k in range(2, 11)}
    for n in re.findall(r"\d+(?:\.\d{1,2})?", user_message):
        facts.prices.add(round(float(n), 2))
        if "." not in n:
            facts.stock.add(int(n))
    return facts


def claims(reply: str) -> list[Claim]:
    text = reply.replace("**", "").replace("*", "")
    found = [Claim("price", round(float(m.group(1).replace(",", "")), 2), m.group(0)) for m in PRICE_RE.finditer(text)]
    seen: set[tuple[int, int]] = set()
    for rx in STOCK_RES:
        for m in rx.finditer(text):
            if m.span(1) in seen:
                continue
            seen.add(m.span(1))
            found.append(Claim("stock", int(m.group(1)), m.group(0).strip()))
    return found


def unsupported(reply: str, facts: Facts) -> tuple[list[Claim], int]:
    """(claims not backed by the facts, total claims checked)."""
    all_claims = claims(reply)
    bad = [
        c
        for c in all_claims
        if (c.kind == "price" and not any(abs(c.value - p) < 0.005 for p in facts.prices))
        or (c.kind == "stock" and int(c.value) not in facts.stock)
    ]
    return bad, len(all_claims)


def correction_prompt(bad: list[Claim]) -> str:
    listed = "; ".join(f'"{c.text}"' for c in bad)
    return (
        "FACT-CHECK FAILED (system message, not from the shopper): your last reply stated "
        f"{listed}, but no tool result in this conversation turn contains that number. "
        "Call lookup_product (or the right tool) now and answer the shopper's question again, "
        "using ONLY prices and stock counts that appear in tool results. Same voice, same length."
    )
