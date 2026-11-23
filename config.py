"""Ticket Arena settings, shared by every script.

Values come from config.json next to this file (copy config.example.json to start).
Anything missing falls back to the defaults below. Your GitHub login is never configured:
it is read from whoever `gh` is logged in as, so the same code works for every teammate.
"""
import json, subprocess
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "config.json"

DEFAULTS = {
    "repo": "your-org/your-repo",
    "ticketPrefix": "EDGE",
    "promoBranches": ["staging", "stage", "demo"],
    "stuckDays": {"review": 2, "promoting": 2},
    "refreshMinutes": 15,
    "chatSpaceName": "your team's Google Chat space",
    "alwaysCc": [],
    "firstMessage": "Good day team please review this pr thank you!",
    "bumpMessage": "Good day team bumping this for re-approval thank you!",
    # worktrees + context calculator (ta-host.py, runs on your PC)
    "worktreeMain": "~/projects/your-repo",
    "worktreeNewCommand": "git worktree add ../worktree-{num} -b {prefix}/{num} origin/main",
    "worktreeRemoveCommand": "git worktree remove ../worktree-{num}",
    "claudeProjectsDir": "~/.claude/projects",
    "sessionDays": 7,
    "contextWindow": 1000000,
    "contextWarnTokens": 200000,
    "contextStopTokens": 350000,
    "hostIntervalSeconds": 15,
    # how Run buttons open a terminal; "" = auto (Windows Terminal on WSL, Terminal.app on macOS,
    # x-terminal-emulator on Linux). Placeholders: {script} {title} {cwd}
    "terminalCommand": "",
    # Claude features that spend tokens: both off unless you turn them on
    "autoDraft": False,       # queue a Claude review draft for PRs that request your review
    "notifyClaude": False,    # write REFRESH lines so a watching Claude session re-uploads to claude.ai
}


@lru_cache(maxsize=1)
def load():
    d = json.loads(json.dumps(DEFAULTS))
    if FILE.exists():
        d.update(json.loads(FILE.read_text()))
    return d


def get(key):
    return load()[key]


@lru_cache(maxsize=1)
def login():
    """GitHub login of whoever gh is authenticated as (GH_TOKEN or `gh auth login`)."""
    r = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True)
    return r.stdout.strip()


def for_page(token=""):
    """The subset of settings the dashboard needs, as JSON-safe data."""
    c = load()
    people_file = HERE / "chat-people.json"
    people = json.loads(people_file.read_text()) if people_file.exists() else {}
    cc = [people.get(x, {}).get("name") or x for x in c["alwaysCc"]]
    return {k: c[k] for k in ("repo", "ticketPrefix", "promoBranches", "stuckDays", "refreshMinutes", "chatSpaceName")} \
        | {"login": login(), "key": token, "ccNames": cc, "firstMessage": c["firstMessage"]}
