"""Summarize output/audit_trail.json to compare agent designs (harness §10).

Groups entries by agent_version (and tier), and prints request counts, latency,
LLM round-trips, tokens, and tool calls. Run from backend/:

    .venv/bin/python scripts/audit_summary.py                 # everything, by version + tier
    .venv/bin/python scripts/audit_summary.py --since 2026-10-07T00:00
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import AUDIT_TRAIL_PATH  # noqa: E402


def pct(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="only entries at/after this ISO timestamp (UTC)")
    ap.add_argument("--until", help="only entries before this ISO timestamp (UTC)")
    args = ap.parse_args()

    entries = json.loads(AUDIT_TRAIL_PATH.read_text()) if AUDIT_TRAIL_PATH.exists() else []
    entries = [e for e in entries if e.get("type", "run") == "run"]  # run summaries only (skip per-step entries)
    if args.since:
        entries = [e for e in entries if e["timestamp"] >= args.since]
    if args.until:
        entries = [e for e in entries if e["timestamp"] < args.until]

    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in entries:
        groups[(e.get("agent_version", "v0-before-versioning"), e.get("tier") or "-")].append(e)

    print(f"{'version':22} {'tier':6} {'n':>3} {'ok%':>5} {'lat p50':>8} {'lat p90':>8} {'LLM trips':>9} {'in tok p50':>10} {'out tok p50':>11} {'tools/turn':>10}")
    for (version, tier), es in sorted(groups.items()):
        ok = [e for e in es if e.get("outcome") == "ok"]
        lat = [e["elapsed_ms"] / 1000 for e in ok if e.get("elapsed_ms") is not None]
        trips = [e["model_requests"] for e in ok if e.get("model_requests") is not None]
        tin = [e["input_tokens"] for e in ok if e.get("input_tokens")]
        tout = [e["output_tokens"] for e in ok if e.get("output_tokens")]
        tools = [len(e.get("tool_calls", [])) for e in ok]
        print(
            f"{version:22} {tier:6} {len(es):>3} {100 * len(ok) / len(es):>4.0f}% "
            f"{st.median(lat) if lat else float('nan'):>7.1f}s {pct(lat, 0.9):>7.1f}s "
            f"{st.mean(trips) if trips else float('nan'):>9.1f} {st.median(tin) if tin else float('nan'):>10.0f} "
            f"{st.median(tout) if tout else float('nan'):>11.0f} {st.mean(tools) if tools else float('nan'):>10.1f}"
        )
    outcomes = Counter(e.get("outcome") for e in entries)
    print("\noutcomes:", dict(outcomes))
    print("tool usage:", dict(Counter(t for e in entries for t in e.get("tool_calls", [])).most_common()))


if __name__ == "__main__":
    main()
