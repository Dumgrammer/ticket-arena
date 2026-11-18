#!/usr/bin/env python3
"""Post a follow-up about one PR to Google Chat, unless it is already merged.

Usage: followup.py <pr-number> [--dry]

Prints one line:
  MERGED <pr> ...    the PR is merged (or closed); stop the loop
  POSTED <pr> ...    a follow-up was sent to Google Chat
  DRY <pr> ...       --dry: shows the message without sending it
  ERROR ...          nothing was sent (missing webhook, gh or network failure)

The Google Chat incoming-webhook URL is read from gchat-webhook next to this script
(one line, keep it private: chmod 600). It never goes into the dashboard.
"""
import json, subprocess, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

REPO = config.get("repo")
HOOK_FILE = Path(__file__).resolve().parent / "gchat-webhook"


PEOPLE_FILE = Path(__file__).resolve().parent / "chat-people.json"
ALWAYS_CC = config.get("alwaysCc")  # GitHub logins cc'd on every follow-up
NOT_PEOPLE = ("[bot]", "copilot", "aikido", "datadog", "sonar", "codecov", "dependabot", "renovate")


def gh_name(login):
    try:
        r = subprocess.run(["gh", "api", f"users/{login}", "--jq", ".name // empty"], capture_output=True, text=True, check=True)
        return r.stdout.strip() or login
    except subprocess.CalledProcessError:
        return login


def cc_list(p):
    """@mentions: the alwaysCc people first, then everyone else who reviewed the PR (not you, not bots).

    chat-people.json maps a GitHub login to {"name": "Chat display name", "id": "Google Chat user id"}.
    With an id the mention really pings them (<users/ID>); without one it is plain "@Name" text.
    """
    people = json.loads(PEOPLE_FILE.read_text()) if PEOPLE_FILE.exists() else {}
    me = config.login()
    logins = list(ALWAYS_CC)
    for rv in p.get("reviews", []):
        login = rv["author"]["login"]
        if login == me or login in logins or any(x in login.lower() for x in NOT_PEOPLE):
            continue
        logins.append(login)
    out = []
    for login in logins:
        info = people.get(login, {})
        if info.get("id"):
            out.append(f"<users/{info['id']}>")
        else:
            out.append("@" + (info.get("name") or gh_name(login)))
    return out


SETTINGS_FILE = Path(__file__).resolve().parent / "followups.json"
THREADS_FILE = Path(__file__).resolve().parent / "threads.json"  # PR number -> Chat thread of its first message


def load_threads():
    return json.loads(THREADS_FILE.read_text()) if THREADS_FILE.exists() else {}


def save_thread(n, thread_name):
    t = load_threads()
    t[str(n)] = thread_name
    THREADS_FILE.write_text(json.dumps(t, indent=2) + "\n")
DEFAULTS = {"enabled": False, "intervalMinutes": 45, "skip": [], "lastPosted": {}}


def load_settings():
    d = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        d.update(json.loads(SETTINGS_FILE.read_text()))
    return d


def save_settings(d):
    SETTINGS_FILE.write_text(json.dumps(d, indent=2) + "\n")


def follow_one(n, dry=False):
    """Check one PR and post its follow-up. Returns one line: MERGED / POSTED / DRY / ERROR."""
    n = str(n)
    try:
        r = subprocess.run(["gh", "pr", "view", n, "-R", REPO, "--json",
                            "number,title,url,state,baseRefName,createdAt,mergedAt,reviewDecision,reviews,isDraft"],
                           capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        return f"ERROR gh failed for #{n}: {e.stderr.strip()[:200]}"
    p = json.loads(r.stdout)
    if p["state"] == "MERGED":
        return f"MERGED {n} into {p['baseRefName']} at {p['mergedAt']}"
    if p["state"] == "CLOSED":
        return f"MERGED {n} closed without merging; nothing to follow up"

    thread = load_threads().get(n)
    cc = "cc: " + " ".join(cc_list(p))
    if thread:
        # already posted once: bump it with a new message at the bottom of the space
        text = config.get("bumpMessage") + "\n" + p["url"] + "\n" + cc
    else:
        text = config.get("firstMessage") + "\n" + p["url"] + "\n" + cc
    if dry:
        return "DRY " + n + (" (bump)" if thread else " (first post)") + "\n" + text
    if not HOOK_FILE.exists():
        return f"ERROR no Google Chat webhook: save the space's webhook URL in {HOOK_FILE}"
    hook = HOOK_FILE.read_text().strip()
    if not hook.startswith("https://chat.googleapis.com/"):
        return "ERROR the webhook file does not hold a https://chat.googleapis.com/ URL"
    url = hook
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json; charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            sent = json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return f"ERROR Google Chat refused the post for #{n}: {e.code} {e.read().decode()[:200]}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR could not reach Google Chat for #{n}: {str(e)[:200]}"
    if not thread and (sent.get("thread") or {}).get("name"):
        save_thread(n, sent["thread"]["name"])  # remembers that this PR has been posted once
    return f"POSTED {n} {'bump' if thread else 'new'} {sent.get('name', '')}"


def auto_round(open_prs, dry=False):
    """Called by refresh.py with the open, non-draft PRs headed for main or a feature branch.
    Posts for each PR whose last follow-up is older than the interval. Returns output lines."""
    d = load_settings()
    if not d["enabled"]:
        return []
    now = datetime.now(timezone.utc)
    out = []
    open_set = {str(n) for n in open_prs}
    for n in sorted(open_set):
        if n in map(str, d["skip"]):
            continue
        last = d["lastPosted"].get(n)
        if last and (now - datetime.fromisoformat(last)).total_seconds() < d["intervalMinutes"] * 60 - 120:
            continue
        line = follow_one(n, dry)
        out.append(line)
        if line.startswith("POSTED"):
            d["lastPosted"][n] = now.isoformat(timespec="seconds")
    # forget PRs that are no longer open
    d["lastPosted"] = {k: v for k, v in d["lastPosted"].items() if k in open_set}
    if not dry:
        save_settings(d)
    return out


def status_line(d=None):
    d = d or load_settings()
    s = "ON" if d["enabled"] else "OFF"
    return f"Auto follow-ups {s} · every {d['intervalMinutes']} min · skipped PRs: {', '.join(map(str, d['skip'])) or 'none'}"


USAGE = """followup.py start            turn automatic follow-ups on (next refresh posts)
followup.py stop             turn them off
followup.py status           show on/off, interval, skipped PRs
followup.py every <minutes>  change the interval
followup.py skip <pr>        never follow up this PR
followup.py unskip <pr>      follow it up again
followup.py <pr> [--dry]     post one follow-up now (--dry shows it without posting)"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if not args:
        print(USAGE)
        return 2
    cmd = args[0]
    d = load_settings()
    if cmd in ("start", "stop"):
        d["enabled"] = cmd == "start"
        save_settings(d)
        print(status_line(d))
        return 0
    if cmd == "status":
        print(status_line(d))
        return 0
    if cmd == "every" and len(args) > 1 and args[1].isdigit() and int(args[1]) >= 15:
        d["intervalMinutes"] = int(args[1])
        save_settings(d)
        print(status_line(d))
        return 0
    if cmd in ("skip", "unskip") and len(args) > 1 and args[1].isdigit():
        skip = [str(x) for x in d["skip"] if str(x) != args[1]]
        if cmd == "skip":
            skip.append(args[1])
        d["skip"] = skip
        save_settings(d)
        print(status_line(d))
        return 0
    if cmd.isdigit():
        line = follow_one(cmd, dry)
        print(line)
        return 1 if line.startswith("ERROR") else 0
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
