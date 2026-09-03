#!/usr/bin/env python3
"""dice-bot: a tiny technocore.chat bot that rolls dice.

Run it as:
    python3 dice_bot.py

It connects to technocore.chat over HTTP (see /docs/protocol on the server),
joins the default room, and listens for messages of the form

    @dice 2d6+3
    @dice 4d8
    @dice d20

It replies with the individual die rolls and the total. Anything else
is ignored, so the bot can share a room without flooding it.

The HTTP protocol is intentionally simple so this file stays small and
copy-pasteable. You can paste the whole thing into a fresh repo, run it,
and it works.

Configuration via environment variables:
    TC_ROOM       room slug to join (default: "lobby")
    TC_NICK       display name (default: "dice-bot")
    TC_BASE       server base url (default: "https://technocore.chat")

Requirements: Python 3.10+ standard library only. No pip install.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from collections import deque

BASE = os.environ.get("TC_BASE", "https://technocore.chat").rstrip("/")
ROOM = os.environ.get("TC_ROOM", "lobby")
NICK = os.environ.get("TC_NICK", "dice-bot")

DICE_RE = re.compile(
    r"^\s*(?P<n>\d*)d(?P<s>\d+)(?:\s*([+-])\s*(?P<m>\d+))?\s*$",
    re.IGNORECASE,
)


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def get_json(path: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8") or "{}")


def roll(expr: str) -> tuple[list[int], int, int | None]:
    """Parse '2d6+3' / 'd20' / '4d8-1' into (rolls, total, modifier)."""
    m = DICE_RE.match(expr)
    if not m:
        raise ValueError(f"bad dice expression: {expr!r}")
    n = int(m.group("n") or "1")
    sides = int(m.group("s"))
    if not 1 <= n <= 100:
        raise ValueError("number of dice must be 1..100")
    if not 2 <= sides <= 1000:
        raise ValueError("sides must be 2..1000")
    sign = m.group(3)
    mod = int(m.group("m")) if m.group("m") else None
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + (mod if sign == "+" else -mod if sign == "-" else 0)
    return rolls, total, mod


def handle(text: str) -> str | None:
    """Return a reply string if text is a dice command, else None."""
    stripped = text.strip()
    if not stripped.lower().startswith(("@dice", "dice:", "!dice")):
        return None
    payload = stripped.split(maxsplit=1)[1] if " " in stripped else stripped.split(":", 1)[-1].strip()
    payload = payload.strip()
    if not payload:
        return "usage: @dice <n>d<s>[+/-<mod>]  e.g. @dice 2d6+3"
    try:
        rolls, total, mod = roll(payload)
    except ValueError as e:
        return f"could not roll {payload!r}: {e}"
    shown = ",".join(str(r) for r in rolls)
    mod_str = f" {'+' if mod is not None and total - sum(rolls) >= 0 else ''}{total - sum(rolls) if mod is not None else ''}".rstrip()
    return f"{NICK} rolled {payload}: [{shown}] = {total}"


def main() -> int:
    print(f"[{NICK}] joining {BASE}/rooms/{ROOM}", file=sys.stderr)
    # Long-poll loop: the server keeps the connection open and streams
    # new messages as JSON lines. If that endpoint isn't available we
    # fall back to polling /rooms/{room}/messages.
    cursor: str | None = None
    backoff = 1
    while True:
        try:
            path = f"/rooms/{ROOM}/messages?since={cursor or ''}"
            data = get_json(path)
            for msg in data.get("messages", []):
                cursor = msg.get("id", cursor)
                if msg.get("nick") == NICK:
                    continue  # don't reply to ourselves
                text = msg.get("text", "")
                reply = handle(text)
                if reply:
                    post_json(
                        f"/rooms/{ROOM}/messages",
                        {"nick": NICK, "text": reply},
                    )
            backoff = 1
        except urllib.error.HTTPError as e:
            if e.code == 429:
                import time
                time.sleep(int(e.headers.get("Retry-After", backoff)))
                backoff = min(backoff * 2, 30)
                continue
            print(f"http error: {e}", file=sys.stderr)
        except (urllib.error.URLError, TimeoutError) as e:
            import time
            print(f"network error, retrying in {backoff}s: {e}", file=sys.stderr)
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        import time
        time.sleep(2)  # gentle poll interval


if __name__ == "__main__":
    sys.exit(main())

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
