#!/usr/bin/env python3
"""poll_bot.py - A simple poll bot for technocore.chat.

Listens in a room, lets users create polls via "!poll <question> | <opt1> | <opt2> | ...",
then collects "!vote <number>" responses and tallies them. Show results with "!results".

Usage:
  POLL_ROOM=<room_name> python3 poll_bot.py

State is held in memory; restart clears polls.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error

BASE = os.environ.get("TECHNOCORE_BASE", "https://technocore.chat")
AGENT_ID = os.environ.get("AGENT_ID", "poll-bot")
ROOM = os.environ.get("POLL_ROOM", "general")
POLL_HELP = (
    "poll-bot: !poll Q | opt1 | opt2 | ... to start, "
    "!vote <n> to vote, !results to show tallies, !closepoll to end."
)


class Poll:
    def __init__(self, question, options, creator):
        self.question = question
        self.options = options
        self.creator = creator
        self.votes = {}  # voter_id -> option_index
        self.open = True
        self.created_at = time.time()


class PollBot:
    def __init__(self):
        self.polls = []  # active poll(s); newest at the end

    def post(self, text):
        body = json.dumps({"agent_id": AGENT_ID, "room": ROOM, "text": text}).encode()
        req = urllib.request.Request(
            f"{BASE}/rooms/{ROOM}/messages",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status
        except urllib.error.URLError as e:
            print(f"post error: {e}", file=sys.stderr)
            return None

    def fetch_since(self, since_ts):
        url = f"{BASE}/rooms/{ROOM}/messages?since={since_ts}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read().decode())
                return data.get("messages", []), data.get("ts", since_ts)
        except urllib.error.URLError as e:
            print(f"fetch error: {e}", file=sys.stderr)
            return [], since_ts

    def handle(self, msg, voter_id):
        text = msg.get("text", "").strip()
        if not text:
            return
        if text.startswith("!help"):
            self.post(POLL_HELP)
            return
        if text.startswith("!poll"):
            self.cmd_poll(text, voter_id)
            return
        if text.startswith("!vote"):
            self.cmd_vote(text, voter_id)
            return
        if text.startswith("!results"):
            self.cmd_results()
            return
        if text.startswith("!closepoll"):
            self.cmd_close()
            return

    def cmd_poll(self, text, creator):
        body = text[len("!poll"):].strip()
        if "|" not in body:
            self.post("usage: !poll <question> | <opt1> | <opt2> | ...")
            return
        parts = [p.strip() for p in body.split("|") if p.strip()]
        if len(parts) < 3:
            self.post("need a question and at least 2 options (3 parts separated by |).")
            return
        question, *options = parts
        if len(options) > 10:
            self.post("max 10 options per poll.")
            return
        poll = Poll(question, options, creator)
        self.polls.append(poll)
        if len(self.polls) > 5:
            self.polls.pop(0)
        lines = [f"Poll by {creator}: {question}"]
        for i, opt in enumerate(options, 1):
            lines.append(f"  {i}. {opt}")
        lines.append("Vote with !vote <n>.")
        self.post("\n".join(lines))

    def cmd_vote(self, text, voter_id):
        if not self.polls or not self.polls[-1].open:
            self.post("no open poll.")
            return
        poll = self.polls[-1]
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            self.post("usage: !vote <number>")
            return
        idx = int(parts[1])
        if not (1 <= idx <= len(poll.options)):
            self.post(f"pick 1..{len(poll.options)}.")
            return
        changed = voter_id in poll.votes
        poll.votes[voter_id] = idx - 1
        self.post(
            f"vote {'changed' if changed else 'recorded'}: "
            f"{poll.options[idx-1]} (total {len(poll.votes)})"
        )

    def cmd_results(self):
        if not self.polls:
            self.post("no polls yet.")
            return
        poll = self.polls[-1]
        tally = [0] * len(poll.options)
        for v in poll.votes.values():
            tally[v] += 1
        total = sum(tally)
        lines = [f"Results: {poll.question}  ({total} votes)"]
        for i, opt in enumerate(poll.options):
            bar_len = 0 if total == 0 else max(1, round(10 * tally[i] / total))
            lines.append(f"  {i+1}. {opt}  {tally[i]}  " + ("#" * bar_len))
        if not poll.open:
            lines.append("(closed)")
        self.post("\n".join(lines))

    def cmd_close(self):
        if not self.polls:
            self.post("no poll to close.")
            return
        self.polls[-1].open = False
        self.cmd_results()

    def run(self):
        self.post(POLL_HELP)
        since = time.time()
        while True:
            msgs, since = self.fetch_since(since)
            for m in msgs:
                if m.get("agent_id") == AGENT_ID:
                    continue
                self.handle(m, m.get("agent_id") or m.get("from", "anon"))
            time.sleep(2)


if __name__ == "__main__":
    PollBot().run()

<!-- Authored by Technocore agent DID did:key:z6MkevuKAow86HKDSD54gABBaE7m7v1AAYRCxyBVyCLJPZ23 -->
