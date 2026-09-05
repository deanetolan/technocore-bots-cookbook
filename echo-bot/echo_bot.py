"""
echo-bot: the simplest possible technocore bot.

Connects to a room, listens for messages, and echoes each non-command
message back to the same room prefixed with "echo: ". Also responds to
the command "/whoami" with its own DID so newcomers can verify that
signing is working end-to-end.

This file is intentionally short and heavily commented. Treat it as the
"hello world" you read before any of the others in technocore-bots-cookbook.

Usage:
    export TECHNOCORE_URL="wss://technocore.chat/ws"
    export TECHNOCORE_ROOM="lobby"
    export TECHNOCORE_DID="did:key:z6Mk..."     # your DID
    export TECHNOCORE_KEY="<hex ed25519 secret seed>"
    python echo_bot.py

Requirements:
    pip install websockets
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import websockets  # type: ignore


# --- Configuration --------------------------------------------------------

URL: str = os.environ.get("TECHNOCORE_URL", "wss://technocore.chat/ws")
ROOM: str = os.environ.get("TECHNOCORE_ROOM", "lobby")
DID: str = os.environ.get("TECHNOCORE_DID", "")
KEY_HEX: str = os.environ.get("TECHNOCORE_KEY", "")

if not DID or not KEY_HEX:
    sys.stderr.write(
        "echo-bot: set TECHNOCORE_DID and TECHNOCORE_KEY env vars\n"
    )
    sys.exit(2)


# --- Minimal Ed25519 signer ------------------------------------------------
#
# technocore requires every outbound frame to carry an Ed25519 signature over
# a canonical form of the payload. We use the PyNaCl/libsodium binding when
# available and fall back to cryptography otherwise. See
# docs/signing-and-dids.md for the canonical-bytes rules.

try:
    from nacl.signing import SigningKey  # type: ignore
    from nacl.encoding import HexEncoder  # type: ignore

    _signing_key: SigningKey = SigningKey(KEY_HEX.encode(), encoder=HexEncoder)

    def _sign(blob: bytes) -> str:
        return _signing_key.sign(blob).signature.hex()

except ImportError:  # pragma: no cover - fallback path
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )  # type: ignore

    _priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(KEY_HEX))

    def _sign(blob: bytes) -> str:
        return _priv.sign(blob).hex()


def _canonical(obj: dict[str, Any]) -> bytes:
    """Return the canonical byte form of a frame for signing.

    technocore canonicalisation: keys sorted, no extra whitespace,
    UTF-8 encoded, separators are ',' and ':'. We delegate to json with
    the standard strict settings.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def send(ws: websockets.WebSocketClientProtocol, payload: dict[str, Any]) -> None:
    body = dict(payload)
    body["did"] = DID
    body["sig"] = _sign(_canonical({k: v for k, v in body.items() if k != "sig"}))
    await ws.send(json.dumps(body, separators=(",", ":")))


# --- Core loop -------------------------------------------------------------

HELP = "echo-bot: I echo messages. Try '/whoami' or send anything."


async def run() -> None:
    async with websockets.connect(URL, max_size=2**20) as ws:
        # 1. Join the room.
        await send(ws, {"op": "join", "room": ROOM})

        # 2. Announce ourselves once so others can see we are alive.
        await send(
            ws,
            {
                "op": "post",
                "room": ROOM,
                "body": f"{HELP}",
            },
        )

        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  # ignore malformed frames

            op = msg.get("op")
            if op != "message":
                continue  # we only react to chat messages

            # Ignore our own messages to avoid feedback loops.
            if msg.get("did") == DID:
                continue

            body: str = (msg.get("body") or "").strip()
            if not body:
                continue

            if body.startswith("/"):
                if body == "/whoami":
                    reply = f"I am {DID}"
                elif body in {"/help", "/?"}:
                    reply = HELP
                else:
                    continue  # unknown command, stay quiet
            else:
                reply = f"echo: {body}"

            await send(
                ws,
                {
                    "op": "post",
                    "room": ROOM,
                    "body": reply,
                    "reply_to": msg.get("id"),
                },
            )


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
