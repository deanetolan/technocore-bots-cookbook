#!/usr/bin/env python3
"""
counter-bot — a minimal technocore.chat example bot.

What it does:
  Counts how many times each sender has spoken in the room since the bot
  started. Replies to the command "counter" with the top N senders, and to
  "counter <did-or-name-fragment>" with that sender's tally.

Why it's useful:
  - Demonstrates per-sender state (a tiny "DB") in pure Python.
  - Shows how to parse simple commands from the room message stream.
  - Shows a clean shutdown via the LEASE / end-of-stream signals.
  - Is short enough to read in one sitting and copy verbatim.

Run it:
  python3 counter_bot.py

It expects the standard technocore.chat loop in stdin -> stdout, one
message per line, framed as JSON objects with at least:
    {"type": "msg", "from": "<did>", "text": "..."}
    {"type": "hello", "room": "...", "bot_did": "..."}
    {"type": "bye", "reason": "..."}
Adjust PARSE_LINE below if your client emits slightly different keys.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from typing import Any, Dict

BOT_NAME = "counter-bot"
TOP_N = 5


def parse_line(raw: str) -> Dict[str, Any]:
    """Parse one framed JSON line from technocore.chat. Tolerant of extra keys."""
    raw = raw.strip()
    if not raw:
        return {"type": "__empty__"}
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {"type": "__bad__", "raw": raw}
    if not isinstance(obj, dict):
        return {"type": "__bad__", "raw": raw}
    return obj


def short_did(did: str) -> str:
    """Return a stable, human-friendly handle from a DID."""
    if not did:
        return "anonymous"
    if did.startswith("did:key:"):
        return "did:key:" + did[len("did:key:"):][:6] + "…"
    return did[:12] + ("…" if len(did) > 12 else "")


def handle_command(text: str, counts: Counter, send) -> None:
    """Interpret a user command and emit a reply if appropriate."""
    parts = text.strip().split()
    if not parts:
        return
    cmd = parts[0].lower()
    if cmd != "counter":
        return

    if len(parts) == 1:
        # Top N leaderboard.
        if not counts:
            send(f"[{BOT_NAME}] no messages counted yet.")
            return
        lines = [f"[{BOT_NAME}] top {min(TOP_N, len(counts))} speakers:"]
        for rank, (sender, n) in enumerate(counts.most_common(TOP_N), 1):
            lines.append(f"  {rank}. {short_did(sender)} — {n}")
        send("\n".join(lines))
        return

    # Lookup a specific sender by DID fragment or full DID.
    needle = parts[1].lower()
    matches = [
        (sender, n) for sender, n in counts.items()
        if needle in sender.lower()
    ]
    if not matches:
        send(f"[{BOT_NAME}] no sender matches '{parts[1]}'.")
        return
    if len(matches) == 1:
        sender, n = matches[0]
        send(f"[{BOT_NAME}] {short_did(sender)} has sent {n} message(s).")
        return
    # Multiple matches: list them briefly.
    joined = ", ".join(short_did(s) for s, _ in matches)
    send(f"[{BOT_NAME}] {len(matches)} matches: {joined}. Be more specific.")


def main() -> int:
    counts: Counter = Counter()
    total_msgs = 0

    def send(text: str) -> None:
        # Frame outbound as a single JSON line, matching the room's wire format.
        sys.stdout.write(json.dumps({"type": "msg", "text": text}) + "\n")
        sys.stdout.flush()

    # Announce ourselves so others can see the example running.
    send(f"[{BOT_NAME}] online. Say 'counter' for top speakers, "
         f"or 'counter <did-fragment>' to look one up.")

    for raw in sys.stdin:
        evt = parse_line(raw)
        etype = evt.get("type")

        if etype == "hello":
            room = evt.get("room", "?")
            send(f"[{BOT_NAME}] joined room {room}.")
            continue

        if etype in ("bye", "__empty__", "__bad__"):
            if etype == "bye":
                send(f"[{BOT_NAME}] shutting down: {evt.get('reason', 'bye')}. "
                     f"Saw {total_msgs} message(s).")
                break
            continue

        if etype != "msg":
            # Heartbeats, presence pings, etc. — ignore but stay alive.
            continue

        sender = evt.get("from") or evt.get("did") or ""
        text = evt.get("text") or evt.get("body") or ""
        if not sender or not text:
            continue

        # Don't count our own replies toward the leaderboard.
        if text.startswith(f"[{BOT_NAME}]"):
            continue

        counts[sender] += 1
        total_msgs += 1

        handle_command(text, counts, send)

    return 0


if __name__ == "__main__":
    sys.exit(main())

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
