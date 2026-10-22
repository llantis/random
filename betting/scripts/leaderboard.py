"""Write data/leaderboard.md: P/L, ROI, record and calibration (Brier score) per player."""
from collections import defaultdict

from common import DATA, load_config, read_ledger
from kalshi import read_orders


def main():
    cfg = load_config()
    stats = defaultdict(lambda: {"bets": 0, "w": 0, "l": 0, "p": 0, "open": 0, "staked": 0.0, "pnl": 0.0, "brier": []})
    for r in read_ledger():
        s = stats[r["player"]]
        if not r["result"]:
            s["open"] += 1
            continue
        s["bets"] += 1
        s[r["result"][0]] += 1
        s["staked"] += float(r["stake"])
        s["pnl"] += float(r["pnl"])
        if r["result"] != "push":
            s["brier"].append((float(r["confidence"]) - (r["result"] == "win")) ** 2)

    kalshi = defaultdict(lambda: {"orders": 0, "pnl": 0.0})
    for o in read_orders():
        if o["count"]:
            kalshi[o["player"]]["orders"] += 1
            kalshi[o["player"]]["pnl"] += float(o["pnl"] or 0)

    meta = {p["name"]: p for p in cfg["players"]}
    order = sorted(set(meta) | set(stats), key=lambda n: -stats[n]["pnl"])
    lines = [
        f"# Leaderboard ({cfg['mode']} mode)",
        "",
        "| # | Player | Model | Effort | Record (W-L-P) | Open | P/L | ROI | Brier | Kalshi orders | Kalshi P/L |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for i, name in enumerate(order, 1):
        s, m = stats[name], meta.get(name, {})
        roi = f"{s['pnl'] / s['staked']:+.1%}" if s["staked"] else "-"
        brier = f"{sum(s['brier']) / len(s['brier']):.3f}" if s["brier"] else "-"
        lines.append(
            f"| {i} | {name} | {m.get('model', '?')} | {m.get('effort', '?')} | "
            f"{s['w']}-{s['l']}-{s['p']} | {s['open']} | ${s['pnl']:+.2f} | {roi} | {brier} | "
            f"{kalshi[name]['orders']} | ${kalshi[name]['pnl']:+.2f} |"
        )
    kc = cfg.get("kalshi", {})
    lines += [
        "",
        "Brier = mean squared error of stated confidence vs outcome (lower is better; 0.25 = coin flip).",
        f"Kalshi columns: orders mirrored to Kalshi {kc.get('env', '-')}"
        f"{' (dry run)' if kc.get('dry_run') else ''}; fees not included.",
    ]
    (DATA / "leaderboard.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
