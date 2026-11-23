# Ticket Arena

A personal dashboard for your tickets, PRs and Claude Code chats. It runs on your own PC and reads GitHub with your own `gh` login, so every developer sees their own work.

<img width="2560" height="1600" alt="Overview" src="https://github.com/user-attachments/assets/cd74e8ec-73e0-4de3-a52e-7a7d4b559a0a" />


**Setting it up?** Go to **[SETUP.md](SETUP.md)**. It takes about 10 minutes.

---

## Why use it

- **See every ticket's stage at a glance**: in review, merged, promoting to staging, or on staging.
- **Never miss a review comment**: comments nobody has answered yet are flagged.
- **Stop chasing reviewers by hand**: it posts "please review" reminders to Google Chat on a timer and stops when the PR merges.
- **Know when a Claude chat is too full**: every Claude Code chat gets a context meter that says keep going, wrap up, or start a new chat.
- **Create and remove worktrees with one click.**
- **Costs no Claude tokens.** It only uses `gh`, `git`, a Chat webhook and local files.

---

## Feature tour

### Navigation

A navbar stays pinned to the top of the window. It has six pages: **Overview**, **Tickets**, **PR comments**, **Team PRs**, **Worktrees** and **Commands**. A badge on each tab counts what needs you there: stuck tickets, comments waiting for your reply, PRs waiting on you, and chats that should start fresh. The navbar also holds the **Refresh now** button. Press keys **1** to **6** to switch pages. Each page has its own link (e.g. `localhost:8765/#/worktrees`), so bookmarks and the back button work.

### Overview: header and summary counters

The header shows your repo and GitHub username and a one-line summary. Below it are six counters: **In review**, **Merged to main**, **Promoting**, **On staging**, **Needs your reply** and **Stuck**. Data refreshes from GitHub every 15 minutes by itself.

### Danger zone: stuck tickets

A ticket is stuck when its PR has been open in review, or open for promotion to staging, longer than the limit (2 days by default). Each alert shows how many days it has been, since when, and whether changes were requested.

<img width="493" height="234" alt="image" src="https://github.com/user-attachments/assets/626c0407-074f-468b-b2d0-68e0f05fcd54" />


### Round 1: Ticket progress

One row per ticket, taken from your PR titles (`EDGE-123: ...`). Each row shows:
- the furthest stage reached, as a progress bar: review, merged, promoting, staging. A teammate's "Promote #PR" PR counts too
- days in that stage against the limit
- the latest PR, lines changed and the last update

Use **Show** to filter and **Sort** to reorder. Click a row to load that ticket into Combo moves.

<img width="2560" height="1600" alt="Tickets" src="https://github.com/user-attachments/assets/971857b4-bb2e-4fa5-9965-a98d31b23a75" />


### Round 2: PR comments and follow-ups

**Follow-ups.** One switch turns on automatic "please review" posts to your Google Chat space. Each open PR gets a post on a timer. The post tags the people in your always-cc list and the PR's reviewers. A PR drops off as soon as it merges, and drafts and promotion PRs are left out. Each PR also has **Skip** / **Unskip**, **Post now**, and shows when it was last posted.

<img width="1620" height="171" alt="image" src="https://github.com/user-attachments/assets/5bf6ed34-f2ab-4cb4-a27d-6d0e6cc46445" />


**Comments.** Review comments and review summaries on your open PRs. Each one is tagged with a severity (Blocking, High, Changes, Medium, Issue, Nit, Low, Note, Approve). Comments nobody has replied to are flagged **needs reply**. Bot comments are shortened to one line. You can filter by needs reply, severity or reviewer, and sort by newest, oldest, most severe, reviewer or PR.

"You'll see in the board hehehehe"

### Round 4: Team PRs

Open PRs from everyone in your team list (`chat-people.json`). Badges tell you where you're needed:
- **Asks you**: your review was requested
- **You: approved / commented**: your own review state
- **replied to you**: someone answered your review comment or @mentioned you. Click it to jump to the reply.

Filters include: hide drafts, promotions or approved PRs; only "replied to me", "asks for my review" or "not reviewed by me".

<img width="2560" height="1600" alt="Team PRs" src="https://github.com/user-attachments/assets/f04be337-a8bb-4346-b20f-8a17a92950f5" />


**Review drafts (optional, uses Claude).** **Draft review** asks a Claude Code session to write review comments for a PR. You untick any you don't want, then press **Post** to send them to GitHub as one review from you, or **Discard**. Nothing is posted without your click. See [SETUP.md, Claude review drafts](SETUP.md#8-optional-claude-review-drafts).

"You'd also see on the board HAHAHAHA if you use it"

### Round 5: Worktrees and the context meter

- **Create worktree**: type a ticket and press the button. It runs your worktree command (plain `git worktree add`, or your own script), and its progress shows live on the page.
- **Remove worktree**: asks you to confirm first. It refuses if the worktree has uncommitted changes, and keeps the branch.
- **One card per worktree**: branch, PR stage, uncommitted file count, and the Claude Code chats that worked on it.

<img width="2560" height="1600" alt="Worktree" src="https://github.com/user-attachments/assets/282fd850-1771-4453-a330-78f5673f0c74" />

**Context meter.** Every Claude Code chat gets one:

| Verdict | When | What to do |
|---|---|---|
| **Keep going** | under 200K tokens | Carry on. It also estimates how many more prompts fit, based on how fast this chat grows. |
| **Wrap up** | 200K to 350K | Finish the current step, then start the next task in a new chat. |
| **Start a new chat** | over 350K | Ask Claude for a handoff summary, then start a new chat. |
| **Just compacted** | right after an auto-compact | Earlier details are now a summary. For new work, a fresh chat is cleaner. |

The bar shows tokens used out of the context window. It has marks at both limits, plus a dotted line where your own chats usually auto-compact. Each chat also shows its prompt count and number of compactions, a green dot if it was active in the last 10 minutes, and a copy button for `claude --resume`. You can change the limits in `config.json`.

<img width="2560" height="1600" alt="Worktree" src="https://github.com/user-attachments/assets/f1f11d03-2d29-48b8-9273-093e998b2210" />

### Round 3: Combo moves

Pick a ticket or PR, then copy a ready-made command:

| Move | Command |
|---|---|
| Start ticket | `/start-ticket <ticket>` |
| Resolve PR | `/resolve-pr-ticket <ticket>` |
| Auto-guard | `/loop 30m /resolve-pr-ticket <ticket>` |
| Self review | `/code-review high <pr>` |
| Watch checks | `gh pr checks <pr> --watch` |
| Unresolved threads | `gh pr view <pr> --comments` |

The slash commands need the matching Claude Code skills.

<img width="2560" height="1600" alt="Moves" src="https://github.com/user-attachments/assets/c5ed3571-9ade-4274-b672-cc2de3b40d30" />

## How it works

```mermaid
flowchart LR
  GH[(GitHub)] -- gh CLI --> C
  subgraph Docker["Docker container"]
    C[control.py<br/>web server + 15-min refresh] --> R[refresh.py]
    C --> F[followup.py]
  end
  F -- webhook --> GC[(Google Chat)]
  subgraph PC["Your PC"]
    H[ta-host.py<br/>host agent] --> WT[git worktrees]
    H --> CL[~/.claude/projects<br/>chat transcripts]
  end
  R --> D[(data/*.json)]
  H --> D
  D --> B[Browser<br/>localhost:8765]
  B -- button clicks --> C
  C -- worktree jobs --> H
```

| File | Role |
|---|---|
| `ta.sh` | One command for everything: `up`, `down`, `restart`, `status`, `logs` |
| `control.py` | Local web server on `127.0.0.1:8765`. It serves the dashboard, runs the GitHub refresh on a timer, and handles button clicks (each needs a secret key) |
| `refresh.py` | Pulls your PRs, comments and team PRs with `gh`, then writes `data/*.json` |
| `followup.py` | Posts follow-ups to a Google Chat webhook. Also works as a command-line tool |
| `ta-host.py` | Host agent, runs on your PC rather than in Docker. Lists worktrees, measures how full each Claude chat is, and runs worktree jobs |
| `index.html`, `ta-local.js` | The dashboard page |
| `config.py` | Loads `config.json`. Your GitHub username comes from `gh`, never from the config |
| `drafts.py`, `DRAFTING.md` | Optional Claude review drafts |
| `chat-scrape.js`, `import_chat_ids.py` | Optional helpers to collect Google Chat user IDs for @mentions |

## FAQ

**Does it use Claude tokens?** No. Two optional features (`autoDraft`, `notifyClaude`) do, and both are off by default. See [Token use](SETUP.md#token-use).

**Does it post anything as me?**
- Follow-ups go to Google Chat through the space's webhook, so they appear under the webhook's name, not yours.
- Review drafts reach GitHub as you, but only when you press **Post**.
- Nothing else writes to GitHub.

**How do I add a teammate to Team PRs?** Add their GitHub username to `chat-people.json` and press **Refresh now**. See [SETUP.md, Add one person](SETUP.md#61-add-one-person).

**How do I set up the Google Chat webhook?** See [SETUP.md, Create the webhook](SETUP.md#51-create-the-webhook). One webhook per space is enough for the whole team.

**Can other people open my dashboard?** No. It only listens on `127.0.0.1`, and every button needs a secret key that's created on your PC.

**Will teammates see my settings?** No. Your settings and secrets (`config.json`, `gchat-webhook`, `control-token`, `chat-people.json`, `data/`) are git-ignored, so each person keeps their own.
