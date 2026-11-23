# Ticket Arena setup guide

This guide takes you from nothing to a working dashboard at http://localhost:8765. For what each section of the dashboard does, see the [README](README.md).

**Time:** about 10 minutes for the basics, plus 5 minutes for each optional part.

| Part | Required? | What you get |
|---|---|---|
| [1. Prerequisites](#1-prerequisites) | Yes | |
| [2. Get the code](#2-get-the-code) | Yes | |
| [3. Make your config](#3-make-your-config) | Yes | |
| [4. Start it](#4-start-it) | Yes | Tickets, stuck alerts, PR comments, Combo moves |
| [5. Google Chat follow-ups](#5-optional-google-chat-follow-ups) | Optional | Automatic "please review" posts |
| [6. Team list](#6-optional-team-list-and-real-mentions) | Optional | Team PRs section, real @mentions in follow-ups |
| [7. Worktrees and context meter](#7-optional-worktrees-and-the-context-meter) | Optional | Worktree buttons, Claude context meter |
| [8. Claude review drafts](#8-optional-claude-review-drafts) | Optional, uses tokens | Claude-written review comments |

---

## 1. Prerequisites

| Tool | Check | Notes |
|---|---|---|
| Linux, WSL2 or macOS | | On Windows, run everything inside WSL2 |
| Docker with Compose | `docker compose version` | Docker Desktop, or Docker Engine in WSL |
| GitHub CLI | `gh auth status` | If it says you aren't logged in, run `gh auth login`. Your account needs access to the repo you track |
| git | `git --version` | |
| Python 3.9+ | `python3 --version` | Runs the host agent on your PC |

---

## 2. Get the code

```bash
git clone <this-repo-url> ~/ticket-arena
```

```bash
cd ~/ticket-arena
```

---

## 3. Make your config

```bash
cp config.example.json config.json
```

Open `config.json`. Your team lead can share a ready-made `config.json` privately (never through this repo), or fill in the first few keys yourself.

**Basics**

| Key | What it is | Example |
|---|---|---|
| `repo` | GitHub repo to track, as `owner/name` | `your-org/your-repo` |
| `ticketPrefix` | Ticket key at the start of PR titles. Only PRs titled `EDGE-123: ...` are tracked | `EDGE` |
| `promoBranches` | Branches that count as "promoting to staging" | `["staging", "stage", "demo"]` |
| `stuckDays` | Days in review or promotion before a ticket is stuck | `{"review": 2, "promoting": 2}` |
| `refreshMinutes` | How often it pulls from GitHub | `15` |

**Follow-ups** (only used if you do step 5)

| Key | What it is |
|---|---|
| `chatSpaceName` | Name of your Chat space. Only a label on the dashboard |
| `alwaysCc` | GitHub usernames tagged in every follow-up. The PR's reviewers are added automatically |
| `firstMessage` / `bumpMessage` | Text of the first post and of later reminders |

**Worktrees and context meter** (step 7)

| Key | What it is |
|---|---|
| `worktreeMain` | Your main checkout of the repo |
| `worktreeNewCommand` / `worktreeRemoveCommand` | Commands that create and remove a worktree |
| `contextWindow` | Your Claude model's context window, in tokens |
| `contextWarnTokens` / `contextStopTokens` | Where the meter switches to "Wrap up" and "Start a new chat" |
| `sessionDays` | How many days of Claude chats to show |

**Claude features that cost tokens** (leave them `false` unless you want them)

| Key | What it is |
|---|---|
| `autoDraft` | Queue a Claude review draft for every PR that requests your review |
| `notifyClaude` | Log each refresh for a Claude session that re-uploads the data to claude.ai |

You don't enter your GitHub username anywhere: it comes from your `gh` login.

---

## 4. Start it

```bash
./ta.sh up
```

This one command:
1. builds and starts the Docker container, which runs the dashboard, the GitHub refresh and follow-ups
2. starts the host agent on your PC, which handles worktrees and the context meter. On Linux and WSL it's installed as a background service, so it restarts if it crashes and starts again when you log in

> [!NOTE]
> **SCREENSHOT TODO** `docs/images/11-ta-up-terminal.png`
> Capture: a terminal after running `./ta.sh up` and then `./ta.sh status`, with "dashboard: http://localhost:8765" and both parts running.

![./ta.sh up output](docs/images/11-ta-up-terminal.png)

Open **http://localhost:8765**. The first GitHub refresh takes about a minute. If the page is empty, wait a moment and press **Refresh now**.

**Check that it worked**
- [ ] The header shows your repo and your GitHub username
- [ ] Ticket progress lists your recent `EDGE-...` PRs
- [ ] The Worktrees section says **Host agent live**

### Everyday commands

| Command | What it does |
|---|---|
| `./ta.sh up` | Start everything. Run it again after a `git pull` that changes the Dockerfile |
| `./ta.sh down` | Stop everything |
| `./ta.sh restart` | Restart both parts, after editing `config.json` or pulling code |
| `./ta.sh status` | Is each part running? |
| `./ta.sh logs` | Follow the host agent's log |

**Updating to a new version**

```bash
git pull && ./ta.sh up
```

---

## 5. Optional: Google Chat follow-ups

Follow-ups post a reminder like this to your Chat space for each of your open PRs, on a timer, until the PR merges:

```
Good day team please review this pr thank you!
https://github.com/your-org/your-repo/pull/12345
cc: @Reviewer One @Reviewer Two
```

**1. Create a webhook for your space.** In Google Chat, open the space, click its name, then **Apps & integrations**, then **Webhooks**, then **Add webhook**. Give it a name (posts appear under this name) and copy the URL.

> [!NOTE]
> **SCREENSHOT TODO** `docs/images/12-gchat-webhook.png`
> Capture: the Google Chat "Webhooks" dialog after adding one. **Blur the webhook URL**: anyone who has it can post to the space.

![Google Chat webhook dialog](docs/images/12-gchat-webhook.png)

**2. Save the URL** in a file called `gchat-webhook`. It's git-ignored and only you can read it:

```bash
echo 'https://chat.googleapis.com/v1/spaces/...' > gchat-webhook && chmod 600 gchat-webhook
```

**3. Try it without posting.** Replace `12345` with one of your open PRs:

```bash
python3 followup.py 12345 --dry
```

**4. Turn follow-ups on** with the **Start follow-ups** button in Round 2. They start **off**.

> [!NOTE]
> **SCREENSHOT TODO** `docs/images/13-follow-up-in-chat.png`
> Capture: a follow-up message as it appears in the Google Chat space, with the PR link and the cc mentions.

![A follow-up in Google Chat](docs/images/13-follow-up-in-chat.png)

**From the terminal**

| Command | What it does |
|---|---|
| `python3 followup.py status` | On or off, interval, skipped PRs |
| `python3 followup.py start` / `stop` | Turn follow-ups on or off |
| `python3 followup.py every 60` | Post every 60 minutes (minimum 15) |
| `python3 followup.py skip 12345` / `unskip 12345` | Exclude a PR, or include it again |
| `python3 followup.py 12345` | Post one follow-up now |

---

## 6. Optional: team list and real mentions

The **Team PRs** section and the follow-up cc list use `chat-people.json`:

```bash
cp chat-people.example.json chat-people.json
```

```json
{
  "github-username": { "name": "Name as shown in Google Chat", "id": "123456789012345678901" }
}
```

- People in this file appear in **Team PRs**.
- With an `id`, follow-ups really ping them in Chat. Without one, they get a plain-text `@Name`.

**The quick way:** ask a teammate who already has the file for their copy.

**Collect the IDs yourself:**
1. Open the Chat space at chat.google.com, open its member list, and scroll to the bottom so everyone has loaded.
2. Open DevTools (F12), go to **Console**, paste the contents of `chat-scrape.js`, and press Enter. It copies `{"Name": "id"}` for everyone to your clipboard.
3. Paste that into a new file called `chat-ids.json`, then run:

```bash
python3 import_chat_ids.py
```

It matches Chat names to the GitHub usernames of people who reviewed your PRs, then lists anyone it couldn't match so you can add them by hand.

> [!NOTE]
> **SCREENSHOT TODO** `docs/images/14-chat-scrape-console.png`
> Capture: the DevTools console after running `chat-scrape.js`, showing "Copied N people to the clipboard". **Blur the names and IDs.**

![Running chat-scrape.js](docs/images/14-chat-scrape-console.png)

---

## 7. Optional: worktrees and the context meter

The host agent is already running after `./ta.sh up`. Point it at your checkout in `config.json`:

| Key | Default | Notes |
|---|---|---|
| `worktreeMain` | `~/projects/your-repo` | Path to your main clone |
| `worktreeNewCommand` | `git worktree add ../worktree-{num} -b {prefix}/{num} origin/main` | Runs inside `worktreeMain` |
| `worktreeRemoveCommand` | `git worktree remove ../worktree-{num}` | |

You can use these placeholders in both commands:

| Placeholder | Becomes |
|---|---|
| `{ticket}` | What you typed, e.g. `PROJ-1234` or `1234` |
| `{num}` | The digits only, e.g. `1234` |
| `{prefix}` | Your `ticketPrefix` |
| `{main}` | The full path of `worktreeMain` |

If you have your own worktree script that also installs and builds, use that instead. For example:

```json
"worktreeNewCommand": "~/.local/bin/my-wt new {ticket}",
"worktreeRemoveCommand": "~/.local/bin/my-wt rm {ticket}"
```

Run `./ta.sh restart` after changing these.

**How the context meter works**
- Claude Code saves every chat on your PC in `~/.claude/projects`. The host agent reads each chat's latest token count from there. Nothing is sent anywhere, and it costs no tokens.
- A chat is shown under the worktree folder it ran in. Otherwise it goes under the worktree whose ticket or PR number appears in the chat's title, and failing that under "Main checkout".
- Pick limits that suit your model. With a 1M window, these defaults work well: wrap up at 200K, new chat at 350K. The dashboard also shows where your own chats have auto-compacted, which helps you tune them.

---

## 8. Optional: Claude review drafts

This one **costs Claude tokens**.

1. Press **Draft review** on a teammate's PR in Team PRs. That adds a `DRAFT <pr>` line to `requests.log`.
2. To have Claude write the draft, open Claude Code in this folder and ask it to watch `requests.log` for `DRAFT` lines and follow `DRAFTING.md`.
3. The draft appears under **Review drafts**. Untick anything you don't want, then press **Post**. Nothing goes to GitHub before you press Post.

Without a Claude Code session watching `requests.log`, the button does nothing and costs nothing. Setting `autoDraft` to `true` also queues a draft for every PR that requests your review.

---

## Token use

Ticket Arena itself never calls Claude. Refresh, follow-ups, worktrees and the context meter only use `gh`, `git`, the Chat webhook and local files. Tokens are spent only by step 8 and by the `autoDraft` and `notifyClaude` settings, all of which are off by default.

## Privacy and security

- The dashboard listens only on `127.0.0.1`, so nobody else on your network can open it.
- Every button needs the secret in `control-token`, which is created on first start. Other web pages can't press your buttons.
- These files are git-ignored and stay on your PC: `config.json`, `gchat-webhook`, `control-token`, `chat-people.json`, `chat-ids.json`, `followups.json`, `threads.json`, `data/`, `*.log`. Never commit them.

## Uninstall

```bash
./ta.sh down && docker rmi ticket-arena
```

```bash
rm -f ~/.config/systemd/user/ticket-arena-host.service && systemctl --user daemon-reload
```

Then delete the folder.

## Troubleshooting

| Problem | Fix |
|---|---|
| Page empty, or the log says "gh is not logged in" | Run `gh auth status`, log in if needed, then `./ta.sh up`. Your GitHub token is passed in at start, so run `up` again after logging in |
| No tickets | PR titles must start with `<ticketPrefix>-<number>:`, e.g. `EDGE-123: Fix login`. Check `repo` and `ticketPrefix` |
| "Host agent not running" in Worktrees | Run `./ta.sh status`, then `./ta.sh logs` to see why. Common cause: `worktreeMain` isn't a git checkout |
| Create worktree shows "failed" | The last output lines are on the job card, and `./ta.sh logs` has the rest. Check that your command works when you run it in a terminal from `worktreeMain` |
| A chat is under the wrong worktree | Put the ticket number in the chat's title (`/rename PROJ-1234 ...`), or run Claude from inside the worktree folder |
| Port 8765 already in use | Change the left side of `ports` in `docker-compose.yml`, e.g. `127.0.0.1:9000:8765` |
| Files in `data/` owned by root | Run `sudo chown -R $(id -u):$(id -g) data`, then `./ta.sh up` |
| macOS: host agent stops after reboot | macOS has no systemd, so run `./ta.sh up` again after you log in |
