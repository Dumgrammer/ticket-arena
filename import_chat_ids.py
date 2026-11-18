#!/usr/bin/env python3
"""Merge Google Chat IDs (from chat-scrape.js) into chat-people.json.

Usage: paste the scraper's output into chat-ids.json (next to this script), then run
  python3 import_chat_ids.py

It matches each Chat name to a GitHub username by comparing it with the GitHub profile
names of everyone who reviewed your PRs. Entries it can't match are listed so you can add
them by hand. Existing entries are kept; keys that aren't GitHub usernames are fixed when
their name matches a reviewer.
"""
import json, re, subprocess, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402

REPO = config.get("repo")
IDS = HERE / "chat-ids.json"
PEOPLE = HERE / "chat-people.json"


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).split()


def gh(*args):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=True).stdout


def reviewers():
    """GitHub logins who reviewed or commented on your last 50 PRs, with their profile names."""
    sys.path.insert(0, str(HERE))
    from followup import NOT_PEOPLE  # same bot list the follow-ups use
    me = config.login()
    bots = NOT_PEOPLE + ("github-actions",)
    prs = json.loads(gh("pr", "list", "-R", REPO, "--author", "@me", "--state", "all", "--limit", "50", "--json", "number"))
    logins = set()
    for p in prs:
        data = json.loads(gh("pr", "view", str(p["number"]), "-R", REPO, "--json", "reviews,comments"))
        for x in data.get("reviews", []) + data.get("comments", []):
            login = (x.get("author") or {}).get("login")
            if login and login != me and not any(b in login.lower() for b in bots) and not login.endswith("-bot"):
                logins.add(login)
    names = {}
    for login in sorted(logins):
        try:
            names[login] = gh("api", f"users/{login}", "--jq", ".name // empty").strip()
        except subprocess.CalledProcessError:
            names[login] = ""
    return names


def match(chat_name, gh_names):
    """Best GitHub login for a Chat display name: exact name, then first+last name overlap."""
    c = norm(chat_name)
    if not c:
        return None
    best, score = None, 0
    for login, name in gh_names.items():
        g = norm(name)
        if g and g == c:
            return login
        overlap = len(set(c) & set(g))
        if g and overlap >= 2 and c[0] == g[0] and overlap > score:
            best, score = login, overlap
    return best


def main():
    if not IDS.exists():
        print(f"Paste the scraper's output into {IDS} first.")
        return 1
    found = json.loads(IDS.read_text())
    people = json.loads(PEOPLE.read_text()) if PEOPLE.exists() else {}
    print("Looking up who reviews your PRs on GitHub...")
    gh_names = reviewers()

    # fix existing entries keyed by something that isn't a reviewer's GitHub username
    for key in list(people):
        if key not in gh_names:
            login = match(people[key].get("name", ""), gh_names)
            if login and login not in people:
                people[login] = people.pop(key)
                print(f"  fixed key  {key} -> {login}")

    added, unmatched = [], []
    for chat_name, uid in found.items():
        login = match(chat_name, gh_names)
        if not login:
            unmatched.append(chat_name)
            continue
        entry = people.setdefault(login, {})
        if entry.get("id") != uid:
            entry.update(name=chat_name, id=uid)
            added.append(f"{login} = {chat_name}")

    PEOPLE.write_text(json.dumps(people, indent=2, ensure_ascii=False) + "\n")
    print(f"Added or updated {len(added)}:")
    for a in added:
        print("  " + a)
    missing = [f"{l} ({n or 'no name'})" for l, n in gh_names.items() if l not in people]
    if missing:
        print("Reviewers still without a Chat ID (plain @name in posts):")
        for m in missing:
            print("  " + m)
    if unmatched:
        print(f"{len(unmatched)} Chat names matched no reviewer (fine if they never review your PRs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
