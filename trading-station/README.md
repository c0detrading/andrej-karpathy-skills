# Trading Station — Gold & Nasdaq daily bias

A local web dashboard that gives a **BULLISH / BEARISH** bias for gold (`GC=F`) and the
Nasdaq 100 (`NQ=F`) on six timeframes, combines them into an overall daily bias, adjusts it
with live news, and pops up a browser notification when the bias changes.

- **Left panel:** bias per symbol for 1m, 5m, 15m, 1h, 4h and 1D, the indicator readings behind
  each one, and the headlines currently pushing the bias.
- **Right panel:** Forex Factory economic calendar (USD, high/medium impact), a live news feed
  from FinancialJuice and Yahoo Finance with each headline's gold/Nasdaq impact, and an alert log.

## Run

```bash
cd trading-station
pip install -r requirements.txt
uvicorn station.app:app --port 8000
```

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
bins starting at 18:00 New York time (the CME session open).

**Overall daily bias**: a weighted average of the timeframes (1D 30, 4h 25, 1h 20, 15m 12, 5m 8,
1m 5), blended 70/30 with the news score.

**News score** (`station/sentiment.py`): every headline is scored by keyword rules, for example:
hawkish Fed / hot inflation / rising yields / strong dollar → both bearish; dovish / cooling
inflation → both bullish; war, missiles, sanctions → gold up, Nasdaq down; ceasefire or
de-escalation → the reverse. A negator in the same clause flips a rule ("rejects ceasefire",
"denies plans for military action"). Rate-policy rules are skipped for non-US central banks.
FinancialJuice data releases (`US CPI Actual 0.4% (Forecast 0.3%, …)`) are scored by their
surprise against forecast. Each headline's impact fades with a 90-minute half-life and drops
out after 6 hours.

## Notifications

- Overall daily bias flips. The alert says when the flip came from news rather than
  technicals, and names the headline.
- 15m, 1h, 4h and 1D bias flips (1m/5m flip too often to be useful).
- New headlines with an impact of 2 or more on either symbol.
- High-impact USD calendar events 15 minutes before release. A banner shows while one is within 30 minutes.

All thresholds and weights are in `station/config.py`.

## Limitations

- **Delayed prices.** Yahoo Finance data is free but not tick-accurate: CME/COMEX futures quotes
  can be delayed (typically ~10 min). Fine for a daily bias, not for scalping entries.
  `station/market.py` is the only place to change if you move to a broker feed.
- **Forex Factory** blocks automated access to its news pages, so the station uses its
  calendar feed. That feed has no "actual" values, so data surprises come from FinancialJuice's
  release headlines instead.
- **Rule-based news scoring** can't read nuance. Sarcasm, "hopes fade" style phrasing, and
  headlines that mention several events can be scored wrongly. Each news item shows the
  rule tags it matched so you can see why.
- The last, still-forming bar is included in scoring (as on TradingView), so intraday biases
  move with price.

This is a decision-support tool, not financial advice.
