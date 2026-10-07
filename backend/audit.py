"""output/audit_trail.json: an append-only log of what the agent did (Problem 12).

One JSON list, oldest first. After every chat turn agent.run_chat appends:
  - one "step" entry per tool call the agent made (tool, short args/result, stop reason), and
  - one "run" summary entry (model, tier, tokens, cards, fact-check, outcome).
Entries written before Problem 12 have no "type"; they are run summaries.

Rules this module enforces:
  - Append-only: existing entries are never removed, trimmed or rewritten. The file is created
    only if it doesn't exist; if it exists but can't be parsed as a JSON list, it is left
    untouched and the new entries are skipped (with a server warning), never "reset".
  - Never raises: a logging failure must not break the chat reply.
  - No secrets: emails are masked (h***@campuscustoms.yale.edu); password/hash/token/key fields
    and key-like strings are replaced with "[redacted]".
"""

from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

from pydantic_core import to_jsonable_python

from config import AUDIT_TRAIL_PATH

log = logging.getLogger("campus_customs.audit")
_lock = threading.Lock()

SHORT = 200  # max characters kept for each logged argument / result

EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
SECRET_RES = [
    re.compile(r"pbkdf2[^\s\"',}]*", re.I),  # stored password hashes
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}"),  # API keys
    re.compile(r"\bBearer\s+\S+", re.I),
    re.compile(r"\b(?=[A-Za-z0-9_]*\d)(?=[A-Za-z0-9_]*[A-Za-z])[A-Za-z0-9_]{32,}\b"),  # long tokens/hashes
]
SECRET_KEY_RE = re.compile(r"pass|hash|salt|token|secret|api_?key|authorization|cookie|session", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def mask(text: str) -> str:
    """Mask emails and anything that looks like a secret in free text."""
    text = EMAIL_RE.sub(r"\1***@\2", text)
    for rx in SECRET_RES:
        text = rx.sub("[redacted]", text)
    return text


def redact(obj: Any) -> Any:
    """Drop the values of secret-looking fields from (JSON-able) structured data."""
    if isinstance(obj, dict):
        return {k: "[redacted]" if SECRET_KEY_RE.search(str(k)) else redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def short(obj: Any, limit: int = SHORT) -> str | None:
    """Redacted, masked, one-line preview of a tool argument or result, trimmed to ~200 chars.
    Masking happens before trimming so a cut can never expose part of an email or key."""
    if obj is None:
        return None
    if isinstance(obj, str):
        text = obj
    else:
        try:
            text = json.dumps(redact(to_jsonable_python(obj)), ensure_ascii=False, default=str)
        except Exception:
            text = str(obj)
    text = mask(" ".join(text.split()))
    return text if len(text) <= limit else text[: limit - 1] + "…"


def append(entries: list[dict]) -> bool:
    """Append entries to the audit trail. Returns False (and logs a warning) instead of raising."""
    if not entries:
        return True
    try:
        with _lock:
            if AUDIT_TRAIL_PATH.exists():
                try:
                    existing = json.loads(AUDIT_TRAIL_PATH.read_text())
                except (OSError, ValueError) as e:
                    log.warning("audit trail unreadable (%s); left untouched, %d entries skipped", e, len(entries))
                    return False
                if not isinstance(existing, list):
                    log.warning("audit trail is not a JSON list; left untouched, %d entries skipped", len(entries))
                    return False
            else:
                existing = []  # first run: create the file
            AUDIT_TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = AUDIT_TRAIL_PATH.with_name(AUDIT_TRAIL_PATH.name + ".tmp")
            tmp.write_text(json.dumps(existing + entries, indent=2, ensure_ascii=False, default=str))
            tmp.replace(AUDIT_TRAIL_PATH)  # atomic swap: readers never see a half-written file
        return True
    except Exception as e:  # disk full, permissions, …: the chat reply must still go out
        log.warning("could not write audit trail (%s: %s); %d entries skipped", type(e).__name__, e, len(entries))
        return False
