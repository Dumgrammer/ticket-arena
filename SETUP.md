# Ticket Arena setup

Ticket Arena is a local dashboard for your GitHub PRs. It shows your tickets by stage, flags stuck ones, lists review comments still waiting on you, shows teammates' open PRs, and can post "please review" follow-ups to Google Chat on a timer.

It runs on your own PC in Docker at http://localhost:8765 and acts as you, using your own `gh` login.

## You need

- Docker with Docker Compose
- GitHub CLI (`gh`), logged in with access to the repo: `gh auth login`

## 1. Get the code

```bash
git clone <this-repo-url> ticket-arena
```

```bash
cd ticket-arena
```

## 2. Make your config

```bash
cp config.example.json config.json
```

Edit `config.json`:

| Key | What it is |
|---|---|
| `repo` | GitHub repo to track, `owner/name` |
| `ticketPrefix` | Ticket key in PR titles. `EDGE` matches titles like `EDGE-123: Fix login` |
| `promoBranches` | Branches that count as "promoting to staging" |
| `stuckDays` | Days in `review` / `promoting` before a ticket counts as stuck |
| `refreshMinutes` | How often the container pulls from GitHub |
| `chatSpaceName` | Name of your Google Chat space. Only used as a label on the dashboard |
| `alwaysCc` | GitHub logins tagged in every follow-up. The PR's reviewers are added automatically |
| `firstMessage` / `bumpMessage` | Text of the first follow-up and of later bumps |

You don't set your GitHub username anywhere: it comes from `gh`.

## 3. Optional: team list and Google Chat

**Team PRs and @mentions.** Copy the example file, then add your teammates:

```bash
cp chat-people.example.json chat-people.json
```

Each key is a GitHub login with `{"name": "...", "id": "..."}`. The **Team PRs** section lists open PRs from everyone in this file. If you fill in a person's Google Chat `id`, follow-ups really ping them. Without an id they get a plain `@Name`. You can ask a teammate for their copy, or get the IDs yourself:

1. Open your Chat space in the browser and scroll through the member list.
2. Paste `chat-scrape.js` into the DevTools console. It copies the IDs to your clipboard.
3. Paste them into `chat-ids.json`, then run `python3 import_chat_ids.py`.

**Follow-ups to Google Chat.** In the Chat space, open Apps & integrations, then Webhooks, and add a webhook. Save its URL in a file called `gchat-webhook`:

```bash
echo 'https://chat.googleapis.com/v1/spaces/...' > gchat-webhook && chmod 600 gchat-webhook
```

Follow-ups start **off**. Turn them on from the dashboard, or run `python3 followup.py start`.

## 4. Start it

```bash
GH_TOKEN=$(gh auth token) TA_UID=$(id -u) TA_GID=$(id -g) docker compose up -d --build
```

Open http://localhost:8765. The first refresh takes a minute or so. After that it refreshes every `refreshMinutes`. The **Refresh now** button refreshes right away.

To stop it:

```bash
docker compose down
```

After you edit `config.json` or any code, restart it:

```bash
docker compose restart
```

## Commands (outside the dashboard)

```bash
python3 followup.py status
```

The other commands work the same way: `start`, `stop`, `every <minutes>`, `skip <pr>`, `unskip <pr>`, and `<pr> --dry`, which shows a follow-up without posting it.

## Optional: Claude review drafts

**Draft review** on a teammate's PR adds a `DRAFT <pr>` line to `requests.log`. To have Claude write the draft, open Claude Code in this folder and ask it to watch `requests.log` for `DRAFT` lines and follow `DRAFTING.md`. Nothing goes to GitHub until you press **Post** on the dashboard. The **Combo moves** commands assume your Claude Code has the `start-ticket` and `resolve-pr-ticket` skills.

## Privacy

These files are yours alone and are git-ignored: `config.json`, `gchat-webhook`, `control-token`, `chat-people.json`, `chat-ids.json`, `followups.json`, `threads.json`, `data/`, `*.log`. Don't commit them.

The server listens only on `127.0.0.1`. Every button needs the `control-token` secret, which is created the first time the server starts.

## Troubleshooting

- **Empty dashboard or "gh is not logged in"**: `GH_TOKEN` was empty. Run `gh auth status`, then start it again with the command in step 4.
- **Port 8765 already in use**: change the left side of `ports` in `docker-compose.yml`, for example `127.0.0.1:9000:8765`.
- **Files in `data/` owned by root**: you started it without `TA_UID` / `TA_GID`. Run `sudo chown -R $(id -u):$(id -g) data`, then start it again with the full command.
- **No tickets**: PR titles must start with `<ticketPrefix>-<number>:`.
