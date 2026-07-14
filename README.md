# internship-search

Scrapes internship listings from public GitHub job-board repos, remembers which ones it has
already seen, and pushes a phone notification when new ones show up.

Sources (both read as raw Markdown, so they don't break when GitHub restyles its HTML):

- [vanshb03/Summer2027-Internships](https://github.com/vanshb03/Summer2027-Internships)
- [speedyapply/2027-SWE-College-Jobs](https://github.com/speedyapply/2027-SWE-College-Jobs)

## Setup

```sh
uv sync                 # or: pip install -r requirements.txt
cp .env.example .env
```

Then pick a topic name and put it in `.env` (see below).

## Notifications

Notifications go through [ntfy](https://ntfy.sh). A notification is just an HTTP POST to
`https://ntfy.sh/<topic>`; every phone subscribed to that topic gets the message. There are no
accounts, no pairing, and no per-device setup.

### 1. Choose an unguessable topic

**The topic name is the only thing keeping your feed private.** Topics on the public server are
readable — and writable — by anyone who knows the name, so `internships` or `stephen-jobs` is
effectively public. Generate a random one:

```sh
openssl rand -hex 16
```

Put it in `.env`:

```sh
NTFY_TOPIC="a1b2c3d4e5f6...."
```

Anyone with the topic name can read the feed, but that's fine: listings are scraped from public
GitHub READMEs, so **the notification includes full details** (company, role, location, apply
link) — one push per new listing, so tapping it opens the apply link directly. A cold-start run
with a lot of new listings sends one summary notification instead, so you don't get buzzed dozens
of times at once.

### 2. Subscribe on the phone

Do this on **each** phone that should get the alerts. Everyone uses the *same* topic string — that
is the entire mechanism by which one message reaches several devices.

1. Install **ntfy** — [Android (Play Store)](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   or [F-Droid](https://f-droid.org/en/packages/io.heckel.ntfy/), or
   [iOS (App Store)](https://apps.apple.com/us/app/ntfy/id1625396347).
2. Open it and tap the **+** button.
3. Type the topic name **exactly** as in `.env` (it's case-sensitive; copy-paste it) and tap
   *Subscribe*. Leave "Use another server" off unless you're self-hosting (see below).
4. Test it: `curl -d "hello" https://ntfy.sh/<your-topic>` — the phone should buzz within a second
   or two.

Adding another person later is just steps 1–3 with the same topic. Send them the topic string over
something private, since it *is* the secret.

### 3. Self-hosting and auth (optional)

Both are opt-in and need no code change:

```sh
NTFY_SERVER="https://ntfy.example.com"   # your own instance; defaults to https://ntfy.sh
NTFY_TOKEN="tk_..."                      # sent as: Authorization: Bearer <token>
```

`NTFY_TOKEN` is what you need for a protected/reserved topic on ntfy.sh or an authenticated
self-hosted server, and it's the only way to stop *strangers* posting to your topic.

Sends are HTTPS-only. A `NTFY_SERVER` starting with `http://` is refused, so a typo can't put your
topic and token on the wire in cleartext. Override with `NTFY_ALLOW_INSECURE=1` only for a trusted
server on your own network.

## Phone approval

Each listing's notification carries two buttons, "Hank interested" and "Steve interested". Tapping
one writes `planning to apply` straight into that person's column (F and E respectively) on the
tracker sheet — no need to open the sheet at all. This is optional; without it, notifications work
exactly as described above, just without the buttons.

ntfy can't call back into a machine on your desk to make this happen, so the buttons POST to a tiny
Google Apps Script Web App bound to the sheet instead — free, hosted by Google, nothing to run or
maintain.

1. Open the tracker sheet, then **Extensions → Apps Script**.
2. Delete the placeholder code and paste in [`appscript/Code.gs`](appscript/Code.gs) (already
   set to your tab name, "Internship & Job Tracker" — update `SHEET_NAME` if you ever rename it).
3. **Deploy → New deployment → Web app**. Set "Execute as" to **Me** and "Who has access" to
   **Anyone** (this is what lets ntfy's server reach it — the deployment URL itself is the only
   thing standing in for auth, similar to the ntfy topic).
4. Copy the deployment URL into `.env`:
   ```sh
   APPROVAL_WEBHOOK_URL="https://script.google.com/macros/s/XXXXXXXX/exec"
   ```
5. Make sure `planning to apply` is one of the allowed options in both E's and F's dropdown
   validation, or Sheets will flag the cell even though the value was written correctly.

Redeploying after editing the script requires **Deploy → Manage deployments → Edit → New
version** — saving in the editor alone doesn't update the live URL.

If you ever want to stop randoms who find the URL from writing to your sheet, set `SECRET` in
`Code.gs` to some random string and put the same value in `APPROVAL_WEBHOOK_SECRET` in `.env`.

## Running

```sh
uv run main.py
```

Prints any listings it hasn't seen before, records them in `seen_urls.txt`, and sends one
notification per new listing (or a single summary notification if there are a lot at once — see
`NOTIFY_BATCH_LIMIT` in `main.py`). A listing is identified by its apply URL, so it's announced
exactly once. Run it again straight away and you'll get `0 new` and no notification.

A first run on a fresh machine (no `seen_urls.txt`) treats every listing as new, so expect a single
"189 new internship listings — too many to list individually" summary notification, and then
quiet.

### Cron

Cron doesn't read your shell profile and starts in `$HOME`, so `cd` into the project first — the
`.env` and `seen_urls.txt` paths are relative to it. Use an absolute path for the binary
(`which uv`).

```cron
# Check for new listings hourly, at :05
5 * * * * cd /home/splayford/internship-search && /usr/bin/uv run main.py >> tracker.log 2>&1
```

`main.py` exits non-zero if a source fails or a notification can't be delivered, so a cron `MAILTO`
or a log watcher will surface it.

## Layout

| File | Purpose |
|---|---|
| `main.py` | Entry point: scrape, diff against seen, print, notify. |
| `notify.py` | The single place that talks to ntfy. |
| `sheets.py` | Writes new listings to the tracker sheet. |
| `store.py` | Remembers seen listings (`seen_urls.txt`), keyed by apply URL. |
| `models.py` | The `Listing` record shared by every source. |
| `scrapers/` | One module per source, over a shared Markdown-table base. |
| `appscript/Code.gs` | Web App pasted into Apps Script; receives phone-approval button taps. |

Adding a source means writing one `Scraper` subclass in `scrapers/` and adding its URL to the
`SOURCES` map in `main.py`.
