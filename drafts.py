#!/usr/bin/env python3
"""Review drafts for teammates' PRs, kept in data/drafts.json (one entry per PR).

  drafts.py set <pr> <file.json>     store a finished draft: {"summary": str, "headSha": str,
                                     "comments": [{"path", "line", "body", "severity"}]}
  drafts.py status <pr> <status>     drafting | ready | posted | discarded | failed
  drafts.py get <pr>                 print one draft
Every change marks "drafts" as pending upload for the claude.ai dashboard.
"""
import json, sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILE = HERE / "data" / "drafts.json"
STATE = HERE / "data" / "state.json"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load():
    return json.loads(FILE.read_text()) if FILE.exists() else []


def save(rows):
    FILE.write_text(json.dumps(rows, ensure_ascii=False))
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    st["pending"] = sorted(set(st.get("pending", [])) | {"drafts"})
    STATE.write_text(json.dumps(st))


def find(rows, pr):
    for r in rows:
        if str(r["pr"]) == str(pr):
            return r
    r = {"pr": int(pr), "status": "none", "comments": [], "summary": "", "headSha": "", "at": now()}
    rows.append(r)
    return r


def set_status(pr, status, **extra):
    rows = load()
    r = find(rows, pr)
    r.update(status=status, at=now(), **extra)
    save(rows)
    return r


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, pr = sys.argv[1], sys.argv[2]
    if cmd == "set":
        d = json.loads(Path(sys.argv[3]).read_text())
        comments = [dict(i=i, path=c["path"], line=int(c["line"]), body=c["body"].strip(),
                         severity=c.get("severity", "suggestion")) for i, c in enumerate(d.get("comments", []))]
        r = set_status(pr, "ready", summary=d.get("summary", "").strip(), headSha=d.get("headSha", ""), comments=comments)
        print(f"ready: #{pr} with {len(comments)} comments")
    elif cmd == "status":
        set_status(pr, sys.argv[3])
        print(f"#{pr} -> {sys.argv[3]}")
    elif cmd == "get":
        print(json.dumps(find(load(), pr), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
