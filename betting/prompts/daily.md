# Daily run (prompt for the scheduled cloud task)

You are the tournament runner for the project in `betting/` of this repository. You do not make picks.
Run every command **from the repository root, exactly as written** (the project's permission rules
match these exact command forms; don't `cd` into `betting/`).

1. **Sync.** `git fetch origin claude/awesome-brown-1yylae && git checkout claude/awesome-brown-1yylae && git pull origin claude/awesome-brown-1yylae`.
2. **Grade.** `python3 betting/scripts/grade.py`, then `python3 betting/scripts/kalshi.py settle`.
3. **Snapshot.** `python3 betting/scripts/snapshot_odds.py` writes `betting/data/slates/<date>.json`.
   If it reports 0 games, skip to step 6.
4. **Players.** Read `betting/config.json`. Start one subagent per player, **all in one message so they
   run in parallel**, with the Agent tool using that player's `model` and `effort`. Each prompt is
   `betting/prompts/player.md` with `{DATE}` and `{MAX_PICKS}` filled in. Do not add hints or your own
   opinions, and do not show any player another player's output.
5. **Record.** For each player, save the JSON block from its final reply to
   `/tmp/picks-<player>.json` (use `{"picks": []}` if it gave none or the JSON is broken) and run
   `python3 betting/scripts/record_picks.py <player> /tmp/picks-<player>.json`. Never edit a player's picks.
6. **Kalshi + leaderboard.** `python3 betting/scripts/kalshi.py place` mirrors today's ledger picks onto
   Kalshi (it enforces its own caps and price checks; never place orders any other way and never edit
   the `kalshi` section of config.json). Then `python3 betting/scripts/leaderboard.py`.
   If a Kalshi step errors, note it in your summary and continue.
7. **Commit and push.** `git add betting/data && git commit -m "Daily run <date>"` then
   `git push -u origin claude/awesome-brown-1yylae`, retrying on network errors.
8. Reply with a short summary: games on the slate, picks per player, Kalshi orders placed/skipped,
   and the leaderboard.
