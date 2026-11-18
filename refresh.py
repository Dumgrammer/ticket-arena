#!/usr/bin/env python3
"""Ticket Arena refresh: pulls your PRs and review comments from GitHub (gh CLI)
and writes tickets.json / comments.json for the dashboard.

Prints one of:
  UNCHANGED                      data is identical to the last run
  CHANGED <files...>             new data written
and, for tickets that newly passed their stuck limit:
  NEW_STUCK <key> <stage> <days>d
"""
import hashlib, json, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

REPO = config.get("repo")
PROMO = tuple(config.get("promoBranches"))
TICKET_RE = re.escape(config.get("ticketPrefix")) + r"-\d+"
_STATE = Path(__file__).resolve().parent / "data" / "state.json"
if len(sys.argv) > 1 and sys.argv[1] == "--pending":
    # report what the Docker container already fetched but claude.ai doesn't have yet (no GitHub calls)
    st = json.loads(_STATE.read_text()) if _STATE.exists() else {}
    print("CHANGED " + " ".join(st.get("pending", [])) if st.get("pending") else "UNCHANGED")
    sys.exit(0)
if len(sys.argv) > 1 and sys.argv[1] == "--mark-uploaded":
    st = json.loads(_STATE.read_text()) if _STATE.exists() else {}
    st["pending"] = [n for n in st.get("pending", []) if n not in sys.argv[2:]]
    _STATE.write_text(json.dumps(st))
    print("pending: " + (" ".join(st["pending"]) or "none"))
    sys.exit(0)
OUT = Path(__file__).resolve().parent / "data"
OUT.mkdir(exist_ok=True)
STUCK_DAYS = config.get("stuckDays")  # the dashboard reads the same values from config.json
ORDER = ["closed", "review", "merged", "promoting", "staging"]


def gh(*args):
    # GitHub's API sometimes times out on big queries; retry before giving up
    import time
    for attempt in range(3):
        r = subprocess.run(["gh", *args], capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout or "null")
        time.sleep(3 * (attempt + 1))
    raise subprocess.CalledProcessError(r.returncode, ["gh", *args], r.stdout, r.stderr)


ME = config.login()
if not ME:
    sys.exit("gh is not logged in: run `gh auth login` or set GH_TOKEN")
NOW = datetime.now(timezone.utc)

prs = gh("pr", "list", "-R", REPO, "--author", "@me", "--state", "all", "--limit", "50", "--json",
         "number,title,url,state,isDraft,baseRefName,createdAt,mergedAt,updatedAt,reviewDecision,additions,deletions")
promos = []
for base in PROMO:
    promos += [dict(p, base=base) for p in gh("pr", "list", "-R", REPO, "--base", base, "--state", "all", "--limit", "100",
                                              "--json", "number,title,url,state,createdAt,mergedAt,author")]

# ---- tickets -------------------------------------------------------------
tickets = {}
my_numbers = {p["number"] for p in prs}
for p in sorted(prs, key=lambda p: p["createdAt"]):
    m = re.match(rf"({TICKET_RE}):\s*(.*)", p["title"])
    if not m:
        continue
    key, title = m.group(1), re.sub(r"\s*\(main → [^)]*\)", "", m.group(2))
    t = tickets.setdefault(key, dict(key=key, ticket=key.split("-")[1], title=title, prs=0, lines=0,
                                     stage="closed", stageSince=p["createdAt"], pr=p["number"], url=p["url"],
                                     target=p["baseRefName"], reviewDecision="", updated=p["updatedAt"]))
    t["prs"] += 1
    t["lines"] += p["additions"] + p["deletions"]
    t["updated"] = max(t["updated"], p["updatedAt"])
    promo = p["baseRefName"] in PROMO
    if p["state"] == "OPEN":
        st, since = ("promoting" if promo else "review"), p["createdAt"]
    elif p["state"] == "MERGED":
        st, since = ("staging" if promo else "merged"), p["mergedAt"]
    else:
        continue
    if ORDER.index(st) >= ORDER.index(t["stage"]):
        t.update(stage=st, stageSince=since, pr=p["number"], url=p["url"], target=p["baseRefName"],
                 reviewDecision=p.get("reviewDecision") or "")

# promotions opened by teammates ("Promote #5678 to staging")
for q in promos:
    if q["author"]["login"] == ME:
        continue
    for n in map(int, re.findall(r"#(\d+)", q["title"])):
        if n not in my_numbers:
            continue
        src = next(p for p in prs if p["number"] == n)
        m = re.match(rf"({TICKET_RE})", src["title"])
        t = tickets.get(m.group(1)) if m else None
        if not t:
            continue
        st = "staging" if q["state"] == "MERGED" else "promoting" if q["state"] == "OPEN" else None
        if st and ORDER.index(st) > ORDER.index(t["stage"]):
            t.update(stage=st, stageSince=q["mergedAt"] if st == "staging" else q["createdAt"],
                     pr=q["number"], url=q["url"], target=q["base"], reviewDecision="")

for t in tickets.values():
    days = (NOW - datetime.fromisoformat(t["stageSince"].replace("Z", "+00:00"))).total_seconds() / 86400
    t["limitDays"] = STUCK_DAYS.get(t["stage"])
    t["stuck"] = "yes" if t["limitDays"] is not None and days >= t["limitDays"] else "no"
ticket_rows = sorted(tickets.values(), key=lambda t: t["updated"], reverse=True)

# ---- automatic Google Chat follow-ups ------------------------------------
import followup  # noqa: E402

follow_prs = [p["number"] for p in prs
              if p["state"] == "OPEN" and not p["isDraft"] and p["baseRefName"] not in PROMO]
for line in followup.auto_round(follow_prs):
    print("FOLLOWUP " + line.splitlines()[0])
fs = followup.load_settings()
for t in ticket_rows:
    if t["stage"] == "review" and t["pr"] in follow_prs:
        t["followUp"] = "skipped" if str(t["pr"]) in map(str, fs["skip"]) else ("on" if fs["enabled"] else "off")
        t["lastFollowUp"] = fs["lastPosted"].get(str(t["pr"]))
    else:
        t["followUp"] = None
        t["lastFollowUp"] = None
    t["followEvery"] = fs["intervalMinutes"]

# ---- comments ------------------------------------------------------------
def clean(b):
    b = re.sub(r"<details>.*", "", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    b = re.sub(r"\*\*|`|🤖|—", " ", b).replace("Agent :", "").replace("Agent:", "")
    return re.sub(r"\s+", " ", b).strip()


def severity(b):
    if b.lstrip("* ").upper().startswith("PASS"):
        return "Pass"
    u = b.upper()
    for k, v in [("BLOCKING", "Blocking"), ("HIGH", "High"), ("CHANGES REQUESTED", "Changes"), ("MEDIUM", "Medium"),
                 ("ISSUE", "Issue"), ("NIT", "Nit"), ("LOW", "Low"), ("LGTM", "Approve"), ("APPROVED", "Approve")]:
        if re.search(r"\b" + k + r"\b", u):
            return v
    return "Note"


# only PRs still open: once a PR is merged its comments count as resolved
recent = [p for p in prs if p["state"] == "OPEN"]
raw = []
for p in recent:
    n = p["number"]
    for c in gh("api", f"repos/{REPO}/pulls/{n}/comments?per_page=100"):
        raw.append(dict(pr=n, author=c["user"]["login"], body=c["body"] or "", path=c.get("path"),
                        line=c.get("line") or c.get("original_line"), at=c["created_at"], url=c["html_url"],
                        thread=c.get("in_reply_to_id") or c["id"], state=None))
    for r in gh("api", f"repos/{REPO}/pulls/{n}/reviews?per_page=100"):
        if r.get("body"):
            raw.append(dict(pr=n, author=r["user"]["login"], body=r["body"], path=None, line=None,
                            at=r["submitted_at"], url=r["html_url"], thread=None, state=r["state"]))

title_of = {p["number"]: p["title"] for p in prs}
comments = []
for c in raw:
    a, b = c["author"], c["body"]
    if a == ME or "quota" in b:
        continue
    kind = "bot" if "[bot]" in a else ("agent" if "Agent" in b[:20] or b.startswith("**") else "human")
    body = clean(b)
    if kind == "bot":
        m = re.search(r"Code Quality Violation\s*(.+?)\(\.\.\.read more", re.sub(r"<[^>]+>", " ", b).replace("\n", " "))
        body = ("Code quality: " + m.group(1).strip()) if m else "Code quality violation"
        sev = "Low" if "Low" in b[:120] else "Medium"
    else:
        sev = "Approve" if c["state"] == "APPROVED" else severity(b)
    # answered: you commented on the PR afterwards, or anyone replied later in the same thread
    answered = any(x["pr"] == c["pr"] and x["at"] > c["at"] and (x["author"] == ME or (c["thread"] and x["thread"] == c["thread"]))
                   for x in raw)
    m = re.match(rf"({TICKET_RE})", title_of.get(c["pr"], ""))
    needs = answered is False and kind != "bot" and sev not in ("Pass", "Approve", "Note")
    comments.append(dict(id=f"{c['pr']}-{c['at']}-{a}", pr=c["pr"], ticket=m.group(1) if m else None, author=a, kind=kind,
                         severity=sev, body=body[:240], path=(c["path"] or "").split("/")[-1] or None, line=c["line"],
                         at=c["at"], url=c["url"], answered="yes" if answered else "no", needsReply="yes" if needs else "no"))
comments.sort(key=lambda c: c["at"], reverse=True)

# ---- teammates' open PRs -------------------------------------------------
people = json.loads((Path(__file__).resolve().parent / "chat-people.json").read_text()) \
    if (Path(__file__).resolve().parent / "chat-people.json").exists() else {}
# one small query per teammate: a single query for every open PR times out (HTTP 502)
team_raw = []
for _login in people:
    if _login == ME:
        continue
    try:
        team_raw += gh("pr", "list", "-R", REPO, "--state", "open", "--author", _login, "--limit", "30", "--json",
                       "number,title,url,author,isDraft,createdAt,updatedAt,reviewDecision,reviewRequests,"
                       "latestReviews,baseRefName,additions,deletions,headRefOid")
    except subprocess.CalledProcessError:
        print(f"TEAM_SKIPPED {_login}")
team = []
for q in team_raw:
    login = q["author"]["login"]
    if login == ME or login not in people:
        continue
    requested = any((r.get("login") or "") == ME for r in q.get("reviewRequests", []))
    mine = [r for r in q.get("latestReviews", []) if (r.get("author") or {}).get("login") == ME]
    team.append(dict(pr=q["number"], title=q["title"], url=q["url"], author=login,
                     name=people.get(login, {}).get("name") or login, isDraft="yes" if q["isDraft"] else "no",
                     decision=q.get("reviewDecision") or "", base=q["baseRefName"],
                     lines=q["additions"] + q["deletions"], opened=q["createdAt"], updated=q["updatedAt"],
                     requestedMe="yes" if requested else "no", myReview=mine[0]["state"] if mine else "",
                     headSha=q.get("headRefOid", "")))
team.sort(key=lambda r: r["updated"], reverse=True)

# ---- replies waiting on me in teammates' PRs -----------------------------
# A thread "waits on me" when I commented in it and the newest comment is someone else's.
# A conversation comment waits on me when it @mentions me and is newer than my last comment there.
BOTS = ("[bot]", "copilot", "aikido", "datadog", "github-actions")
def _human(login):
    return login and login != ME and not any(b in login.lower() for b in BOTS)

for r in team:
    waiting = []
    try:
        rc = gh("api", f"repos/{REPO}/pulls/{r['pr']}/comments?per_page=100")
        ic = gh("api", f"repos/{REPO}/issues/{r['pr']}/comments?per_page=100")
    except subprocess.CalledProcessError:
        r.update(repliesToMe=0, replyBy="", replyAt="", replyUrl="")
        continue
    threads = {}
    for c in rc:
        threads.setdefault(c.get("in_reply_to_id") or c["id"], []).append(c)
    for cs in threads.values():
        cs.sort(key=lambda c: c["created_at"])
        if any(c["user"]["login"] == ME for c in cs) and _human(cs[-1]["user"]["login"]):
            waiting.append(cs[-1])
    my_last = max([c["created_at"] for c in rc + ic if c["user"]["login"] == ME] or [""])
    for c in ic:
        if _human(c["user"]["login"]) and f"@{ME.lower()}" in (c.get("body") or "").lower() and c["created_at"] > my_last:
            waiting.append(c)
    waiting.sort(key=lambda c: c["created_at"])
    last = waiting[-1] if waiting else None
    r.update(repliesToMe=len(waiting),
             replyBy=(people.get(last["user"]["login"], {}).get("name") or last["user"]["login"]) if last else "",
             replyAt=last["created_at"] if last else "",
             replyUrl=last["html_url"] if last else "")


# auto-draft reviews for PRs that ask for my review (once per head commit)
_drafts_file = Path(__file__).resolve().parent / "data" / "drafts.json"
_drafts = {str(d["pr"]): d for d in (json.loads(_drafts_file.read_text()) if _drafts_file.exists() else [])}
_state_file = Path(__file__).resolve().parent / "data" / "state.json"
_auto = (json.loads(_state_file.read_text()) if _state_file.exists() else {}).get("autoDrafted", {})
for r in team:
    if r["requestedMe"] == "yes" and r["isDraft"] == "no" and not r["myReview"] \
            and _auto.get(str(r["pr"])) != r["headSha"] and _drafts.get(str(r["pr"]), {}).get("status") not in ("drafting", "ready"):
        print(f"AUTO_DRAFT {r['pr']}")
        _auto[str(r["pr"])] = r["headSha"]
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent / "drafts.py"), "status", str(r["pr"]), "drafting"],
                       capture_output=True)
        with open(Path(__file__).resolve().parent / "requests.log", "a") as _f:
            _f.write(f"DRAFT {r['pr']} auto\n")

# ---- write + report ------------------------------------------------------
state_file = OUT / "state.json"
state = json.loads(state_file.read_text()) if state_file.exists() else {}
changed = []
state["autoDrafted"] = _auto
# announce replies to me that are new since the last run (a newer reply on the same PR counts too)
_prev_replies = state.get("replies", {})
_now_replies = {str(r["pr"]): r["replyAt"] for r in team if r.get("repliesToMe")}
for _pr, _at in _now_replies.items():
    if _prev_replies.get(_pr, "") < _at:
        _r = next(x for x in team if str(x["pr"]) == _pr)
        print(f"NEW_REPLY {_pr} {_r['replyBy']} on {_r['name']}'s PR: {_r['title'][:60]}")
state["replies"] = _now_replies
for name, rows in (("tickets", ticket_rows), ("comments", comments), ("team", team)):
    text = json.dumps(rows, ensure_ascii=False)
    h = hashlib.sha256(text.encode()).hexdigest()
    if state.get(name) != h:
        (OUT / f"{name}.json").write_text(text)
        state[name] = h
        changed.append(name)

prev_stuck = set(state.get("stuck", []))
now_stuck = {t["key"] for t in ticket_rows if t["stuck"] == "yes"}
for t in ticket_rows:
    if t["key"] in now_stuck - prev_stuck:
        days = (NOW - datetime.fromisoformat(t["stageSince"].replace("Z", "+00:00"))).days
        print(f"NEW_STUCK {t['key']} {t['stage']} {days}d")
state["stuck"] = sorted(now_stuck)
state["at"] = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
state_file.write_text(json.dumps(state))
pending = sorted(set(state.get("pending", [])) | set(changed))
state["pending"] = pending
state_file.write_text(json.dumps(state))
# CHANGED lists every file not yet uploaded, even if another run already wrote it
print("CHANGED " + " ".join(pending) if pending else "UNCHANGED")
