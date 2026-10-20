#!/usr/bin/env python3
"""Ask Gemini to choose the day's games and make its own $1 picks.

Usage:
    GEMINI_API_KEY=... python3 betting/gemini_picks.py --date 2026-10-21 [--games 3]

Prints a JSON list of picks to stdout:
    [{"sport": "NBA", "matchup": "Philadelphia 76ers @ New York Knicks",
      "pick": "Knicks -4.5", "odds": "-110", "reason": "..."}]

Uses only the standard library. GEMINI_MODEL overrides the model.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-pro-latest"

PROMPT = """You are Gemini, competing against Claude in a daily sports betting tournament.
Each game gets a $1 stake. Today is {date}.

1. Search the web for the real games scheduled on {date} (any major sport or league).
2. Choose {games} games you want to bet on today.
3. For each game make ONE bet (moneyline, spread or total) with current sportsbook odds.

Write picks in this short style: "Knicks -4.5", "Thunder ML", "Over 221.5".
Write matchups as "Away Team @ Home Team" (or "Team A vs Team B" for soccer).

Reply with ONLY a JSON array, no other text:
[{{"sport": "...", "matchup": "...", "pick": "...", "odds": "...", "reason": "one sentence"}}]
"""


def ask_gemini(prompt, model, key):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }
    headers = {"Content-Type": "application/json"}
    if key:  # otherwise the environment's network secret supplies it
        headers["x-goog-api-key"] = key
    req = urllib.request.Request(
        API.format(model=model),
        data=json.dumps(body).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.load(resp)
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def parse_picks(text):
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        raise ValueError("no JSON array in Gemini reply:\n" + text)
    picks = json.loads(match.group(0))
    for p in picks:
        missing = {"sport", "matchup", "pick"} - p.keys()
        if missing:
            raise ValueError(f"pick missing {missing}: {p}")
    return picks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--games", type=int, default=3)
    args = parser.parse_args()

    key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    try:
        text = ask_gemini(PROMPT.format(date=args.date, games=args.games), model, key)
    except urllib.error.HTTPError as e:
        sys.exit(f"Gemini API error {e.code}: {e.read().decode()[:500]}")
    print(json.dumps(parse_picks(text), indent=2))


if __name__ == "__main__":
    main()
