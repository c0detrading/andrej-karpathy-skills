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
uvicorn station.app:app --port 8000
```

Or double-click **`Start ONYX.bat`** (Windows) or **`Start ONYX.command`**
(Mac), which installs requirements, starts the server and opens the browser. For a desktop
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

**Overall daily bias**: 60% technical (a weighted average of the timeframes: 1D 30, 4h 25,
1h 20, 15m 12, 5m 8, 1m 5), 25% news, 15% macro.

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
out after 6 hours.

## What each card shows

- **Hit rate per timeframe**: the bias is replayed over the last ~1000 bars and checked against
  the price a few bars later (1m: 15 bars, 5m: 12, 15m: 16, 1h: 8, 4h: 6, 1D: 1). Around 50% means
  that timeframe's bias has no edge on its own. Use this to decide how much to trust it.
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

Settings, including the Telegram token and API key, are stored in `data/settings.json` on your
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

## Limitations

- **Delayed prices.** Yahoo Finance data is free but not tick-accurate: CME/COMEX futures quotes
  can be delayed (typically ~10 min). Fine for a daily bias, not for scalping entries.
  `station/market.py` is the only place to change if you move to a broker feed.
- **Forex Factory** blocks automated access to its news pages, so the station uses its
  calendar feed. That feed has no "actual" values, so data surprises come from FinancialJuice's
  release headlines instead.
- **Rule-based news scoring** (the default, when Claude scoring is off) can't read nuance. Sarcasm, "hopes fade" style phrasing, and
  headlines that mention several events can be scored wrongly. Each news item shows the
  rule tags it matched so you can see why.
- The last, still-forming bar is included in scoring (as on TradingView), so intraday biases
  move with price.

This is a decision-support tool, not financial advice.
