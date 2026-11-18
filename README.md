# Ticket Arena

A dashboard for your GitHub PRs that runs on your own PC. It reads from GitHub with your own `gh` login, so every teammate sees their own tickets.

## What it shows

- **Ticket progress**: each ticket from your PR titles (e.g. `EDGE-123: ...`) and its furthest stage: in review, merged to main, promoting, or on staging. It also shows how long the ticket has been in that stage.
- **Stuck tickets**: PRs that have been in review or promotion longer than your limit.
- **PR comments**: review comments on your open PRs, with the ones still waiting on your reply flagged.
- **Follow-ups**: optional "please review" posts to Google Chat on a timer. They tag your reviewers and stop once the PR merges.
- **Team PRs**: teammates' open PRs, with replies and review requests waiting on you. Optionally, Claude can draft a review, which is posted only when you press Post.
- **Combo moves**: ready-to-copy Claude Code and `gh` commands for a ticket or PR.

## Quick start

```bash
cp config.example.json config.json   # set your repo, branches, cc list
GH_TOKEN=$(gh auth token) TA_UID=$(id -u) TA_GID=$(id -g) docker compose up -d --build
```

Then open http://localhost:8765.

**Full instructions are in [SETUP.md](SETUP.md)**, including Google Chat follow-ups, the team list, commands and troubleshooting.

## How it works

| File | Role |
|---|---|
| `refresh.py` | Pulls your PRs, comments and team PRs with `gh`, then writes `data/*.json` |
| `control.py` | Local server on `127.0.0.1:8765`. It serves the dashboard, runs the refresh on a timer, and handles button clicks (protected by a secret token) |
| `followup.py` | Posts follow-ups to a Google Chat webhook. Also a CLI: `start`, `stop`, `status`, `skip` |
| `index.html` + `ta-local.js` | The dashboard page |
| `config.py` | Loads `config.json`. Your GitHub login comes from `gh`, never from config |

Personal settings and secrets (`config.json`, `gchat-webhook`, `control-token`, `chat-people.json`, `data/`) are git-ignored. Each person keeps their own.
