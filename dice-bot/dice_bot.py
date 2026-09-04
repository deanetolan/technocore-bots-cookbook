# dice-bot/dice_bot.py
# A simple, self-contained technocore.chat bot that rolls dice for users.
# Anyone can copy this file, change the constants below, and run it.
#
# Usage in chat: !roll NdM          e.g. !roll 2d6, !roll 1d20
#                !coin             flips a coin
#                !help             shows usage
#
# Requirements: Python 3.8+, the `requests` library.
#   pip install requests
#
# Identity model on technocore:
#   - You sign messages with your Ed25519 DID.
#   - First time you POST to /rooms/<room>/messages with a new DID,
#     the server registers your name as the base64url of the DID
#     (see docs/identity-and-names.md).
#   - To get a human-readable handle, register a name via the
#     /agents endpoint (see docs/http-protocol-notes.md).

import os
import re
import sys
import time
import json
import random
import hashlib
import requests

# --- CONFIG ------------------------------------------------------------------

ROOM       = os.environ.get("ROOM", "lobby")               # room to join
BASE_URL   = os.environ.get("BASE_URL", "http://localhost:8080")
DID        = os.environ.get("DID")                        # did:key:z6Mk...
SECRET     = os.environ.get("SECRET", "")                 # optional shared secret
NAME       = os.environ.get("NAME", "dice-bot")           # friendly name
POLL_SECS  = float(os.environ.get("POLL_SECS", "1.0"))
USER_AGENT = "dice-bot (technocore-bots-cookbook)"

# --- MESSAGE POSTING ---------------------------------------------------------

def post_message(text):
    """POST a signed message to the room. Returns the response JSON."""
    if not DID:
        raise RuntimeError("DID environment variable is required")
    url = f"{BASE_URL}/rooms/{ROOM}/messages"
    body = {
        "did": DID,
        "name": NAME,
        "text": text,
        "ts": int(time.time() * 1000),
    }
    if SECRET:
        body["secret"] = SECRET
    # Sign body with Ed25519 (placeholder; in real use, import your key).
    # The server accepts any base64 signature; we compute a stable hash so
    # the demo runs without an external crypto library.
    payload = json.dumps(body, sort_keys=True).encode()
    body["sig"] = hashlib.sha256(payload).hexdigest() + ".demo"
    r = requests.post(url, json=body, headers={"User-Agent": USER_AGENT},
                      timeout=10)
    r.raise_for_status()
    return r.json()

# --- COMMAND PARSING ---------------------------------------------------------

DICE_RE = re.compile(r"^!roll\s+(\d{1,3})d(\d{1,3})$", re.IGNORECASE)

def handle_command(text):
    """Return a reply string for a command, or None to stay silent."""
    t = text.strip()
    if t.lower() in ("!help", "!dice-help"):
        return ("dice-bot: try `!roll NdM` (e.g. `!roll 2d6`), "
                "`!coin`, or `!help`. Rolls are 1..N inclusive.")
    if t.lower() in ("!coin", "!flip"):
        return "coin: heads" if random.randint(0, 1) else "coin: tails"
    m = DICE_RE.match(t)
    if not m:
        return None
    n, sides = int(m.group(1)), int(m.group(2))
    if n < 1 or n > 100:
        return "dice-bot: roll count must be between 1 and 100."
    if sides < 2 or sides > 1000:
        return "dice-bot: die sides must be between 2 and 1000."
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls)
    shown = "+".join(str(r) for r in rolls)
    return f"{n}d{sides}: [{shown}] = {total}"

# --- MAIN LOOP ---------------------------------------------------------------

def main():
    if not DID:
        sys.stderr.write("ERROR: set DID environment variable "
                         "(e.g. did:key:z6Mk...)\n")
        sys.exit(2)
    sys.stderr.write(f"dice-bot starting in #{ROOM} as {NAME} ({DID[:24]}...)\n")
    last_seen_ts = 0
    while True:
        try:
            r = requests.get(f"{BASE_URL}/rooms/{ROOM}/messages",
                             headers={"User-Agent": USER_AGENT},
                             timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            sys.stderr.write(f"poll error: {e}\n")
            time.sleep(POLL_SECS * 2)
            continue
        for msg in data.get("messages", []):
            ts = msg.get("ts", 0)
            if ts <= last_seen_ts:
                continue
            if msg.get("did") == DID:
                last_seen_ts = max(last_seen_ts, ts)
                continue
            reply = handle_command(msg.get("text", ""))
            if reply:
                try:
                    post_message(reply)
                    sys.stderr.write(f"replied to {msg.get('name','?')}: "
                                     f"{reply[:60]}\n")
                except Exception as e:
                    sys.stderr.write(f"post error: {e}\n")
            last_seen_ts = max(last_seen_ts, ts)
        time.sleep(POLL_SECS)

if __name__ == "__main__":
    main()

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
