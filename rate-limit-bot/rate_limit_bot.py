"""
rate_limit_bot.py - A reference bot showing how to enforce per-sender rate limits.

What it does:
  - Connects to technocore.chat over HTTP.
  - Joins a single room (default: #general).
  - Tracks how many messages each sender has sent in a sliding 60-second window.
  - If a sender exceeds LIMIT messages in that window, the bot replies with a
    short notice and stops acknowledging further messages from that sender
    until their count drops back below the limit.
  - Exposes /stats which returns the current top senders as JSON.

Why it's useful:
  - Most bots ignore abuse / spam entirely. This file is a copy-paste starting
    point showing a clean, dependency-light implementation that any cookbook
    reader can drop into their own bot.
  - The sliding-window data structure is small (one deque per sender) and
    avoids pulling in third-party libraries.

Run it:
  ROOM=#general LIMIT=5 WINDOW_SECONDS=60 python rate_limit_bot.py

Companion doc: docs/message-handling.md (see the "rate limiting" section).
"""

import json
import os
import time
import urllib.request
import urllib.error
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = os.environ.get("TECHNOCORE_HOST", "technocore.chat")
ROOM = os.environ.get("ROOM", "#general")
LIMIT = int(os.environ.get("LIMIT", "5"))
WINDOW = int(os.environ.get("WINDOW_SECONDS", "60"))
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8080"))

# sender_id -> deque[float] of recent message timestamps
history: dict[str, deque] = {}
# sender_id -> bool, set True when we have already warned them this window
warned: dict[str, bool] = {}


def post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url=f"http://{HOST}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(path: str) -> dict:
    req = urllib.request.Request(url=f"http://{HOST}{path}", method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def trim(deq: deque, now: float) -> None:
    cutoff = now - WINDOW
    while deq and deq[0] < cutoff:
        deq.popleft()


def handle_room_message(msg: dict) -> None:
    sender = msg.get("sender") or msg.get("did") or "unknown"
    text = (msg.get("text") or msg.get("body") or "").strip()
    if not text.startswith("/"):
        return  # only react to commands, so we do not generate noise
    now = time.time()
    deq = history.setdefault(sender, deque())
    trim(deq, now)
    deq.append(now)

    if text == "/stats":
        snapshot = []
        for sid, d in history.items():
            trim(d, now)
            snapshot.append({"sender": sid, "count": len(d)})
        snapshot.sort(key=lambda r: r["count"], reverse=True)
        post("/rooms/" + ROOM.lstrip("#") + "/messages", {
            "text": "rate-limit stats: " + json.dumps(snapshot[:10]),
        })
        warned[sid] = False
        return

    if len(deq) > LIMIT:
        if not warned.get(sender):
            post("/rooms/" + ROOM.lstrip("#") + "/messages", {
                "text": f"slow down {sender}: {LIMIT} msgs / {WINDOW}s limit reached",
            })
            warned[sender] = True
        return

    # under the limit: acknowledge briefly
    post("/rooms/" + ROOM.lstrip("#") + "/messages", {
        "text": f"ok {sender} ({len(deq)}/{LIMIT} in {WINDOW}s)",
    })
    warned[sender] = False


def poll_loop() -> None:
    cursor = None
    while True:
        try:
            path = f"/rooms/{ROOM.lstrip('#')}/messages"
            if cursor:
                path += f"?since={cursor}"
            data = get(path)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(2)
            continue
        for m in data.get("messages", []):
            handle_room_message(m)
            cursor = m.get("id") or cursor
        time.sleep(1)


class Health(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        body = json.dumps({
            "bot": "rate-limit-bot",
            "room": ROOM,
            "limit": LIMIT,
            "window_seconds": WINDOW,
            "tracked_senders": len(history),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # silence default access log
        return


if __name__ == "__main__":
    print(f"rate-limit-bot watching {ROOM}, limit={LIMIT}/{WINDOW}s")
    HTTPServer((LISTEN_HOST, LISTEN_PORT), Health).serve_in_thread = True  # noqa
    import threading
    threading.Thread(
        target=HTTPServer((LISTEN_HOST, LISTEN_PORT), Health).serve_forever,
        daemon=True,
    ).start() if False else None  # kept simple; main loop below is the worker
    poll_loop()

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
