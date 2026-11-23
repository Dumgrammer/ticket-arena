#!/usr/bin/env python3
"""Ticket Arena host agent: worktrees + Claude context calculator.

Runs on your PC (not in Docker), because it needs your git checkouts, your worktree
command (e.g. my-wt, which runs pnpm) and your Claude Code transcripts.

Every few seconds it:
  - lists the worktrees of `worktreeMain` (git worktree list), with branch, ticket and dirty files
  - reads the Claude Code sessions in ~/.claude/projects (only what was appended since last time)
    and works out how full each session's context is
  - runs worktree jobs the dashboard queued in requests.log ("WT_NEW <ticket>", "WT_RM <ticket>")
and writes data/worktrees.json for the dashboard.

  python3 ta-host.py            keep running (Ctrl+C to stop)
  python3 ta-host.py --once     one pass, then exit
"""
import json, os, re, shlex, subprocess, sys, threading, time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402

C = config.load()
MAIN = Path(os.path.expanduser(C["worktreeMain"]))
PROJECTS = Path(os.path.expanduser(C["claudeProjectsDir"]))
OUT = HERE / "data" / "worktrees.json"
LOG = HERE / "requests.log"
STATE = HERE / "data" / "host-state.json"
TICKET_OK = re.compile(r"^(?:[A-Za-z]+-)?\d{2,7}$")   # 1234, PROJ-1234, DEVOPS-1234
PREFIX = config.get("ticketPrefix")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run(*args, cwd=None, timeout=30):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


# ---- worktrees -------------------------------------------------------------
def worktrees():
    out, cur = [], {}
    for line in run("git", "-C", str(MAIN), "worktree", "list", "--porcelain").splitlines() + [""]:
        if line.startswith("worktree "):
            cur = {"path": line[9:], "branch": "", "detached": False}
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "detached":
            cur["detached"] = True
        elif not line and cur:
            out.append(cur)
            cur = {}
    rows = []
    for w in out:
        p = Path(w["path"])
        m = re.search(r"(\d{4,7})", w["branch"] or p.name)
        rows.append({
            "path": str(p), "name": p.name, "branch": w["branch"] or "(detached)",
            "ticket": m.group(1) if m else "",
            "isMain": p == MAIN, "agent": "/.agent-worktrees/" in str(p) or "/.claude/worktrees/" in str(p),
            "exists": p.is_dir(),
            "dirty": len(run("git", "-C", str(p), "status", "--short").splitlines()) if p.is_dir() else None,
            "sessions": [],
        })
    return rows


# ---- Claude sessions (incremental) ----------------------------------------
class Session:
    """Aggregates one transcript, reading only bytes appended since the last pass."""

    def __init__(self, path):
        self.path, self.offset = path, 0
        self.id = path.stem
        self.title = self.custom = self.first = self.model = ""
        self.cwds, self.branches = {}, {}
        self.used = 0            # context size after the newest main-thread API call
        self.per_prompt = []     # context size at the end of each of your prompts
        self.prompts = 0
        self.compactions = 0
        self.pre_tokens = []     # context size at each auto/manual compaction
        self.last_at = ""
        self.compacted_pending = False

    def feed(self):
        size = self.path.stat().st_size
        if size < self.offset:   # file was rewritten
            self.__init__(self.path)
        if size == self.offset:
            return
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            data = f.read()
        end = data.rfind(b"\n") + 1      # keep a half-written last line for next time
        self.offset += end
        for raw in data[:end].splitlines():
            if b'"api-request' in raw[:40]:
                continue
            try:
                o = json.loads(raw)
            except ValueError:
                continue
            self.line(o)

    def line(self, o):
        t = o.get("type")
        if t == "ai-title":
            self.title = o.get("aiTitle") or self.title
            return
        if t == "custom-title":
            self.custom = o.get("customTitle") or self.custom
            return
        if o.get("isSidechain"):
            return
        if o.get("cwd"):
            self.cwds[o["cwd"]] = self.cwds.get(o["cwd"], 0) + 1
        if o.get("gitBranch"):
            self.branches[o["gitBranch"]] = self.branches.get(o["gitBranch"], 0) + 1
        if o.get("timestamp"):
            self.last_at = max(self.last_at, o["timestamp"])
        if t == "system" and o.get("subtype") == "compact_boundary":
            self.compactions += 1
            pre = (o.get("compactMetadata") or {}).get("preTokens")
            if pre:
                self.pre_tokens.append(pre)
            # the new size is only known after the next reply; start growth tracking from scratch
            self.used, self.per_prompt, self.compacted_pending = 0, [], True
            return
        msg = o.get("message") if isinstance(o.get("message"), dict) else {}
        if t == "user" and not o.get("isMeta") and not o.get("isCompactSummary"):
            c = msg.get("content")
            text = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c or [] if isinstance(x, dict) and x.get("type") == "text")
            if text and not text.startswith("<") and not text.startswith("Base directory for this skill"):
                if self.prompts and self.used:
                    self.per_prompt.append(self.used)
                self.prompts += 1
                if not self.first:
                    self.first = text.strip()[:140]
            elif text.startswith("Base directory for this skill") and not self.first:
                self.first = "/" + text.split("/skills/")[-1].split()[0].strip("/") if "/skills/" in text else text[:60]
            return
        if t == "assistant" and msg.get("usage") and msg.get("model") != "<synthetic>":
            u = msg["usage"]
            self.used = (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                         + u.get("cache_read_input_tokens", 0) + u.get("output_tokens", 0))
            self.model = msg.get("model") or self.model
            self.compacted_pending = False

    def growth(self):
        """Average context added per prompt over your last 6 prompts (since the last compaction drop)."""
        pts = self.per_prompt[-7:] + [self.used]
        deltas = [b - a for a, b in zip(pts, pts[1:]) if b >= a]
        return int(sum(deltas) / len(deltas)) if deltas else 0


SESSIONS = {}


def scan_sessions():
    cutoff = time.time() - int(C["sessionDays"]) * 86400
    seen = []
    for d in PROJECTS.glob("*"):
        for f in d.glob("*.jsonl"):
            try:
                if f.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            s = SESSIONS.get(f)
            if s is None:
                s = SESSIONS[f] = Session(f)
            try:
                s.feed()
            except OSError:
                continue
            seen.append(s)
    return seen


def prmap():
    f = HERE / "data" / "prmap.json"
    return json.loads(f.read_text()) if f.exists() else {}


def attach(rows, sessions):
    """Put each session under the worktree it worked in: by directory, else ticket/PR number in its title."""
    by_path = sorted([r for r in rows if r["exists"]], key=lambda r: -len(r["path"]))
    by_ticket = {}
    for r in rows:
        if r["ticket"] and not r["isMain"] and not r["agent"]:
            by_ticket.setdefault(r["ticket"], r)
    main = next((r for r in rows if r["isMain"]), None)
    prs = prmap()
    window, warn, stop = int(C["contextWindow"]), int(C["contextWarnTokens"]), int(C["contextStopTokens"])
    live_secs = 10 * 60
    for s in sessions:
        if not s.used and not s.compacted_pending:
            continue
        cwd = max(s.cwds, key=s.cwds.get) if s.cwds else ""
        home = next((r for r in by_path if cwd == r["path"] or cwd.startswith(r["path"] + "/")), None)
        if home is None and not cwd.startswith(str(MAIN.parent)):
            continue                     # a session from some other project
        if home is None or home["isMain"]:
            text = " ".join([s.custom, s.title, s.first])
            nums = re.findall(r"(?<![\d#/])(\d{4,7})(?!\d)", text) + re.findall(r"(?:#|/pull/)(\d{3,7})", text)
            for n in nums:
                key = prs.get(n, n)                      # a PR number maps to its ticket
                if key in by_ticket:
                    home = by_ticket[key]
                    break
        home = home or main
        if home is None:
            continue
        g = s.growth()
        left = max(stop - s.used, 0)
        status = "compacted" if s.compacted_pending else "new" if s.used >= stop else "wrap" if s.used >= warn else "ok"
        age = time.time() - s.path.stat().st_mtime
        home["sessions"].append({
            "id": s.id, "title": s.custom or s.title or s.first[:60] or s.id[:8], "first": s.first,
            "cwd": cwd, "model": s.model, "used": s.used, "pct": round(100 * s.used / window, 1),
            "status": status, "prompts": s.prompts, "compactions": s.compactions,
            "growth": g, "promptsLeft": (left // g) if g and not s.compacted_pending else None, "tokensLeft": left,
            "lastAt": s.last_at, "live": age < live_secs,
            "resume": f"cd {shlex.quote(cwd or home['path'])} && claude --resume {s.id}",
        })
    for r in rows:
        r["sessions"].sort(key=lambda x: x["lastAt"], reverse=True)


# ---- jobs from the dashboard ----------------------------------------------
JOBS = []          # newest last; kept in memory and written into worktrees.json
JOB_LOCK = threading.Lock()


def job_cmd(action, ticket):
    tpl = C["worktreeNewCommand"] if action == "new" else C["worktreeRemoveCommand"]
    ticket_num = re.sub(r"\D", "", ticket)
    return [a.replace("{ticket}", ticket).replace("{num}", ticket_num).replace("{prefix}", PREFIX)
             .replace("{main}", str(MAIN)) for a in shlex.split(os.path.expanduser(tpl))]


def start_job(action, ticket):
    if not TICKET_OK.match(ticket):
        return
    with JOB_LOCK:
        if any(j["ticket"] == ticket and j["status"] == "running" for j in JOBS):
            return
        job = {"action": action, "ticket": ticket, "status": "running", "startedAt": now_iso(), "endedAt": "", "tail": []}
        JOBS.append(job)
        del JOBS[:-8]

    def work():
        cmd = job_cmd(action, ticket)
        job["command"] = " ".join(cmd)
        try:
            p = subprocess.Popen(cmd, cwd=str(MAIN), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 env=dict(os.environ, CI="1"))
            for ln in p.stdout:
                ln = ln.rstrip()
                if ln:
                    job["tail"] = (job["tail"] + [ln[-200:]])[-6:]
            ok = p.wait() == 0
        except FileNotFoundError as e:
            job["tail"].append(f"command not found: {e.filename}")
            ok = False
        job.update(status="done" if ok else "failed", endedAt=now_iso())
        write()
    threading.Thread(target=work, daemon=True).start()


def read_requests():
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    size = LOG.stat().st_size if LOG.exists() else 0
    off = st.get("logOffset", size)          # first run: ignore old lines
    if size < off:
        off = 0
    if size > off:
        with open(LOG) as f:
            f.seek(off)
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] in ("WT_NEW", "WT_RM"):
                    start_job("new" if parts[0] == "WT_NEW" else "rm", parts[1])
    st["logOffset"] = size
    STATE.write_text(json.dumps(st))


# ---- output ----------------------------------------------------------------
LAST = {"rows": []}


def write(rows=None):
    rows = rows if rows is not None else LAST["rows"]
    comp = sorted(p for s in SESSIONS.values() for p in s.pre_tokens)
    data = {
        "at": now_iso(), "main": str(MAIN),
        "window": int(C["contextWindow"]), "warn": int(C["contextWarnTokens"]), "stop": int(C["contextStopTokens"]),
        "compactedAt": {"count": len(comp), "min": comp[0] if comp else None,
                        "median": comp[len(comp) // 2] if comp else None},
        "newCommand": " ".join(job_cmd("new", "<ticket>")),
        "worktrees": rows, "jobs": list(JOBS),
    }
    OUT.parent.mkdir(exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(OUT)


def one_pass():
    read_requests()
    rows = worktrees()
    attach(rows, scan_sessions())
    LAST["rows"] = rows
    write(rows)


if __name__ == "__main__":
    if not (MAIN / ".git").exists():
        sys.exit(f"worktreeMain is not a git checkout: {MAIN} (set it in config.json)")
    import fcntl
    OUT.parent.mkdir(exist_ok=True)
    _lock = open(HERE / "data" / "host.lock", "w")
    try:
        fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)   # only one host agent at a time
    except OSError:
        sys.exit("another ta-host.py is already running (./ta.sh status)")
    interval = int(C["hostIntervalSeconds"])
    print(f"Ticket Arena host agent: {MAIN} · sessions in {PROJECTS} · every {interval}s", flush=True)
    while True:
        t0 = time.time()
        try:
            one_pass()
        except Exception as e:  # noqa: BLE001
            print("pass failed:", e, flush=True)
        if "--once" in sys.argv:
            print(f"wrote {OUT} in {time.time() - t0:.1f}s")
            break
        time.sleep(max(1, interval - (time.time() - t0)))
