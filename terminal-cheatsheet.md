# Terminal Cheat Sheet

Commands I keep forgetting. Search this file with `Cmd+F` (or `grep -i ssh terminal-cheatsheet.md`).

---

## SSH

| Command | What it does |
|---|---|
| `ssh -t gallup@paperclip bash --norc --noprofile` | **Clean shell on paperclip** — skips `.bashrc` / `.profile`, so a broken or noisy startup file can't get in the way |
| `ssh gallup@paperclip` | Normal login |
| `ssh -v gallup@paperclip` | Verbose — see why a connection hangs or fails (`-vvv` for more) |
| `ssh gallup@paperclip 'uptime'` | Run one command remotely and come back |
| `ssh -L 4000:localhost:4000 gallup@paperclip` | Port-forward: open `localhost:4000` on your Mac to reach port 4000 on paperclip |
| `scp file.txt gallup@paperclip:~/` | Copy a file **to** the server |
| `scp gallup@paperclip:~/file.txt .` | Copy a file **from** the server |
| `rsync -avz ./dir/ gallup@paperclip:~/dir/` | Sync a folder (only sends changes) |
| `ssh-copy-id gallup@paperclip` | Install your key so you stop typing the password |
| `ssh-keygen -R paperclip` | Remove a stale host key ("REMOTE HOST IDENTIFICATION HAS CHANGED") |

Why the clean-shell flags matter:
- `-t` forces a real terminal, so the remote `bash` is interactive (prompt, arrow keys, Ctrl+C).
- `--norc` skips `~/.bashrc`; `--noprofile` skips `~/.bash_profile` / `~/.profile` / `/etc/profile`.

### Make it a one-word command

Add to `~/.zshrc` on the Mac, then `source ~/.zshrc`:

```bash
alias pclean='ssh -t gallup@paperclip bash --norc --noprofile'
alias pc='ssh gallup@paperclip'
```

Or put the host in `~/.ssh/config` so every tool (ssh, scp, rsync) knows it:

```
Host paperclip
    User gallup
    # HostName 192.168.x.x   # if "paperclip" doesn't resolve on its own
```

Then `ssh paperclip` and `scp file.txt paperclip:~/` just work.

---

## Remembering commands

| Command | What it does |
|---|---|
| `Ctrl+R` then type | Search your shell history (press `Ctrl+R` again for older matches) |
| `history \| grep ssh` | Every `ssh` command you've run |
| `!!` | Re-run the last command (`sudo !!` = last command with sudo) |
| `alias` | List your aliases |
| `type pclean` | Show what a command/alias actually runs |
| `man ssh` / `tldr ssh` | Full manual / short examples (`brew install tldr`) |

---

## Navigating & files

| Command | What it does |
|---|---|
| `cd -` | Jump back to the previous directory |
| `ls -lah` | List everything, with sizes in KB/MB |
| `pwd` | Where am I? |
| `open .` | Open the current folder in Finder (Mac) |
| `code .` | Open the current folder in VS Code |
| `find . -name "*.env*"` | Find files by name |
| `grep -rn "text" .` | Search inside files (line numbers) |
| `du -sh * \| sort -h` | What's taking up space here |
| `df -h` | Free disk space |
| `tail -f app.log` | Follow a log as it's written |
| `less file` | Page through a file (`/` to search, `q` to quit) |

---

## Processes & ports

| Command | What it does |
|---|---|
| `lsof -i :4000` | What's using port 4000? |
| `kill -9 <PID>` | Force-stop a process |
| `lsof -ti :4000 \| xargs kill -9` | Free port 4000 in one go |
| `ps aux \| grep node` | Find running node processes |
| `top` / `htop` | Live CPU/memory (`q` to quit) |
| `Ctrl+C` / `Ctrl+Z` / `fg` | Stop / pause / resume the foreground job |

---

## Network (Mac)

| Command | What it does |
|---|---|
| `ipconfig getifaddr en0` | This Mac's LAN IP (Wi-Fi) |
| `ping paperclip` | Is it reachable? |
| `curl -I https://www.maresync.com` | Just the HTTP headers / status code |
| `nc -zv paperclip 22` | Is the SSH port open? |

---

## tmux (keep sessions alive on the server)

Run work on paperclip inside tmux so it survives a dropped SSH connection.

| Command | What it does |
|---|---|
| `tmux new -s work` | Start a named session |
| `Ctrl+B` then `D` | Detach (leaves it running) |
| `tmux ls` | List sessions |
| `tmux a -t work` | Reattach |
| `ssh -t gallup@paperclip tmux a -t work` | SSH straight into that session |

---

## Git

| Command | What it does |
|---|---|
| `git status -sb` | Short status + branch |
| `git log --oneline -15` | Recent commits |
| `git switch -c my-branch` | New branch |
| `git switch -` | Back to the previous branch |
| `git diff --staged` | What's about to be committed |
| `git stash` / `git stash pop` | Park changes / bring them back |
| `git restore file` | Throw away changes to one file |
| `git commit --amend` | Fix the last commit (only if not pushed) |
| `git pull --rebase` | Update without a merge commit |

---

## Mare Sync

| Command | What it does |
|---|---|
| `pnpm --filter web dev` | Web + tRPC API on port 4000 — **start this first** |
| `pnpm --filter mobile dev` | Expo (needs web running; auto-fixes the LAN IP) |
| `pnpm mobile:ip` | Re-point the mobile app at this Mac's current IP (then restart Expo) |
| `npx supabase start` / `stop` | Local Supabase in Docker |
| `pnpm db:local:reset` | Rebuild the **local** DB + test data |
| `npx supabase status` | Local URLs and keys |
| `pnpm lint && pnpm test` | Fast checks before a PR |
| `pnpm mare:preflight` | Full QA gate |

---

## Keyboard shortcuts (any terminal)

| Keys | What it does |
|---|---|
| `Ctrl+A` / `Ctrl+E` | Start / end of line |
| `Ctrl+U` / `Ctrl+K` | Delete to start / end of line |
| `Ctrl+W` | Delete previous word |
| `Ctrl+L` | Clear screen |
| `Tab` (twice) | Autocomplete / show options |
| `Ctrl+D` | Exit the shell (logs you out of SSH) |
| `~.` (at start of line) | Kill a frozen SSH session |
