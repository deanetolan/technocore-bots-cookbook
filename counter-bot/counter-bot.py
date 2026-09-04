#!/usr/bin/env python3
"""counter-bot: the simplest non-trivial example in the cookbook.

Watches a room and maintains a per-author tally of every message it sees.
Periodically (every N seconds, configurable) it posts the current leaderboard
as a single message. Demonstrates the core loop every non-trivial technocore
bot needs:

  1. connect to the HTTP-native chat server (long-poll, no websockets needed)
  2. parse incoming `room.message` events from a chunked JSON stream
  3. keep tiny per-room state (a dict mapping author DID -> int count)
  4. occasionally publish back to the room using your signed DID

This is intentionally a single file, under ~150 lines of real logic, with no
external dependencies beyond the Python standard library. Drop it on a
server, fill in the three constants below, run `python3 counter-bot.py`, and
you have a live bot.

Identity
--------
You sign every outbound message with your Ed25519 DID. The simplest path
is to generate a key once with:

    python3 -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; \
        k = Ed25519PrivateKey.generate(); \
        print(k.private_bytes_raw().hex())"

then derive did:key:z6Mk... from the same module. For testing, the server
accepts an unsigned payload if you set SIGNING_KEY_HEX = None; production
should always sign.

Configuration
-------------
Edit the three constants in the CONFIG block, or override via environment
variables: COUNTER_ROOM, COUNTER_INTERVAL, COUNTER_SIGNING_KEY_HEX.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict
from typing import Any

# --- CONFIG ----------------------------------------------------------------

SERVER   = os.environ.get("COUNTER_SERVER", "https://technocore.chat")
ROOM     = os.environ.get("COUNTER_ROOM",   "lobby")           # room slug
INTERVAL = float(os.environ.get("COUNTER_INTERVAL", "30"))      # seconds
# 32-byte Ed25519 secret seed, hex-encoded. None => unsigned (dev only).
SIGNING_KEY_HEX = os.environ.get("COUNTER_SIGNING_KEY_HEX")

# --- IDENTITY ---------------------------------------------------------------

def _ed25519_public_b64(raw_secret: bytes) -> str:
    """Return the multicodec-prefixed base64 form used in did:key:z6Mk..."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.from_private_bytes_raw_secret(raw_secret)
    raw_pub = sk.public_key().public_bytes_raw()
    # 0xed01 multicodec prefix for Ed25519 public keys.
    prefixed = b"\xed\x01" + raw_pub
    return base64.urlsafe_b64encode(prefixed).rstrip(b"=").decode("ascii")

def _sign_payload(payload: bytes, secret: bytes) -> str:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.from_private_bytes_raw(secret)
    sig = sk.sign(payload)
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")

def my_did() -> str:
    if not SIGNING_KEY_HEX:
        return "did:key:z6Mkunsigned-dev-only"
    return "did:key:z6Mk" + _ed25519_public_b64(bytes.fromhex(SIGNING_KEY_HEX))

# --- HTTP HELPERS ----------------------------------------------------------

def http_json(path: str, body: dict | None = None, timeout: float = 30.0) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        SERVER + path,
        data=data,
        method="POST" if body is not None else "GET",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else None

def post_message(text: str) -> None:
    payload = {"room": ROOM, "text": text, "did": my_did()}
    if SIGNING_KEY_HEX:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload["signature"] = _sign_payload(body, bytes.fromhex(SIGNING_KEY_HEX))
    try:
        http_json("/api/rooms/" + ROOM + "/messages", payload, timeout=10.0)
    except urllib.error.URLError as exc:
        print("[counter-bot] post failed:", exc, file=sys.stderr)

# --- MAIN LOOP -------------------------------------------------------------

def run() -> None:
    counts: dict[str, int] = defaultdict(int)
    last_post = 0.0
    cursor: str | None = None

    print(f"[counter-bot] did={my_did()} room={ROOM} interval={INTERVAL}s")

    while True:
        # 1. Long-poll for new events.
        path = "/api/rooms/" + ROOM + "/events"
        if cursor:
            path += "?after=" + cursor
        try:
            events = http_json(path, timeout=max(5.0, INTERVAL))
        except urllib.error.URLError as exc:
            print("[counter-bot] poll error, retrying:", exc, file=sys.stderr)
            time.sleep(2.0)
            continue
        except (json.JSONDecodeError, TimeoutError):
            time.sleep(1.0)
            continue

        if isinstance(events, list) and events:
            cursor = events[-1].get("id", cursor)

        # 2. Tally every room.message event we have not yet counted.
        for ev in events or []:
            if ev.get("type") != "room.message":
                continue
            author = ev.get("author") or ev.get("did") or "<unknown>"
            counts[author] += 1

        # 3. Publish a leaderboard when the interval elapses.
        now = time.monotonic()
        if counts and now - last_post >= INTERVAL:
            top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
            lines = [f"{name}: {n}" for name, n in top]
            post_message("message counts (top 5) — " + ", ".join(lines))
            last_post = now


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("[counter-bot] bye")

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
