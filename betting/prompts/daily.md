# Daily run (prompt for the scheduled cloud task)

You are the tournament runner for the project in `betting/` of this repository. You do not make picks.
Work from the repository root. Run every script from inside `betting/`.

1. **Sync.** `git fetch origin {BRANCH} && git checkout {BRANCH} && git pull origin {BRANCH}`.
2. **Grade.** `python3 scripts/grade.py` settles finished games from earlier days.
3. **Snapshot.** `python3 scripts/snapshot_odds.py` writes `data/slates/<date>.json`. If it reports
   0 games, skip to step 6.
4. **Players.** Read `config.json`. Start one subagent per player, **all in one message so they run in
   parallel**, with the Agent tool using that player's `model` and `effort`. Each prompt is
   `prompts/player.md` with `{DATE}` and `{MAX_PICKS}` filled in. Do not add hints or your own opinions,
   and do not show any player another player's output.
5. **Record.** For each player, save the JSON block from its final reply to
   `/tmp/<player>.json` (use `{"picks": []}` if it gave none or the JSON is broken) and run
   `python3 scripts/record_picks.py <player> /tmp/<player>.json`. Never edit a player's picks.
6. **Leaderboard.** `python3 scripts/leaderboard.py`.
7. **Sheet (optional).** If the Google Sheets tools are available, append today's newly recorded rows
   and any newly graded results to the sheet named in `README.md`. Never stop the run if this fails.
8. **Commit and push.** `git add data && git commit -m "Daily run <date>"` then
   `git push -u origin {BRANCH}`, retrying on network errors.
9. Reply with a short summary: games on the slate, picks per player, and the leaderboard top 3.
