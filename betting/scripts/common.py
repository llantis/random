"""Shared paths, config loading, odds helpers and ledger I/O."""
import csv
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SLATES = DATA / "slates"
PICKS = DATA / "picks"
LEDGER = DATA / "ledger.csv"
ODDS_API = "https://api.the-odds-api.com/v4"

LEDGER_FIELDS = [
    "date", "player", "model", "effort", "sport", "matchup", "game_id",
    "commence_time", "option_id", "pick", "price_decimal", "price_american",
    "stake", "confidence", "reason", "placed_at", "result", "pnl",
]


def load_config():
    return json.loads((ROOT / "config.json").read_text())


def now_utc():
    return datetime.now(timezone.utc)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def today():
    # Slates are keyed by the US Eastern calendar day.
    return now_utc().astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def american(decimal_odds):
    if decimal_odds >= 2.0:
        return f"+{round((decimal_odds - 1) * 100)}"
    return f"-{round(100 / (decimal_odds - 1))}"


def odds_api_get(path, **params):
    key = os.environ.get("ODDS_API_KEY")
    if not key:
        raise SystemExit("ODDS_API_KEY is not set (add it as an environment secret).")
    params["apiKey"] = key
    url = f"{ODDS_API}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        remaining = resp.headers.get("x-requests-remaining")
        if remaining is not None:
            print(f"  odds-api requests remaining: {remaining}")
        return json.loads(resp.read())


def read_ledger():
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline="") as f:
        return list(csv.DictReader(f))


def write_ledger(rows):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        w.writerows(rows)
