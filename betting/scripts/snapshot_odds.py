"""Take one odds snapshot for the day so every player sees identical lines.

Usage:
  python3 scripts/snapshot_odds.py                 # fetch from The Odds API
  python3 scripts/snapshot_odds.py --from-file raw.json   # build from a saved odds response (testing)
Writes data/slates/YYYY-MM-DD.json. Refuses to overwrite an existing slate unless --force.
"""
import argparse
import json
from datetime import timedelta

from common import SLATES, american, load_config, now_utc, odds_api_get, parse_time, today

SIDE_NAMES = {"h2h": "ML", "spreads": "SPREAD", "totals": "TOTAL"}


def pick_bookmaker(event, prefs):
    books = {b["key"]: b for b in event.get("bookmakers", [])}
    for key in prefs:
        if key in books:
            return books[key]
    return next(iter(books.values()), None)


def build_game(event, sport, prefs, idx):
    book = pick_bookmaker(event, prefs)
    if not book:
        return None
    gid = f"G{idx:02d}"
    home, away = event["home_team"], event["away_team"]
    options = []
    for market in book.get("markets", []):
        mkey = market["key"]
        for o in market["outcomes"]:
            if mkey == "totals":
                side = o["name"].lower()  # over / under
                label = f"{o['name']} {o['point']}"
            else:
                side = "home" if o["name"] == home else "away" if o["name"] == away else "draw"
                label = o["name"] if mkey == "h2h" else f"{o['name']} {o['point']:+g}"
                if mkey == "h2h":
                    label += " ML"
            price = float(o["price"])
            options.append({
                "id": f"{gid}-{SIDE_NAMES[mkey]}-{side.upper()}",
                "market": mkey,
                "side": side,
                "point": o.get("point"),
                "label": label,
                "price_decimal": price,
                "price_american": american(price),
            })
    if not options:
        return None
    return {
        "game_id": gid,
        "event_id": event["id"],
        "sport": sport,
        "commence_time": event["commence_time"],
        "home": home,
        "away": away,
        "matchup": f"{away} @ {home}",
        "bookmaker": book["key"],
        "options": options,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-file", help="JSON file: {sport_key: [odds-api events]}")
    ap.add_argument("--date", default=today())
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    out = SLATES / f"{args.date}.json"
    if out.exists() and not args.force:
        raise SystemExit(f"{out} already exists; slate is locked for the day.")

    now = now_utc()
    horizon = now + timedelta(hours=cfg["slate_window_hours"])
    if args.from_file:
        raw = json.loads(open(args.from_file).read())
    else:
        raw = {}
        for sport in cfg["sports"]:
            print(f"fetching {sport}")
            try:
                raw[sport] = odds_api_get(
                    f"/sports/{sport}/odds",
                    regions=cfg["regions"],
                    markets=",".join(cfg["markets"]),
                    oddsFormat="decimal",
                    commenceTimeFrom=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    commenceTimeTo=horizon.strftime("%Y-%m-%dT%H:%M:%SZ"),
                )
            except Exception as e:  # off-season sports 404/422; skip them
                print(f"  skipped: {e}")

    # Games already offered on an earlier day's slate are not offered again.
    seen = {g["event_id"] for f in SLATES.glob("*.json") if f != out for g in json.loads(f.read_text())["games"]}
    games = []
    for sport, events in raw.items():
        for ev in sorted(events, key=lambda e: e["commence_time"]):
            start = parse_time(ev["commence_time"])
            if not (now < start <= horizon) or ev["id"] in seen:
                continue
            g = build_game(ev, sport, cfg["bookmaker_preference"], len(games) + 1)
            if g:
                games.append(g)

    SLATES.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "date": args.date,
        "snapshot_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stake": cfg["stake"],
        "max_picks": cfg["max_picks_per_player_per_day"],
        "games": games,
    }, indent=2))
    print(f"wrote {out} with {len(games)} games")


if __name__ == "__main__":
    main()
