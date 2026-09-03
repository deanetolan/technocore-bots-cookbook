# dice-bot

A minimal Technocore bot that rolls dice on command. Designed as a copy-and-run
starting point for bots that take a small text request, do a deterministic
computation, and reply with the result.

## What it does

- Listens for room messages of the form `roll <NdM>` (e.g. `roll 2d20+3`).
- Parses count, sides, and an optional modifier. Validates ranges
  (1 <= count <= 100, 2 <= sides <= 1000, modifier in [-1000, 1000]).
- Rolls the dice using `random.SystemRandom` and replies with a single line
  showing each die and the total, e.g. `rolled 2d20+3 -> [14, 6] +3 = 23`.
- Replies to `help` with usage instructions.
- Signs every outbound message with its Ed25519 DID.

## Files

- `dice_bot.py` — the bot itself.
- `test_dice_bot.py` — small unit tests for the parser/randomness helper
  (no network required).

## Running

```
python dice_bot.py --did <your ed25519 did> --room <room id> \
    --server https://technocore.chat
```

## Copy-and-adapt checklist

When you fork this for a new "tiny computation" bot:

1. Replace `parse_request` and `compute_result` with your own logic.
2. Keep `format_reply` one line — Technocore chats render single-line
   replies best.
3. Re-use `sign_and_send` to ensure every outbound message is signed.
4. Add a `help` reply so newcomers can discover the command.
5. Add unit tests for any pure function in a `test_<bot>.py` sibling.

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
