"""Settle ungraded ledger rows from final scores. No player grades its own bets.

Usage:
  python3 scripts/grade.py                         # fetch scores from The Odds API (last 3 days)
  python3 scripts/grade.py --scores-file s.json    # {sport_key: [odds-api score events]} (testing)
"""
import argparse
import json

from common import load_config, odds_api_get, read_ledger, write_ledger


def outcome(row, ev):
    """Return 'win' / 'loss' / 'push' for a ledger row given a completed score event."""
    scores = {s["name"]: float(s["score"]) for s in ev["scores"]}
    home, away = scores[ev["home_team"]], scores[ev["away_team"]]
    market, side = row["option_id"].split("-")[1:3]
    if market == "ML":
        winner = "HOME" if home > away else "AWAY" if away > home else "DRAW"
        return "win" if side == winner else "loss"
    point = float(row["pick"].rsplit(" ", 1)[1])
    if market == "SPREAD":
        margin = (home - away) if side == "HOME" else (away - home)
        diff = margin + point
    else:  # TOTAL
        total = home + away
        diff = (total - point) if side == "OVER" else (point - total)
    return "win" if diff > 0 else "loss" if diff < 0 else "push"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores-file")
    args = ap.parse_args()

    rows = read_ledger()
    open_rows = [r for r in rows if not r["result"]]
    if not open_rows:
        print("nothing to grade")
        return

    if args.scores_file:
        raw = json.loads(open(args.scores_file).read())
    else:
        raw = {}
        for sport in sorted({r["sport"] for r in open_rows}):
            print(f"fetching scores for {sport}")
            raw[sport] = odds_api_get(f"/sports/{sport}/scores", daysFrom=3)

    events = {ev["id"]: ev for evs in raw.values() for ev in evs if ev.get("completed") and ev.get("scores")}
    graded = 0
    for r in open_rows:
        ev = events.get(r["game_id"])
        if not ev:
            continue
        res = outcome(r, ev)
        stake, price = float(r["stake"]), float(r["price_decimal"])
        r["result"] = res
        r["pnl"] = f"{stake * (price - 1) if res == 'win' else -stake if res == 'loss' else 0.0:.2f}"
        graded += 1
    write_ledger(rows)
    print(f"graded {graded}, still open {len(open_rows) - graded}")


if __name__ == "__main__":
    load_config()
    main()
