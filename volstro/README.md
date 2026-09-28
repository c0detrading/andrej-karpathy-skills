# Volstro Pipeline: clients, prospects and a daily social media report

A local web app for Volstro Design with two views:

- **Pipeline**: every client and prospect on one board, by stage (Lead → Contacted → Proposal sent →
  Negotiation → Current client, plus Lost). Each card shows the client's value, the next step (red when
  overdue), follower counts per platform and, for current clients, any concerns. The tiles on top total the
  current clients and potential clients (monthly and one-off values). Drag a card to change its stage, or
  click it to edit the client, add social accounts or type in numbers.
- **Daily report**: every current client with their Instagram, Facebook and TikTok numbers (followers and
  their change over 1, 7 and 30 days, engagement against its 30-day average, posts in the last 7 days,
  last post) and a list of concerns to address, the most urgent clients first. A new report is saved every
  day and past reports stay available from the date picker.

## Run

```bash
cd volstro
pip install -r requirements.txt
python -m pipeline
```

Or double-click **`Start Volstro.bat`** (Windows) or **`Start Volstro.command`** (Mac). It installs the
requirements, starts the app and opens <http://localhost:8100>. The app uses port 8100, so it can run
alongside ONYX (port 8000). Run the tests with `python -m pytest`.

## Where the numbers come from

| Platform | How | What you need |
|---|---|---|
| Instagram | Fetched daily from Meta (Business Discovery) | One Meta token. Works for any **business or creator** account, including prospects, with nothing needed from them |
| Facebook | Fetched daily from Meta | The same token, with access to the client's Page (the client adds Volstro as a partner on their Page) |
| TikTok | Typed in (client → **Enter numbers**) or imported from a CSV (Settings) | TikTok has no open API for other accounts' stats |

Settings has step-by-step instructions for creating the Meta token (about 15 minutes, once) and a
**Check connection** button. Any account can also have its numbers typed in, for example while the Meta
connection isn't set up yet.

For each account the app stores one set of numbers per day: followers, posts in the last 7 days, and
average likes and comments over the latest 12 posts. Posts less than a day old are left out of the averages
because they are still collecting likes. **Engagement** = (average likes + average comments) ÷ followers.

## Concerns in the daily report

| Concern | Medium | High |
|---|---|---|
| Followers lost over 7 days (and at least 10 followers) | 1% | 3% |
| Days since the last post | 7 | 14 |
| Engagement below its 30-day average (needs 7 days of history) | 30% | 50% |
| Numbers not updated (Instagram/Facebook: 2 days, TikTok: 8 days) | ✓ | |
| Meta couldn't fetch the account (the error is shown) | | ✓ |
| The client's next step is overdue | ✓ | |

All thresholds are in `pipeline/config.py`.

The report is made every day at the time set in Settings (08:00 by default). If the app isn't running then,
it is made as soon as the app starts. **Refresh numbers now** fetches everything again and rebuilds today's
report.

## Your data

Clients, numbers and reports are stored in `data/volstro.db` (SQLite) and settings, including the Meta token,
in `data/settings.json`. The `data/` folder stays on your computer and is never uploaded to GitHub. Back it
up if the pipeline matters to you.

## Hosting it online for the team (optional)

Run it on a small cloud server (any Linux VPS) behind a web server that provides HTTPS, for example
[Caddy](https://caddyserver.com) with a `Caddyfile` of `pipeline.example.com { reverse_proxy 127.0.0.1:8100 }`:

```bash
cd volstro
VOLSTRO_PASSWORD='a long random password' VOLSTRO_ALLOWED_HOSTS=pipeline.example.com python -m pipeline
```

The app refuses to listen on a network address (`VOLSTRO_HOST=0.0.0.0`) unless `VOLSTRO_PASSWORD` is set.
With a password, every page asks you to log in, and a login lasts 30 days. Everyone shares one password.
There are no separate user accounts.

## Limitations

- **Not tested against a live Meta account.** The Instagram and Facebook requests follow Meta's Graph API
  v26.0 documentation and are covered by tests with recorded responses, but the first real run may show a
  Meta error on some accounts. The error is shown on the account and in the report.
- Instagram Business Discovery only sees **business and creator** accounts, and returns nothing for
  age-restricted ones. When an account hides its like counts, engagement is left blank.
- Facebook numbers need Volstro to have access to the Page. Without it, Meta returns a permissions error.
- TikTok numbers are only as fresh as the last time someone typed them in or imported them.
- No comment or sentiment tracking: the report works from counts, not from what people write.
