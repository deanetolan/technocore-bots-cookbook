"""
quote-bot: a tiny technocore chat bot that periodically posts a random quote
to a room. Useful as a copy-paste starting point for any bot that needs
to do something on a timer (reminders, digests, heartbeat, etc.).

Run:
    python quote_bot.py --room <room_id> \
        --signing-key <ed25519_hex_or_path> \
        --token <bearer_token> \
        --interval 300

It will:
  1. POST /v1/rooms/<room>/messages with a quote.
  2. Sleep for --interval seconds.
  3. Repeat forever (Ctrl-C to stop).

Quote source is a small bundled list, so the bot works offline and has
no external dependencies beyond the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import signal
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_BASE = "https://technocore.chat"
DEFAULT_INTERVAL = 300  # seconds between posts
USER_AGENT = "quote-bot/1.0 (+https://technocore.chat)"

# A tiny, curated quote list. Add or replace as you like.
QUOTES = [
    "Programs must be written for people to read. — Harold Abelson",
    "Simplicity is the soul of efficiency. — Austin Freeman",
    "Make it work, make it right, make it fast. — Kent Beck",
    "The best way to predict the future is to invent it. — Alan Kay",
    "Premature optimization is the root of all evil. — Donald Knuth",
    "Talk is cheap. Show me the code. — Linus Torvalds",
    "First, solve the problem. Then, write the code. — John Johnson",
    "Any sufficiently advanced bug is indistinguishable from a feature.",
    "It works on my machine. — every developer, ever",
    "There are only two hard things in CS: cache invalidation and naming things.",
]


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only, so this is trivially copy-pasteable)
# ---------------------------------------------------------------------------

def _read_signing_key(value: str) -> str:
    """Accept either a raw hex string or a path to a file containing hex."""
    if os.path.exists(value):
        with open(value, "r", encoding="utf-8") as f:
            return f.read().strip()
    return value.strip()


def post_message(base: str, room: str, token: str, text: str,
                 timeout: float = 10.0) -> dict:
    url = f"{base.rstrip('/')}/v1/rooms/{room}/messages"
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_running = True


def _stop(_signum, _frame):
    global _running
    _running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Post random quotes to a room.")
    p.add_argument("--base", default=DEFAULT_BASE,
                   help=f"technocore base URL (default: {DEFAULT_BASE})")
    p.add_argument("--room", required=True, help="room id to post into")
    p.add_argument("--token", required=True,
                   help="bearer token for the bot account")
    p.add_argument("--signing-key", dest="signing_key", default="",
                   help="optional ed25519 key (hex or path); logged at startup")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                   help=f"seconds between posts (default: {DEFAULT_INTERVAL})")
    p.add_argument("--once", action="store_true",
                   help="post a single quote and exit (useful for cron)")
    p.add_argument("--dry-run", action="store_true",
                   help="print instead of POSTing")
    args = p.parse_args(argv)

    if args.interval < 1:
        p.error("--interval must be >= 1")

    key = _read_signing_key(args.signing_key) if args.signing_key else ""
    print(f"[quote-bot] base={args.base} room={args.room} "
          f"interval={args.interval}s once={args.once} dry_run={args.dry_run}",
          file=sys.stderr)
    if key:
        # Never print the full key; just confirm we loaded it.
        print(f"[quote-bot] signing key loaded ({len(key)} chars)",
              file=sys.stderr)

    rng = random.SystemRandom()  # cryptographic RNG, no extra deps

    while _running:
        quote = rng.choice(QUOTES)
        text = f"📜 {quote}"
        try:
            if args.dry_run:
                print(text)
            else:
                resp = post_message(args.base, args.room, args.token, text)
                mid = resp.get("id") or resp.get("message_id") or "?"
                print(f"[quote-bot] posted id={mid}", file=sys.stderr)
        except urllib.error.HTTPError as e:
            print(f"[quote-bot] HTTP {e.code} {e.reason}: {e.read()[:200]}",
                  file=sys.stderr)
        except urllib.error.URLError as e:
            print(f"[quote-bot] network error: {e.reason}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 — keep loop alive
            print(f"[quote-bot] unexpected error: {e!r}", file=sys.stderr)

        if args.once:
            break

        # Sleep in short chunks so SIGTERM shuts us down promptly.
        slept = 0
        while _running and slept < args.interval:
            time.sleep(min(1, args.interval - slept))
            slept += 1

    print("[quote-bot] bye", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
