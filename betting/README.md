# Betting: AI model tournament

Several Claude players (different models and effort levels) independently bet a flat $1 per pick on
the same daily odds snapshot. Everything runs as a cloud scheduled task; no local machine needed.
Currently **paper mode**: no real money moves.

## How a day works
1. `scripts/grade.py` settles yesterday's bets from final scores.
2. `scripts/snapshot_odds.py` takes **one** odds snapshot (The Odds API) for games in the next 30h and
   locks it as `data/slates/<date>.json`. Every player sees identical lines.
3. The runner starts one subagent per player in `config.json`, in parallel, with that player's
   model and effort. Players see only the slate and `prompts/player.md`, never each other's picks.
4. `scripts/record_picks.py` is the only way into the ledger and enforces the rules in code: option
   must be in the slate, game not started, one pick per game, daily pick cap, fixed stake, picks
   locked once recorded.
5. `scripts/leaderboard.py` writes `data/leaderboard.md` (P/L, ROI, record, Brier calibration).

The scheduled task's prompt is `prompts/daily.md`.

## Files
| Path | What |
|---|---|
| `config.json` | players, stake, pick cap, sports, markets, preferred bookmakers |
| `data/slates/` | daily odds snapshots |
| `data/picks/<date>/<player>.json` | each player's accepted and rejected picks |
| `data/ledger.csv` | every bet and its result (source of truth) |
| `data/leaderboard.md` | standings |

## Setup
- Environment secret `ODDS_API_KEY` (free key from the-odds-api.com; ~7 sports × 1 call/day + scores fits the free tier).
- Optional: Google Sheets connector granted to the scheduled task to mirror the ledger to
  "Gemini vs Claude - Daily Betting Showdown".

## Running by hand
```
cd betting/scripts
python3 grade.py
python3 snapshot_odds.py
python3 record_picks.py opus-max picks.json
python3 leaderboard.py
```

## Kalshi (demo)
`scripts/kalshi.py` mirrors validated ledger picks onto Kalshi. It is the only code that holds the key.
- `check` (auth + balance), `place` (today's picks), `settle` (fills + results) → `data/kalshi_orders.csv`.
- Mapping: ML → YES on "Team wins"; draw → YES on "Tie"; favorite −X → YES on "Team wins by over X";
  underdog +X → NO on the favorite's "wins by over X"; Over/Under X → YES/NO on "Over X".
- Skips (logged with a reason) when there's no matching market or strike, no usable ask, the ask is more
  than `max_slippage` worse than the slate price, or a cap would be exceeded.
- Config `kalshi`: `env` (`demo`/`prod`), `dry_run`, `max_slippage`, `daily_cap`, `total_cap` (dollars).
- Secrets: `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_B64` (base64 of the private key PEM).
- The paper ledger stays the tournament score; Kalshi shows what actually executes. Real money means
  `env: prod` with production keys, and should only be switched deliberately.

Sportsbooks such as DraftKings or FanDuel are not supported: they have no betting API and ban automation.
