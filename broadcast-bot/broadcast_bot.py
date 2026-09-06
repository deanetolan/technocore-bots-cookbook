# broadcast_bot.py - fan-out broadcaster for technocore.chat
#
# A simple, copy-pasteable example showing how to publish a single message
# into multiple rooms at once. Useful for announcements, alert bots, and
# cross-room notifications.
#
# Usage:
#   1. Run: python broadcast_bot.py
#   2. It connects, joins ROOMS, and waits for !broadcast <text> commands
#      in any joined room.
#   3. The same text is then sent to every other room in ROOMS.
#
# Notes:
#   - The originating room is excluded from the fan-out to avoid echo spam.
#   - Uses a short per-room cooldown so the bot cannot be used to flood.
#
# Requires: a websockets client. Tested with `websockets>=11`.
#   pip install websockets

import asyncio
import json
import time
from collections import defaultdict

import websockets

# --- Config ---------------------------------------------------------------

HOST = "technocore.chat"
PORT = 80
# Adjust to taste. Each entry is the room name (without the leading slash).
ROOMS = ["general", "announcements", "lobby"]
COOLDOWN_SECONDS = 30          # per-source-room cooldown after each broadcast
MAX_MESSAGE_LEN = 4000         # safety cap; protocol limit is 4000 chars
PREFIX = "!broadcast"          # command trigger

# --- Connection -----------------------------------------------------------

async def connect():
    uri = f"ws://{HOST}:{PORT}/"
    ws = await websockets.connect(uri)
    # First frame after connect is expected to be a hello.
    hello = json.loads(await ws.recv())
    print(f"[hello] {hello}")
    return ws

async def send(ws, obj):
    await ws.send(json.dumps(obj))

async def join(ws, room):
    await send(ws, {"type": "join", "room": room})

async def post(ws, room, text):
    await send(ws, {"type": "post", "room": room, "text": text})

# --- Bot logic ------------------------------------------------------------

last_broadcast_at: dict[str, float] = defaultdict(float)

def is_command(text: str) -> bool:
    return text.strip().startswith(PREFIX)

def extract_payload(text: str) -> str:
    payload = text.strip()[len(PREFIX):].strip()
    return payload[:MAX_MESSAGE_LEN]

async def handle_broadcast(ws, source_room: str, payload: str):
    now = time.monotonic()
    if now - last_broadcast_at[source_room] < COOLDOWN_SECONDS:
        wait = int(COOLDOWN_SECONDS - (now - last_broadcast_at[source_room]))
        await post(ws, source_room, f"(broadcast cooldown: {wait}s left)")
        return
    if not payload:
        await post(ws, source_room, "(usage: !broadcast <message>)")
        return
    last_broadcast_at[source_room] = now
    delivered = 0
    for room in ROOMS:
        if room == source_room:
            continue
        await post(ws, room, payload)
        delivered += 1
        # Tiny pacing gap so we never burst the server.
        await asyncio.sleep(0.05)
    await post(ws, source_room, f"(broadcast delivered to {delivered} room(s))")

async def run():
    ws = await connect()
    for room in ROOMS:
        await join(ws, room)
        print(f"[joined] {room}")

    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        mtype = msg.get("type")
        if mtype != "message":
            # Could be 'presence', 'ack', 'error' etc. Ignore for this bot.
            continue

        room = msg.get("room", "")
        text = msg.get("text", "")
        if room not in ROOMS:
            continue
        if is_command(text):
            await handle_broadcast(ws, room, extract_payload(text))

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("bye")

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
