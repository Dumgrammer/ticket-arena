# Drafting a review for a teammate's PR

Optional. Triggered by a `DRAFT <pr>` line in `requests.log` (the dashboard's Draft review
button, or `AUTO_DRAFT` for PRs that request your review). A Claude Code session opened in this folder handles it: ask it to
watch `requests.log` for `DRAFT` lines and follow this file. Without that session, drafts stay "drafting".

Nothing here posts to GitHub. Posting happens only when you press Post on the dashboard
(control server `/post-review`).

1. Read the PR: `gh pr view <pr> -R <repo from config.json> --json title,body,headRefOid,files,author`
   and the diff: `gh pr diff <pr> -R <repo>`. For big diffs, read the files most likely
   to hide bugs first (logic, auth/permissions, data writes, migrations), skim generated files and lockfiles.
2. Write review comments only for real problems or clear improvements: correctness bugs, missing edge
   cases, security/permission gaps, broken tests, misleading names or docs. Skip style nits the linter
   would catch. 0-8 comments; zero is fine when the PR is clean.
3. Each comment targets a line that exists on the RIGHT side of the diff (an added or context line in a
   hunk), otherwise GitHub rejects the whole review. Use the new-file line number.
4. Tone: friendly teammate, direct, no emojis. Say what is wrong, why it matters, and a concrete fix.
   Severity is one of: blocking, issue, suggestion, question.
5. Summary: 1-3 sentences, what the PR does well and the main concern, if any.
6. Save as JSON `{"summary", "headSha", "comments": [{"path", "line", "body", "severity"}]}` in the
   scratchpad, then: `python3 drafts.py set <pr> <file>`.
   If the PR is closed/merged or unreadable: `python3 drafts.py status <pr> failed`.
7. The local dashboard picks the draft up on its next reload (within a minute).
