# Screenshot shot list

The README and SETUP guide have a placeholder for every image below. Each is marked **SCREENSHOT TODO**.

**For each image:**
1. Save the image as `docs/images/<file name>`.
2. Delete the `> [!NOTE] ... SCREENSHOT TODO` block above it in the doc. The `![...]` line under it shows the image automatically.

To find what's still missing:

```bash
grep -rn "SCREENSHOT TODO" README.md SETUP.md
```

## General tips

- Use a browser window about **1300 px wide** at 100% zoom, so the dashboard isn't in its phone layout.
- Open each section from the navbar (the "Where" column names the page). Crop to the section and leave out the browser bar and tabs. For `01-overview.png`, keep the navbar in the shot.
- Save as PNG. Keep each file under about 500 KB, and compress at tinypng.com if needed.
- **Blur before saving**: webhook URLs, Google Chat user IDs, and anything from a customer or client. Teammates' names and PR titles are fine for an internal repo. If the repo will be public, blur those too.

## Shot list

| # | File | Where | Set up first | Must be visible |
|---|---|---|---|---|
| 1 | `01-overview.png` | Dashboard, top of page | Wait for a refresh so the counters have numbers | Header with repo and username, summary sentence, Refresh now button, all six counters |
| 2 | `02-stuck-tickets.png` | Danger zone | Needs at least one PR open longer than `stuckDays`. If you have none, temporarily set `"review": 0` in `config.json`, run `./ta.sh restart`, then set it back | At least one red alert card, with its days count and "since" text |
| 3 | `03-ticket-progress.png` | Round 1 | | Five or more rows at different stages (yellow review, cyan merged, green staging), plus the Show and Sort controls |
| 4 | `04-follow-ups.png` | Round 2, Follow-ups | Turn follow-ups ON | The ON switch, two or three PRs with Skip and Post now, and "last posted" times |
| 5 | `05-pr-comments.png` | Round 2, Comments | Set Show to "All" | Three to six cards with different severity tags, at least one "needs reply" |
| 6 | `06-team-prs.png` | Round 4 | | An "Asks you" badge, a pink "replied to you" badge, and a Draft review button |
| 7 | `07-review-draft.png` | Round 4, Review drafts | Needs a ready draft (see SETUP step 8). Skip this image if you don't use drafts | The summary, two or three comment checkboxes (one unticked), and the Post and Discard buttons |
| 8 | `08-worktrees.png` | Round 5 | Type a ticket in the input box | The Create worktree bar with "Host agent live", the legend line, and two or three worktree cards |
| 9 | `09-context-meter.png` | Round 5, one card, zoomed in | Pick a card with a chat over 200K | The meter with its yellow and red marks and dotted line, the verdict ("Wrap up" or "Start a new chat"), and the resume command row |
| 10 | `10-combo-moves.png` | Round 3 | Fill in a ticket and a PR number | All six cards with real numbers in the commands |
| 11 | `11-ta-up-terminal.png` | Terminal | Run `./ta.sh up`, then `./ta.sh status` | "dashboard: http://localhost:8765", "container: Up ...", "host agent: active" |
| 12 | `12-gchat-webhook.png` | Google Chat, space, Apps & integrations, Webhooks | Add a webhook | The Webhooks dialog, with the **URL blurred** |
| 13 | `13-follow-up-in-chat.png` | Google Chat space | Post one with **Post now** | The message text, PR link and cc mentions |
| 14 | `14-chat-scrape-console.png` | chat.google.com, DevTools Console | Run `chat-scrape.js` | "Copied N people to the clipboard", with the **names and IDs blurred** |

## Optional: GIFs

Short GIFs (under 10 seconds) work well for:
- Pressing **Create worktree** and watching the job card go from running to done
- Ticking and unticking filters in a **Show** menu

Save them in `docs/images/` and add them the same way, e.g. `![Create worktree](docs/images/create-worktree.gif)`.
