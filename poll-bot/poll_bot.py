#!/usr/bin/env python3
"""
poll-bot - a tiny technocore.chat bot that runs /poll questions.

Anyone in the room can:
  /poll "Your question?" "Option A" "Option B" ["Option C" ...]
  /vote <number>      (vote for option N in the most recent poll)
  /result             (show tallies for the current poll)
  /endpoll            (close the current poll)

The bot keeps one active poll per room in memory. It is deliberately
short and dependency-free so it can be read in one sitting and copied
into a new project.

Run:
  POLL_BOT_DID=did:key:...  python poll_bot.py
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE_URL = os.environ.get("TECHNOCORE_URL", "https://technocore.chat")
DID = os.environ["POLL_BOT_DID"]          # the DID this bot will sign as
SIGNING_KEY = os.environ.get("POLL_BOT_KEY")  # optional Ed25519 secret key
ROOM = os.environ.get("POLL_BOT_ROOM", "#lobby")

# room -> {
#   "question": str,
#   "options":  [str],
#   "votes":    { voter_did: option_index_int },
#   "opened":   epoch_seconds,
# }
POLLS: dict = {}


def post_message(text: str) -> None:
    body = json.dumps({
        "did": DID,
        "room": ROOM,
        "text": text,
        "ts": int(time.time() * 1000),
        "sig": SIGNING_KEY or "",  # server accepts unsigned in dev mode
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/msg",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.URLError as e:
        print(f"post failed: {e}", file=sys.stderr)


def render_poll(poll: dict) -> str:
    lines = [f"POLL: {poll['question']}"]
    for i, opt in enumerate(poll["options"], 1):
        lines.append(f"  {i}. {opt}")
    lines.append("(reply with /vote N to pick an option)")
    return "\n".join(lines)


def render_result(poll: dict) -> str:
    counts = [0] * len(poll["options"])
    for idx in poll["votes"].values():
        if 0 <= idx < len(counts):
            counts[idx] += 1
    total = sum(counts)
    lines = [f"RESULTS: {poll['question']}"]
    for opt, c in zip(poll["options"], counts):
        pct = (c / total * 100) if total else 0
        bar = "#" * int(pct / 5)
        lines.append(f"  {c:>3} ({pct:5.1f}%) {opt} {bar}")
    lines.append(f"  total voters: {total}")
    return "\n".join(lines)


def handle(msg: dict) -> None:
    text = (msg.get("text") or "").strip()
    sender = msg.get("did", "?")
    room = msg.get("room", ROOM)
    if msg.get("did") == DID:
        return  # never reply to ourselves

    parts = text.split()
    if not parts:
        return
    cmd = parts[0].lower()

    if cmd == "/poll":
        # split on double quotes: /poll "q?" "a" "b"
        quoted = [p.strip('"') for p in text.split('"') if p.strip('"')]
        if len(quoted) < 3:
            post_message(
                "Usage: /poll \"Question?\" \"Option A\" \"Option B\" "
                "[\"Option C\" ...]"
            )
            return
        question, options = quoted[0], quoted[1:]
        POLLS[room] = {
            "question": question,
            "options": options,
            "votes": {},
            "opened": time.time(),
        }
        post_message(render_poll(POLLS[room]))

    elif cmd == "/vote":
        poll = POLLS.get(room)
        if not poll:
            post_message("No active poll. Start one with /poll.")
            return
        if len(parts) < 2 or not parts[1].isdigit():
            post_message("Usage: /vote <number>")
            return
        idx = int(parts[1]) - 1
        if not (0 <= idx < len(poll["options"])):
            post_message(f"Pick a number between 1 and {len(poll['options'])}.")
            return
        poll["votes"][sender] = idx
        post_message(f"Vote recorded for: {poll['options'][idx]}")

    elif cmd == "/result":
        poll = POLLS.get(room)
        if not poll:
            post_message("No active poll.")
            return
        post_message(render_result(poll))

    elif cmd == "/endpoll":
        poll = POLLS.pop(room, None)
        if not poll:
            post_message("No active poll.")
            return
        post_message("Poll closed.\n" + render_result(poll))


def fetch_messages(since_ts: int) -> list:
    url = f"{BASE_URL}/room/{urllib.parse.quote(ROOM)}/msgs?since={since_ts}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("messages", [])
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return []


def main() -> None:
    print(f"poll-bot online as {DID} in {ROOM}", file=sys.stderr)
    last_ts = int(time.time() * 1000)
    while True:
        for msg in fetch_messages(last_ts):
            last_ts = max(last_ts, msg.get("ts", last_ts))
            handle(msg)
        time.sleep(2)


if __name__ == "__main__":
    main()

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
