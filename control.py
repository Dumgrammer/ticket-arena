#!/usr/bin/env python3
"""Ticket Arena control server: lets the dashboard's buttons run follow-up commands.

Listens on 127.0.0.1:8765 only (your own machine). Every request needs the secret token
from control-token (created on first start), so other web pages can't press the buttons for you.

  /start  /stop  /status  /skip?pr=N  /unskip?pr=N  /post?pr=N   (all with &t=<token>)

Usually run by Docker (see SETUP.md). Without Docker:  TA_AUTO_REFRESH=1 python3 control.py
"""
import html, json, os, re, secrets, subprocess, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import followup  # noqa: E402
import drafts  # noqa: E402
import config  # noqa: E402

REPO = config.get("repo")


def post_review(pr, skip):
    """Post the ready draft for a PR to GitHub as a COMMENT review from you. Returns (ok, message)."""
    d = drafts.find(drafts.load(), pr)
    if d.get("status") != "ready":
        return False, f"PR #{pr} has no ready draft (status: {d.get('status', 'none')})."
    keep = [c for c in d["comments"] if c["i"] not in skip]
    if not keep and not d.get("summary"):
        return False, "Nothing left to post: every comment was unticked."
    payload = {"event": "COMMENT", "body": d.get("summary", ""),
               "comments": [{"path": c["path"], "line": c["line"], "side": "RIGHT", "body": c["body"]} for c in keep]}
    if d.get("headSha"):
        payload["commit_id"] = d["headSha"]
    r = subprocess.run(["gh", "api", "-X", "POST", f"repos/{REPO}/pulls/{pr}/reviews", "--input", "-"],
                       input=json.dumps(payload), capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stdout or r.stderr).strip()[-300:]
        return False, f"GitHub refused the review: {err}"
    drafts.set_status(pr, "posted", posted=len(keep))
    return True, f"Posted {len(keep)} comment(s) on PR #{pr} as a review from you."

PORT = int(os.environ.get("TA_PORT", "8765"))
BIND = os.environ.get("TA_BIND", "127.0.0.1")          # 0.0.0.0 inside Docker
AUTO_REFRESH = os.environ.get("TA_AUTO_REFRESH") == "1"  # run refresh.py every 15 min by itself
REFRESH_LOCK = threading.Lock()


def run_refresh():
    """Run refresh.py once (also posts due follow-ups). Returns its output lines."""
    with REFRESH_LOCK:
        r = subprocess.run([sys.executable, str(HERE / "refresh.py")], capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "unknown error").strip()[-300:])
    out = (r.stdout or "").strip().splitlines()
    if config.get("notifyClaude") and out and out[-1].startswith("CHANGED"):
        # tells the Claude session (if open) to upload to the claude.ai copy too
        with open(HERE / "requests.log", "a") as f:
            f.write(f"REFRESH {datetime.now().isoformat(timespec='seconds')} {' '.join(out)}\n")
    return out


def auto_refresh_loop():
    while True:
        try:
            run_refresh()
        except Exception as e:  # noqa: BLE001
            print("auto refresh failed:", e, flush=True)
        time.sleep(int(config.get("refreshMinutes")) * 60)


def local_page():
    """index.html wrapped as a standalone page, each inline script in its own scope like on claude.ai."""
    body = (HERE / "index.html").read_text()
    cfg = page_config()
    body = re.sub(r"<script>", "<script>(() => {", body)
    body = re.sub(r"</script>", "\n})();</script>", body)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Ticket Arena</title>
<style>html,body{{margin:0;background:#0c0a17}}</style>
<script>window.TA_LOCAL = true; window.TA_CONFIG = {cfg};</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script src="/ta-local.js"></script>
</head><body><div id="dash-root">{body}</div></body></html>"""


def page_config():
    # the page is only served to this PC, so it may carry the control key
    return json.dumps(config.for_page(TOKEN)).replace("</", "<\\/")
TOKEN_FILE = HERE / "control-token"
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(18))
    TOKEN_FILE.chmod(0o600)
TOKEN = TOKEN_FILE.read_text().strip()

PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Ticket Arena · {title}</title>
<style>
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0c0a17;color:#f5f2ff;
font:16px 'Segoe UI',system-ui,sans-serif}}
.c{{padding:28px 32px;border-top:4px solid {color};background:#161229;max-width:560px;margin:16px}}
h1{{font:italic 900 40px Impact,'Arial Narrow Bold',sans-serif;text-transform:uppercase;margin:0 0 10px;color:{color}}}
p{{margin:6px 0;color:#a8a1c9}} b{{color:#f5f2ff}}
</style>
<div class="c"><h1>{title}</h1><p>{msg}</p><p><b>{status}</b></p>
<p>You can close this tab.</p></div>
<script>setTimeout(function(){{window.close()}},4000)</script>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_raw(self, code, ctype, data):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def reply(self, code, title, msg, color="#77f56a"):
        if getattr(self, "want_json", False):
            return self.send_raw(code, "application/json", json.dumps(
                {"ok": code < 400, "title": title, "msg": msg, "status": followup.status_line()}).encode())
        body = PAGE.format(title=html.escape(title), msg=html.escape(msg), color=color,
                           status=html.escape(followup.status_line())).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        self.want_json = q.get("fmt") == "json"
        # the dashboard itself and its data (read-only, no key needed; only reachable from this PC)
        if u.path in ("/", "/index.html"):
            return self.send_raw(200, "text/html; charset=utf-8", local_page().encode())
        if u.path == "/ta-local.js":
            return self.send_raw(200, "text/javascript; charset=utf-8", (HERE / "ta-local.js").read_bytes())
        if u.path in ("/data/tickets.json", "/data/comments.json", "/data/team.json", "/data/drafts.json", "/data/worktrees.json"):
            f = HERE / u.path.lstrip("/")
            return self.send_raw(200, "application/json", f.read_bytes() if f.exists() else b"[]")
        if not secrets.compare_digest(q.get("t", ""), TOKEN):
            return self.reply(403, "Not allowed", "This link is missing the dashboard's control key.", "#ff5a4e")
        action = u.path.strip("/")
        pr = q.get("pr", "")
        d = followup.load_settings()
        if action in ("start", "stop"):
            d["enabled"] = action == "start"
            followup.save_settings(d)
            return self.reply(200, "Follow-ups on" if d["enabled"] else "Follow-ups off",
                              "Each open PR gets a Google Chat follow-up at the next refresh, then on the timer."
                              if d["enabled"] else "No more follow-ups will be posted until you start them again.",
                              "#77f56a" if d["enabled"] else "#a8a1c9")
        if action in ("skip", "unskip") and pr.isdigit():
            skip = [str(x) for x in d["skip"] if str(x) != pr]
            if action == "skip":
                skip.append(pr)
            d["skip"] = skip
            followup.save_settings(d)
            return self.reply(200, f"PR #{pr} {'skipped' if action == 'skip' else 'back on'}",
                              f"PR #{pr} will {'not ' if action == 'skip' else ''}get follow-ups.", "#ffe03d")
        if action == "post" and pr.isdigit():
            line = followup.follow_one(pr)
            if line.startswith("POSTED"):
                d = followup.load_settings()
                from datetime import datetime, timezone
                d["lastPosted"][pr] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                followup.save_settings(d)
                return self.reply(200, f"Posted #{pr}", "The follow-up was sent to Google Chat.")
            if line.startswith("MERGED"):
                return self.reply(200, f"#{pr} is merged", "Nothing to follow up.", "#33dcff")
            return self.reply(500, "Not posted", line, "#ff5a4e")
        if action == "refresh":
            try:
                out = run_refresh()
            except Exception as e:  # noqa: BLE001
                return self.reply(500, "Refresh failed", str(e), "#ff5a4e")
            last = out[-1] if out else "UNCHANGED"
            posted = [l for l in out if l.startswith("FOLLOWUP POSTED")]
            stuck = [l.split()[1] for l in out if l.startswith("NEW_STUCK")]
            extra = (f" Posted {len(posted)} follow-up(s)." if posted else "") + (f" Newly stuck: {', '.join(stuck)}." if stuck else "")
            if self.want_json:
                return self.reply(200, "Refreshed", "Fresh data from GitHub." + extra, "#33dcff")
            if last.startswith("CHANGED"):
                return self.reply(200, "Refreshing",
                                  f"New data from GitHub ({last.split(' ', 1)[1]}). The dashboard updates in about a minute." + extra, "#ffe03d")
            return self.reply(200, "Up to date", "Checked GitHub just now: nothing changed since the dashboard's last update." + extra, "#33dcff")
        if action == "draft" and pr.isdigit():
            drafts.set_status(pr, "drafting")
            with open(HERE / "requests.log", "a") as f:
                f.write(f"DRAFT {pr}\n")
            return self.reply(200, f"Drafting #{pr}",
                              "Queued. A Claude Code session watching requests.log drafts it (see DRAFTING.md); "
                              "the draft shows on the dashboard when it is done.", "#ffe03d")
        if action == "post-review" and pr.isdigit():
            skip = {int(x) for x in q.get("skip", "").split(",") if x.strip().isdigit()}
            ok, msg = post_review(pr, skip)
            return self.reply(200 if ok else 500, "Review posted" if ok else "Not posted", msg,
                              "#77f56a" if ok else "#ff5a4e")
        if action == "discard-draft" and pr.isdigit():
            drafts.set_status(pr, "discarded")
            return self.reply(200, f"Draft for #{pr} discarded", "Nothing was posted.", "#a8a1c9")
        if action in ("wt-new", "wt-rm"):
            t = q.get("ticket", "").strip().upper()
            if not re.fullmatch(r"(?:[A-Z]+-)?\d{2,7}", t):
                return self.reply(400, "Not queued", "Give a ticket like 1234 or PROJ-1234.", "#ff5a4e")
            with open(HERE / "requests.log", "a") as f:
                f.write(f"{'WT_NEW' if action == 'wt-new' else 'WT_RM'} {t}\n")
            host = HERE / "data" / "worktrees.json"
            alive = host.exists() and time.time() - host.stat().st_mtime < 120
            msg = ("The host agent is creating it now; progress shows in the Worktrees section." if action == "wt-new"
                   else "The host agent is removing it (refused if it has uncommitted changes; the branch is kept).")
            if not alive:
                msg = "Queued, but the host agent isn't running: start it with python3 ta-host.py (see SETUP.md)."
            return self.reply(200 if alive else 503, f"Worktree {t}", msg, "#ffe03d" if alive else "#ff5a4e")
        if action == "status":
            return self.reply(200, "Status", "Current follow-up settings:", "#33dcff")
        return self.reply(404, "Unknown button", f"No action called '{action}'.", "#ff5a4e")


if __name__ == "__main__":
    if AUTO_REFRESH:
        threading.Thread(target=auto_refresh_loop, daemon=True).start()
    print(f"Ticket Arena on http://localhost:{PORT} (auto refresh {'on' if AUTO_REFRESH else 'off'})", flush=True)
    ThreadingHTTPServer((BIND, PORT), H).serve_forever()
