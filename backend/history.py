"""Saved chat history for logged-in shoppers, stored in the seed table chat_messages.

One row per message: user_id, role ('user' | 'assistant'), content, products_json
(the cards shown under an assistant reply, same JSON-array format as the seed rows),
search_json (the "View all" search, added by db.migrate), created_at (UTC).
Guests are never stored.
"""

from __future__ import annotations

from config import MAX_HISTORY_TURN_CHARS

import json
from contextlib import closing
from dataclasses import dataclass

from db import connect
from models import ChatReply, ChatTurn, SearchSpec

REPLAY_MESSAGES = 10  # most recent saved messages replayed to the model as context
HISTORY_LIMIT = 100  # most recent messages returned to the widget on reload


@dataclass
class StoredMessage:
    id: int
    role: str
    content: str
    created_at: str
    product_ids: list[str]
    search: SearchSpec | None


def _product_ids(products_json: str | None) -> list[str]:
    try:
        items = json.loads(products_json or "[]")
    except json.JSONDecodeError:
        return []
    return [i["product_id"] for i in items if isinstance(i, dict) and i.get("product_id")]


def _search(search_json: str | None) -> SearchSpec | None:
    try:
        return SearchSpec.model_validate_json(search_json) if search_json else None
    except ValueError:
        return None


def load(user_id: int, limit: int = HISTORY_LIMIT) -> list[StoredMessage]:
    """The shopper's most recent messages, oldest first."""
    with closing(connect()) as conn:
        rows = conn.execute(
            """SELECT id, role, content, products_json, search_json, created_at FROM chat_messages
               WHERE user_id = ? AND role IN ('user', 'assistant') ORDER BY id DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    return [
        StoredMessage(r["id"], r["role"], r["content"], r["created_at"], _product_ids(r["products_json"]), _search(r["search_json"]))
        for r in reversed(rows)
    ]


def stats(user_id: int) -> tuple[int, str | None]:
    """(number of saved messages, UTC timestamp of the first one)."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT COUNT(*) AS n, MIN(created_at) AS first FROM chat_messages WHERE user_id = ?", (user_id,)).fetchone()
    return row["n"], row["first"]


def recent_turns(user_id: int, n: int = REPLAY_MESSAGES) -> list[ChatTurn]:
    """Saved messages to replay to the agent (the DB, not the browser, is the source of truth)."""
    return [ChatTurn(role=m.role, content=m.content[:MAX_HISTORY_TURN_CHARS]) for m in load(user_id, n)]


def save_exchange(user_id: int, user_text: str, reply: ChatReply) -> None:
    products_json = json.dumps([p.model_dump() for p in reply.products]) if reply.products else None
    search_json = reply.search.model_dump_json() if reply.search else None
    with closing(connect(readonly=False)) as conn:
        conn.execute("INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)", (user_id, user_text))
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json, search_json) VALUES (?, 'assistant', ?, ?, ?)",
            (user_id, reply.reply, products_json, search_json),
        )
        conn.commit()


def clear(user_id: int) -> int:
    with closing(connect(readonly=False)) as conn:
        n = conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,)).rowcount
        conn.commit()
    return n
