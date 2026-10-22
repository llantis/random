"""Mirror ledger picks onto Kalshi (demo by default) and settle them.

Usage:
  python3 scripts/kalshi.py check            # auth + balance
  python3 scripts/kalshi.py place [--date D] # place today's unplaced picks (dry run unless kalshi.dry_run is false)
  python3 scripts/kalshi.py settle           # update fills and settle finished markets

Only ledger rows (already validated by record_picks.py) are ever placed. Caps are enforced here:
stake per bet, daily and all-time spend, price sanity vs the slate price, one order per ledger row.
Secrets: KALSHI_API_KEY_ID, KALSHI_PRIVATE_KEY_B64 (base64 of the PEM file).
"""
import argparse
import base64
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from common import DATA, load_config, now_utc, parse_time, read_ledger, today

HOSTS = {"demo": "https://demo-api.kalshi.co", "prod": "https://api.elections.kalshi.com"}
API = "/trade-api/v2"
ORDERS = DATA / "kalshi_orders.csv"
ORDER_FIELDS = [
    "date", "player", "option_id", "pick", "ticker", "side", "price", "count", "cost",
    "order_id", "status", "filled", "result", "pnl", "note", "placed_at",
]
SPORT_CODES = {
    "basketball_nba": "NBA", "americanfootball_nfl": "NFL", "americanfootball_ncaaf": "NCAAF",
    "icehockey_nhl": "NHL", "baseball_mlb": "MLB", "soccer_epl": "EPL", "soccer_uefa_champs_league": "UCL",
}
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def load_key(value):
    """Accept a base64'd PEM file, raw PEM text, or the bare base64 body of the PEM (DER)."""
    from cryptography.hazmat.primitives import serialization
    value = value.strip()
    if "BEGIN" in value:
        return serialization.load_pem_private_key(value.encode(), password=None)
    raw = base64.b64decode(value + "=" * (-len(value) % 4))
    if b"BEGIN" in raw:
        return serialization.load_pem_private_key(raw, password=None)
    return serialization.load_der_private_key(raw, password=None)


class Kalshi:
    def __init__(self, env):
        self.base = HOSTS[env]
        self.key_id = os.environ.get("KALSHI_API_KEY_ID")
        pem = os.environ.get("KALSHI_PRIVATE_KEY_B64")
        self.key = None
        if self.key_id and pem:
            self.key = load_key(pem)

    def _sign(self, msg):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ed25519, padding
        if isinstance(self.key, ed25519.Ed25519PrivateKey):
            return self.key.sign(msg)
        return self.key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                                              salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())

    def req(self, method, path, body=None, auth=True, **params):
        full = API + path
        url = self.base + full + ("?" + urllib.parse.urlencode(params) if params else "")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            if not self.key:
                raise SystemExit("KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_B64 not set.")
            ts = str(int(time.time() * 1000))
            sig = self._sign((ts + method + full).encode())
            headers.update({"KALSHI-ACCESS-KEY": self.key_id, "KALSHI-ACCESS-TIMESTAMP": ts,
                            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode()})
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"{method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}")

    def markets(self, series):
        out, cursor = [], None
        while True:
            params = {"series_ticker": series, "status": "open", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            d = self.req("GET", "/markets", auth=False, **params)
            out += d.get("markets", [])
            cursor = d.get("cursor")
            if not cursor:
                return out



def norm(s):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def dollars(m, key):
    v = m.get(f"{key}_dollars")
    if v is not None:
        return float(v)
    v = m.get(key)
    return v / 100 if v is not None else None


def event_date(code):
    m = re.match(r"(\d{2})([A-Z]{3})(\d{2})", code)
    return f"20{m.group(1)}-{MONTHS[m.group(2)]:02d}-{m.group(3)}" if m else None


class Matcher:
    """Finds the Kalshi market + side equivalent to a ledger pick."""

    def __init__(self, client):
        self.client, self.cache = client, {}

    def series(self, name):
        if name not in self.cache:
            try:
                self.cache[name] = self.client.markets(name)
            except Exception as e:
                print(f"  could not load {name}: {e}")
                self.cache[name] = []
        return self.cache[name]

    def find_event(self, code, game):
        """Return (event_code, {home: team_code, away: team_code, draw: 'TIE'}) or None."""
        events = {}
        for m in self.series(f"KX{code}GAME"):
            events.setdefault(m["event_ticker"].split("-", 1)[1], []).append(m)
        start_day = parse_time(game["commence_time"]).astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
        home, away = norm(game["home"]), norm(game["away"])
        hits = []
        for ev, ms in events.items():
            if event_date(ev) != start_day:
                continue
            teams = {}
            for m in ms:
                tcode, sub = m["ticker"].rsplit("-", 1)[1], norm(m.get("yes_sub_title", ""))
                if tcode == "TIE":
                    teams["draw"] = "TIE"
                elif sub and sub in home and sub not in away:
                    teams["home"] = tcode
                elif sub and sub in away and sub not in home:
                    teams["away"] = tcode
            if "home" in teams and "away" in teams:
                hits.append((ev, teams))
        return hits[0] if len(hits) == 1 else None

    def match(self, row, game):
        code = SPORT_CODES.get(row["sport"])
        if not code:
            return None, "sport not on Kalshi"
        found = self.find_event(code, game)
        if not found:
            return None, "no unique Kalshi event"
        ev, teams = found
        _, market, side = row["option_id"].split("-")
        side = side.lower()
        if market == "ML":
            if side not in teams:
                return None, "no market for that side"
            return (f"KX{code}GAME-{ev}-{teams[side]}", "yes"), None
        point = float(row["pick"].rsplit(" ", 1)[1])
        if market == "TOTAL":
            for m in self.series(f"KX{code}TOTAL"):
                if m["event_ticker"].endswith(ev) and m.get("floor_strike") == point:
                    return (m["ticker"], "yes" if side == "over" else "no"), None
            return None, f"no Kalshi total at {point}"
        # Spread: favorite -X => YES "fav wins by over X"; underdog +X => NO on the favorite's market.
        fav = side if point < 0 else ("away" if side == "home" else "home")
        want = "yes" if point < 0 else "no"
        pat = re.compile(rf"-{re.escape(teams[fav])}\d+$")
        for m in self.series(f"KX{code}SPREAD"):
            if m["event_ticker"].endswith(ev) and pat.search(m["ticker"]) and m.get("floor_strike") == abs(point):
                return (m["ticker"], want), None
        return None, f"no Kalshi spread at {abs(point)}"


def read_orders():
    if not ORDERS.exists():
        return []
    with ORDERS.open(newline="") as f:
        return list(csv.DictReader(f))


def write_orders(rows):
    with ORDERS.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_FIELDS)
        w.writeheader()
        w.writerows(rows)


def place(cfg, client, date):
    kc = cfg["kalshi"]
    slate = json.loads((DATA / "slates" / f"{date}.json").read_text())
    games = {g["event_id"]: g for g in slate["games"]}
    orders = read_orders()
    done = {(o["date"], o["player"], o["option_id"]) for o in orders}
    real = [o for o in orders if o["order_id"] and not o["order_id"].startswith("dry")]
    spent_total = sum(float(o["cost"] or 0) for o in real)
    spent_today = sum(float(o["cost"] or 0) for o in real if o["date"] == date)
    matcher, now = Matcher(client), now_utc()

    for r in read_ledger():
        if r["date"] != date or (r["date"], r["player"], r["option_id"]) in done:
            continue
        rec = {k: "" for k in ORDER_FIELDS}
        rec.update(date=date, player=r["player"], option_id=r["option_id"], pick=r["pick"],
                   placed_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
        game = games.get(r["game_id"])
        found, why = matcher.match(r, game) if game else (None, "game not in slate")
        if parse_time(r["commence_time"]) <= now:
            found, why = None, "game started"
        if found:
            ticker, side = found
            m = client.req("GET", f"/markets/{ticker}", auth=False)["market"]
            ask = dollars(m, f"{side}_ask")
            implied = 1 / float(r["price_decimal"])
            stake = float(cfg["stake"])
            count = int(stake // ask) if ask else 0
            cost = round(count * ask, 2) if count else 0
            rec.update(ticker=ticker, side=side, price=ask)
            if not ask or not (0.02 <= ask <= 0.98):
                why = f"no usable ask ({ask})"
            elif ask > implied + kc["max_slippage"]:
                why = f"ask {ask:.2f} worse than slate {implied:.2f}+{kc['max_slippage']}"
            elif count < 1:
                why = "stake below one contract"
            elif spent_today + cost > kc["daily_cap"] or spent_total + cost > kc["total_cap"]:
                why = "cap reached"
            else:
                rec.update(count=count, cost=cost)
                if kc["dry_run"]:
                    rec.update(order_id=f"dry-{uuid.uuid4().hex[:8]}", status="dry_run")
                else:
                    price_key = f"{side}_price"
                    body = {"ticker": ticker, "action": "buy", "side": side, "count": count, "type": "limit",
                            price_key: round(ask * 100), "client_order_id": str(uuid.uuid4()),
                            "expiration_ts": int(parse_time(r["commence_time"]).timestamp())}
                    try:
                        o = client.req("POST", "/portfolio/orders", body)["order"]
                        rec.update(order_id=o["order_id"], status=o.get("status", ""))
                        spent_today += cost
                        spent_total += cost
                    except Exception as e:
                        why = f"order failed: {e}"
                        rec.update(count="", cost="")
        if why:
            rec["note"] = why
        orders.append(rec)
        print(f"{r['player']:>14} {r['pick']:<32} -> {rec['ticker'] or '-'} {rec['side']} "
              f"{rec['status'] or 'skipped'} {rec['note']}")
    write_orders(orders)


def settle(cfg, client):
    orders = read_orders()
    for o in orders:
        if o["result"] or not o["ticker"] or not o["count"]:
            continue
        if not o["order_id"].startswith("dry") and o["status"] not in ("executed", "canceled"):
            od = client.req("GET", f"/portfolio/orders/{o['order_id']}")["order"]
            o["status"] = od.get("status", o["status"])
            filled = od.get("fill_count", od.get("filled_count"))
            if filled is None and od.get("remaining_count") is not None:
                filled = int(o["count"]) - int(od["remaining_count"])
            o["filled"] = filled if filled is not None else o["filled"]
        elif o["order_id"].startswith("dry"):
            o["filled"] = o["count"]
        m = client.req("GET", f"/markets/{o['ticker']}", auth=False)["market"]
        if m.get("result") in ("yes", "no"):
            n, p = int(o["filled"] or 0), float(o["price"])
            won = m["result"] == o["side"]
            o["result"] = "win" if won else "loss"
            o["pnl"] = f"{n * (1 - p) if won else -n * p:.2f}"
    write_orders(orders)
    print(f"settled; {sum(1 for o in orders if o['result'])} of {len(orders)} rows have results")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "place", "settle"])
    ap.add_argument("--date", default=today())
    args = ap.parse_args()
    cfg = load_config()
    kc = cfg.get("kalshi", {})
    if not kc.get("enabled"):
        raise SystemExit("kalshi.enabled is false in config.json")
    client = Kalshi(kc["env"])
    if args.cmd == "check":
        bal = client.req("GET", "/portfolio/balance")
        print(f"env={kc['env']} dry_run={kc['dry_run']} balance=${bal.get('balance', 0) / 100:.2f}")
    elif args.cmd == "place":
        place(cfg, client, args.date)
    else:
        settle(cfg, client)


if __name__ == "__main__":
    main()
