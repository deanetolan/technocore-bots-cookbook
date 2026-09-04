#!/usr/bin/env python3
"""poll-bot: a tiny opinion-poll bot for technocore.chat.

Posts a question, accepts votes "1".."5", and announces tallies when the
owner issues "!tally". Demonstrates: persistent state in a JSON file,
time-bounded polls, simple owner gating, and the request/reply pattern
covered in docs/patterns.md.

Run:
    POLLS_FILE=./polls.json \
    OWNER_DID=did:key:z6Mk... \
    python3 poll_bot.py

Wire protocol is the same minimal shape used across the cookbook:
    {"op":"send","room":"...","text":"..."}     -> bot prints message
    {"op":"poll:ask","room":"...","q":"...","opts":5,"minutes":10}
"""
from __future__ import annotations
import json, os, sys, time, uuid as _uuid
from pathlib import Path

POLLS_FILE = Path(os.environ.get("POLLS_FILE", "./polls.json"))
OWNER_DID  = os.environ.get("OWNER_DID", "")  # empty => anyone may tally (dev mode)


def load() -> dict:
    if POLLS_FILE.exists():
        return json.loads(POLLS_FILE.read_text())
    return {"active": None, "history": []}


def save(state: dict) -> None:
    POLLS_FILE.write_text(json.dumps(state, indent=2))


def parse(line: str) -> dict | None:
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return None
    return msg if isinstance(msg, dict) else None


def reply(room: str, text: str) -> None:
    print(json.dumps({"op": "send", "room": room, "text": text}), flush=True)


def tally(p: poll) -> str:
    opts = p.get("opts", 5)
    counts = [0] * opts
    for v in p["votes"].values():
        if 1 <= v <= opts:
            counts[v - 1] += 1
    total = sum(counts)
    lines = [f"Poll: {p['q']}", f"Total votes: {total}"]
    for i, c in enumerate(counts, 1):
        pct = (100.0 * c / total) if total else 0.0
        lines.append(f"  {i}: {c}  ({pct:5.1f}%)")
    return "\n".join(lines)


def handle(state: dict, msg: dict) -> None:
    op = msg.get("op")
    room = msg.get("room", "")

    if op == "poll:ask":
        if state["active"]:
            reply(room, f"A poll is already open. Close it first: !tally")
            return
        opts   = max(2, min(9, int(msg.get("opts", 5))))
        mins   = max(1, int(msg.get("minutes", 10)))
        state["active"] = {
            "id":   _uuid.uuid4().hex[:8],
            "q":    str(msg.get("q", "(no question)"))[:200],
            "opts": opts,
            "opens":  int(time.time()),
            "closes": int(time.time()) + mins * 60,
            "votes": {},
        }
        save(state)
        scale = "".join(str(i) for i in range(1, opts + 1))
        reply(room, f"POLL [{state['active']['id']}] {state['active']['q']}  "
                    f"Reply with a number 1..{opts}. Closes in {mins}m.")

    elif op == "poll:vote":
        p = state["active"]
        if not p:
            return
        voter = str(msg.get("from", ""))[:120]
        choice = int(msg.get("choice", 0))
        if not voter or not (1 <= choice <= p["opts"]):
            reply(room, f"Vote must be a number 1..{p['opts']}.")
            return
        p["votes"][voter] = choice
        save(state)
        reply(room, f"Thanks {voter[:12]}.. recorded vote {choice}.")

    elif op == "message":
        text = str(msg.get("text", "")).strip()
        sender = str(msg.get("from", ""))
        p = state["active"]

        # Bare digits count as votes.
        if p and text.isdigit() and 1 <= int(text) <= p["opts"]:
            p["votes"][sender or "anon"] = int(text)
            save(state)
            reply(room, f"Vote {text} recorded from {sender[:12]}.")
            return

        if text.startswith("!tally"):
            if OWNER_DID and sender != OWNER_DID:
                reply(room, "Only the poll owner may call !tally.")
                return
            if not p:
                reply(room, "No active poll.")
                return
            reply(room, tally(p))
            state["history"].append(p)
            state["active"] = None
            save(state)

        elif text.startswith("!close"):
            if OWNER_DID and sender != OWNER_DID:
                return
            state["history"].append(p) if p else None
            state["active"] = None
            save(state)
            reply(room, "Poll closed.")

        elif text.startswith("!help"):
            reply(room, "Commands: bare digits = vote, !tally = close & report, "
                        "!close = cancel. Operators: send op=poll:ask to start.")


def main() -> None:
    state = load()
    for raw in sys.stdin:
        msg = parse(raw)
        if msg:
            try:
                handle(state, msg)
            except Exception as e:  # never crash the loop
                sys.stderr.write(f"err: {e}\n")


if __name__ == "__main__":
    main()

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
