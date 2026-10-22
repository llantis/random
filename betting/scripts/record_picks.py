"""Validate one player's picks against the day's slate and lock them into the ledger.

Usage: python3 scripts/record_picks.py <player> <picks.json> [--date YYYY-MM-DD]
picks.json: {"picks": [{"option_id": "G03-ML-HOME", "confidence": 0.58, "reason": "..."}]}

This is the only path into the ledger, so every rule is enforced here, not in prompts:
known player, option exists in the slate, game not started, one pick per game,
at most max_picks, fixed stake, and a player's picks can only be recorded once per day.
"""
import argparse
import json

from common import PICKS, SLATES, load_config, now_utc, parse_time, read_ledger, today, write_ledger


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("picks_file")
    ap.add_argument("--date", default=today())
    args = ap.parse_args()

    cfg = load_config()
    player = next((p for p in cfg["players"] if p["name"] == args.player), None)
    if not player:
        raise SystemExit(f"unknown player {args.player!r}")

    slate = json.loads((SLATES / f"{args.date}.json").read_text())
    options = {o["id"]: (g, o) for g in slate["games"] for o in g["options"]}

    out = PICKS / args.date / f"{args.player}.json"
    if out.exists():
        raise SystemExit(f"{args.player} already has locked picks for {args.date}")

    submitted = json.loads(open(args.picks_file).read()).get("picks", [])
    now = now_utc()
    accepted, rejected, seen_games = [], [], set()
    for p in submitted:
        oid = p.get("option_id")
        if oid not in options:
            rejected.append((oid, "not in slate"))
            continue
        game, opt = options[oid]
        if parse_time(game["commence_time"]) <= now:
            rejected.append((oid, "game already started"))
            continue
        if game["game_id"] in seen_games:
            rejected.append((oid, "second pick on same game"))
            continue
        if len(accepted) >= cfg["max_picks_per_player_per_day"]:
            rejected.append((oid, "over daily pick limit"))
            continue
        try:
            conf = min(max(float(p.get("confidence", 0.5)), 0.0), 1.0)
        except (TypeError, ValueError):
            conf = 0.5
        seen_games.add(game["game_id"])
        accepted.append({
            "date": args.date,
            "player": player["name"],
            "model": player["model"],
            "effort": player["effort"],
            "sport": game["sport"],
            "matchup": game["matchup"],
            "game_id": game["event_id"],
            "commence_time": game["commence_time"],
            "option_id": oid,
            "pick": opt["label"],
            "price_decimal": opt["price_decimal"],
            "price_american": opt["price_american"],
            "stake": cfg["stake"],
            "confidence": round(conf, 3),
            "reason": " ".join(str(p.get("reason", "")).split())[:300],
            "placed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result": "",
            "pnl": "",
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    write_ledger(read_ledger() + accepted)
    print(f"{args.player}: {len(accepted)} accepted, {len(rejected)} rejected")
    for oid, why in rejected:
        print(f"  rejected {oid}: {why}")


if __name__ == "__main__":
    main()
