"""Loads .env once and exposes settings.

Looked up in order: backend/.env, hw4/.env (the project root; copy .env.example there), then
up to two parent folders (William's PORTKEY_API_KEY lives in "AI Foundation/.env", outside the
repo). The first file that sets a variable wins. Imported before anything reads os.environ.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
for env_dir in (BACKEND, ROOT, *list(ROOT.parents)[:2]):
    load_dotenv(env_dir / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


FAST_MODEL = os.getenv("FAST_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"
SMART_MODEL = os.getenv("SMART_MODEL", "gpt-6-luna").strip() or "gpt-6-luna"
SMART_REASONING_EFFORT = os.getenv("SMART_REASONING_EFFORT", "medium").strip() or "medium"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").strip()
CACHE_TTL_SECONDS = _int("CACHE_TTL_SECONDS", 60)
MAX_TOOL_CALLS_PER_TURN = _int("MAX_TOOL_CALLS_PER_TURN", 8)
MAX_HISTORY_MESSAGES = _int("MAX_HISTORY_MESSAGES", 10)
# Safety limits backing the "Safety rules" in prompts/prompt.md (harness §12).
MAX_MESSAGE_CHARS = _int("MAX_MESSAGE_CHARS", 1000)  # one shopper message
MAX_HISTORY_TURN_CHARS = _int("MAX_HISTORY_TURN_CHARS", 2000)  # one replayed history turn
MAX_HISTORY_TURNS_ACCEPTED = _int("MAX_HISTORY_TURNS_ACCEPTED", 20)  # turns a guest's browser may send
MAX_MODEL_REQUESTS_PER_TURN = _int("MAX_MODEL_REQUESTS_PER_TURN", 8)  # LLM round-trips per turn
AUDIT_TRAIL_PATH = ROOT / os.getenv("AUDIT_TRAIL_PATH", "output/audit_trail.json")
# Label written on every audit entry, so before/after comparisons group cleanly (see harness §10).
AGENT_VERSION = os.getenv("AGENT_VERSION", "v1-single-agent").strip() or "v1-single-agent"
