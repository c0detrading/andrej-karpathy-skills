# ONYX — Gold, Nasdaq & Bitcoin daily bias

A local web dashboard that gives a **BULLISH / BEARISH** bias for gold (`GC=F`), the
Nasdaq 100 (`NQ=F`) and Bitcoin (`BTC-USD`) on six timeframes, combines them into an overall daily bias, adjusts it
with live news, and pops up a browser notification when the bias changes.

- **Left panel:** bias per symbol for 1m, 5m, 15m, 1h, 4h and 1D, the indicator readings behind
  each one, and the headlines currently pushing the bias.
- **Right panel:** Forex Factory economic calendar (USD, high/medium impact), a live news feed
  from FinancialJuice and Yahoo Finance with each headline's gold/Nasdaq/Bitcoin impact, and an alert log.
  Every timestamp shows the full date and time in your computer's time zone, and the dot in
  front of each headline shows its relevance: grey = no effect, yellow → red = weak → strong.

## Run

```bash
cd onyx
pip install -r requirements.txt
python -m station
```

Or double-click **`Start ONYX.bat`** (Windows) or **`Start ONYX.command`**
(Mac), which installs requirements, starts the server and opens the browser (or just opens the
browser if ONYX is already running). For a desktop
shortcut: on Windows, right-click the `.bat` → *Send to* → *Desktop (create shortcut)*; on Mac,
right-click the `.command` → *Make Alias* and drag the alias to the Desktop.

Open <http://localhost:8000> and click **Enable alerts** to allow desktop notifications
(a short beep also plays for each alert). Run the tests with `python -m pytest`.

## How the bias is calculated

**Per timeframe** (`station/bias.py`): each indicator on the latest bar casts a vote from -1 to +1.
The votes are weighted and summed into a score from -100 to +100:

| Vote | Weight | Bullish when |
|---|---|---|
| Close vs EMA 20 / 50 / 100 / 200 | 5 / 5 / 5 / 10 | close above the EMA |
| EMA stack 20>50, 50>100, 100>200 | 5 / 5 / 10 | faster EMA above slower |
| RSI 14 | 15 | above 50 (scaled; 70+ is a full vote) |
| Bollinger %B (20, 2) | 15 | above the middle band (riding the upper band is a full vote) |
| MACD (12, 26, 9) | 15 | histogram > 0 (half) and MACD > 0 (half) |
| DMI 14 | 10 | +DI above −DI |

A bias only flips once the score passes ±10 (`BIAS_HYSTERESIS`), so it doesn't flicker around zero.
A timeframe needs 200 bars before it is scored. The 4h bars are built from 1h bars, with
bins starting at 18:00 New York time (the CME session open) for gold and Nasdaq, and at
00:00 UTC for Bitcoin, which trades 24/7.

**Overall daily bias**: 60% technical (a weighted average of the timeframes: 1D 32, 4h 25,
1h 20, 15m 13, 5m 10; 1m is shown for information but not counted, as it backtested as the
noisiest), 25% news, 15% macro.

**No clear bias**: a score within ±20 is shown greyed out as "no clear bias", with the direction
it leans. Alerts still fire on flips (the underlying bias is still bullish or bearish).

**Tuned models** (`station/bias.py` → `tune`): once a day ONYX tries five models on every asset
and timeframe: all indicators (default), EMAs only, momentum only (RSI/Bollinger/MACD/DMI), all
indicators only when trending (ADX ≥ 20), and contrarian (fade the indicators). The winner on the
older 70% of the price history is kept only if it also makes at least 0.01% per call on the
newest 30%, which it never saw, and beats the default there. Otherwise the default stays. Results
are in Settings → Tuned models, and you can switch tuning off there.

**Macro**: the US Dollar Index (`DX-Y.NYB`) and 10-year yield (`^TNX`) are scored with the same
indicators on 1h/4h/1D. Rising dollar and yields count against gold (fully) and against Nasdaq
and Bitcoin (half). When macro pushes strongly against an asset's bias, its card says so.

**News score** (`station/sentiment.py`): every headline is scored by keyword rules, for example:
hawkish Fed / hot inflation / rising yields / strong dollar → both bearish; dovish / cooling
inflation → both bullish; war, missiles, sanctions → gold up, Nasdaq down; ceasefire or
de-escalation → the reverse. Bitcoin follows risk sentiment on macro news
(hawkish or risk-off → bearish) and has its own rules for ETF flows, buying, hacks and regulation. A negator in the same clause flips a rule ("rejects ceasefire",
"denies plans for military action"). Rate-policy rules are skipped for non-US central banks.
FinancialJuice data releases (`US CPI Actual 0.4% (Forecast 0.3%, …)`) are scored by their
surprise against forecast. Each headline's impact fades with a 90-minute half-life and drops
out after 6 hours. Headlines from the same source and speaker in the same hour (FinancialJuice
posts a speech as 10-20 lines, "Fed's Hammack: …") count as one event, capped at the weight of
one strong headline.

## What each card shows

- **Hit rate and edge per timeframe**: the bias is replayed over the last ~1000 bars and checked
  against the price a few bars later (1m: 15 bars, 5m: 12, 15m: 16, 1h: 8, 4h: 6, 1D: 1).
  *Edge* is the average % move in the bias direction per call, which matters more than the hit
  rate: a 45% hit rate with bigger wins than losses still makes money. The indicator table also
  shows the hit rate for strong signals only (|score| ≥ 20). Around 50% / ~0% edge means that
  timeframe's bias has no edge on its own.
- **Live record**: every weekday between the New York open (09:30) and noon, each asset's
  overall bias is saved to `data/bias_log.jsonl` and graded against that day's close.
- **Plain-English read** of how the timeframes line up (for example "pullback in an uptrend"),
  plus volatility: how much of the daily ATR today's range has used (quiet / normal / active / wild).
- **Chart** of the selected timeframe (click a timeframe tile) with EMA 20/50/200 and Bollinger Bands.
- **Key levels**: previous day high/low/close, weekly open and (futures) overnight high/low,
  highlighted when price is within a quarter of the 1h ATR.

The right panel also has a **daily briefing** (sent at the time set in Settings, or on demand),
the calendar with each asset's **15-minute reaction** after high-impact releases, and news from
FinancialJuice, Yahoo Finance, the Federal Reserve (policy releases and speeches) and CoinDesk.

## Settings

Open **Settings** (top right) to:
- pick the assets (gold, Nasdaq, Bitcoin, silver, S&P 500, Dow, crude oil, EUR/USD, Ethereum)
  or add any Yahoo Finance ticker;
- connect **Telegram** so alerts reach your phone (step-by-step instructions on the page);
- turn on **Claude news scoring** with an Anthropic API key. Claude re-scores market-relevant
  headlines (at most 200 a day), catching nuance the keyword rules miss;
- set the **daily briefing** time.

- add an **OANDA** API token for **real-time prices** (a free practice account works). Assets
  OANDA carries switch to OANDA; the rest stay on Yahoo. Each card shows its price source;
- see and re-run the **tuned models**, or stop ONYX.

Settings, including the Telegram token and API keys, are stored in `data/settings.json` on your
computer. That folder is never uploaded to GitHub.

## Notifications

- Overall daily bias flips. The alert says when the flip came from news rather than
  technicals, and names the headline.
- 15m, 1h, 4h and 1D bias flips (1m/5m flip too often to be useful).
- New headlines with an impact of 2 or more on either symbol.
- High-impact USD calendar events 15 minutes before release. A banner shows while one is within 30 minutes.
- Each asset's move 15 minutes after a high-impact release.
- The daily briefing.

With Telegram set up, every alert is also sent to your chat.

All thresholds and weights are in `station/config.py`.

## Run in the background, start with your computer

- **Windows:** double-click `Autostart ON (Windows).bat`. ONYX then runs hidden and starts when
  you log in. `Autostart OFF (Windows).bat` undoes it.
- **Mac:** double-click `Autostart ON (Mac).command` (`Autostart OFF (Mac).command` undoes it).
  macOS blocks background apps from reading Documents, Desktop and Downloads, so keep the ONYX
  folder in your home folder for this.

Open ONYX any time at <http://localhost:8000> or with the Start ONYX shortcut. Logs go to
`data/onyx.log`. **Stop ONYX** is on the Settings page.

## Hosting it online (optional)

To use ONYX from your phone or any browser, run it on a small cloud server (any Linux VPS):

1. Install Python 3.11+ and git, clone this repository and `pip install -r onyx/requirements.txt`.
2. Run it with a password, behind a web server that provides HTTPS, for example
   [Caddy](https://caddyserver.com) with a `Caddyfile` of `onyx.example.com { reverse_proxy 127.0.0.1:8000 }`:
   ```bash
   cd onyx
   ONYX_PASSWORD='a long random password' ONYX_ALLOWED_HOSTS=onyx.example.com python -m station
   ```
   Use a process manager such as systemd to keep it running.

ONYX refuses to listen on a network address (`ONYX_HOST=0.0.0.0`) unless `ONYX_PASSWORD` is set.
With a password, every page asks you to log in; sessions last 30 days. Browser notifications
need HTTPS, which Caddy provides automatically.

## Limitations

- **Delayed prices** without OANDA. Yahoo Finance data is free but not tick-accurate: CME/COMEX
  futures quotes can be delayed (typically ~10 min). Add an OANDA token in Settings for real-time.
- **Small edges.** The backtested edges are hundredths of a percent per call, similar to trading
  costs, and they change as market regimes change. Treat the bias as a summary of what the market
  is doing, not as a forecast, and watch the live record.
- **Forex Factory** blocks automated access to its news pages, so the station uses its
  calendar feed. That feed has no "actual" values, so data surprises come from FinancialJuice's
  release headlines instead.
- **Rule-based news scoring** (the default, when Claude scoring is off) can't read nuance. Sarcasm, "hopes fade" style phrasing, and
  headlines that mention several events can be scored wrongly. Each news item shows the
  rule tags it matched so you can see why.
- The last, still-forming bar is included in scoring (as on TradingView), so intraday biases
  move with price.

This is a decision-support tool, not financial advice.
