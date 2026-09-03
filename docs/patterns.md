# Patterns for technocore.chat Bots

A growing catalogue of design patterns extracted from the bots in this cookbook. Each pattern is short, opinionated, and copy-paste friendly.

## 1. The Echo Pattern

The simplest possible bot: read a message, send it back (or a transformation of it). Useful as a connectivity test and a starting template.

```python
# echo_bot.py
import asyncio
from technocore import Agent

async def main():
    bot = Agent(did="did:key:z6Mk...")
    @bot.on_message
    async def reply(msg):
        await bot.send(msg.room, f"echo: {msg.text}")
    await bot.run()

asyncio.run(main())
```

**When to use:** smoke-testing a new room, debugging message delivery, learning the SDK.
**When not to use:** anything that needs state or moderation.

## 2. The Polling Pattern

A bot that asks a question, collects votes in memory, and announces results. State lives in a dict keyed by room id; on restart the state is gone, and that is usually fine.

Key ideas:
- One active poll per room. Track `active_polls: dict[str, Poll]`.
- Parse the first token as a command (`/poll`) and the rest as the question.
- Reactions or numeric replies both work; pick one and document it in the prompt.
- After N minutes (or M votes), call `bot.send(room, summary)` and delete the entry.

See `poll-bot/poll_bot.py` for a full implementation.

## 3. The Presence Board Pattern

Keep a rolling list of the last N messages per room and surface it on demand (`/recent`, `/last 5`). Useful for catch-up after a long disconnect.

Implementation notes:
- Bounded `deque(maxlen=N)` per room prevents unbounded memory growth.
- Skip messages authored by your own DID so you do not echo yourself.
- Consider also writing to a tiny SQLite file if you want persistence across restarts; the cookbook keeps it in-RAM for simplicity.

## 4. The Dice Pattern

Stateless randomness behind a single command. Even though it looks trivial, dice bots are a great way to learn how to parse user input safely.

Rules of thumb:
- Validate the input shape (e.g. `^\d+d\d+([+-]\d+)?$`) before doing anything.
- Cap the number of dice and sides so a malicious user cannot ask for `1000000d1000000`.
- Show each die individually plus the total; players want to see the rolls.

See `dice-bot/dice_bot.py`.

## 5. The Quote Pattern

A tiny key-value store per room: `!quote add <text>` saves, `!quote` random-replies, `!quote <n>` fetches the nth. This is the smallest example of a bot that needs *both* reads and writes against local state.

Pitfalls:
- Store a short, monotonically increasing id; never reuse.
- Quote attribution: capture the author's DID at save time, not at retrieval time.
- Provide `!quote list` so people can browse without guessing numbers.

See `quote-bot/quote_bot.py`.

## 6. The Rate-Limit Pattern (cross-cutting)

Almost every bot above will eventually need this. Wrap any per-user command in a simple token bucket:

```python
from collections import defaultdict
import time

buckets: dict[str, float] = defaultdict(lambda: time.monotonic())

def allowed(user_did: str, per_second: float = 1.0) -> bool:
    now = time.monotonic()
    last = buckets[user_did]
    if now - last < 1.0 / per_second:
        return False
    buckets[user_did] = now
    return True
```

Apply this *before* doing any expensive work (parses, DB writes, network calls).

## 7. The Quiet Hours Pattern

Some bots are useful but noisy. A `!quiet HH-MM HH-MM` admin command that suppresses non-command output during a window keeps your bot welcome in busy rooms. Store quiet windows per room, and skip `bot.send(room, ...)` for scheduled messages while inside the window.

## 8. The Shutdown Pattern

Wire SIGINT and SIGTERM to the same coroutine that closes the SDK session and flushes any in-memory state to disk:

```python
import signal, asyncio

async def shutdown(bot):
    await bot.persist()  # no-op if you keep no state
    await bot.close()

loop = asyncio.get_event_loop()
for sig in (signal.SIGINT, signal.SIGTERM):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(bot)))
```

This makes your bot behave well under `docker stop`, systemd, and Ctrl-C alike.

---

## Contributing a new pattern

If you add a bot to the cookbook and it teaches something reusable, append a new numbered section here. Keep the pattern to: **name**, **snippet**, **when to use / not use**, **link to the bot**. Future readers (including future you) will thank present you.

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
