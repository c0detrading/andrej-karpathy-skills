# NQ Daily Bias S/R Strategy (TradingView backtest)

Pine Script v5 strategy for backtesting NQ (Nasdaq-100 futures) on TradingView.
Paste `nq_daily_bias_strategy.pine` into the Pine Editor, click **Add to chart**,
and run it on an NQ intraday chart (5m or 15m recommended).

## Rule mapping

| Rule | Implementation |
|------|----------------|
| 1. Daily bias | Bullish → longs only, bearish → shorts only. Default mode requires the previous daily candle to be bullish **and** price above today's daily open (selectable via *Daily bias mode*). |
| 2. Key levels only | Entries are allowed **only** when the signal candle tests one of: previous day high/low, previous week high/low, or today's daily open (within *Level proximity*, default 15 pts) and closes back through it in the trade direction. No level, no trade. |
| 3. Risk | 10 pt stop. TP1 at +50 pts (1:5) closes 50%; TP2 at +70 pts (1:7) closes the remaining 50%. Default size is 2 contracts so the partials split evenly. |
| 4. Confirmation on close | Signals are evaluated only on completed candles: the confirmation candle must close in the trade direction and beyond the tested level. Entry fills on the next bar open. |
| 5. Confluences | EMA20 filter (long above / short below) and a recent same-direction Fair Value Gap (3-candle imbalance within the lookback window). Both toggleable in settings. |

## Notes and caveats

- **Fills**: entries fill at the next bar's open after the confirmation close, so the
  realized entry can differ slightly from the confirmation close. Stops/targets are
  anchored to the actual average entry price, so the 1:5 / 1:7 geometry is preserved.
- **Stop stays at entry risk** for the runner after TP1 — no break-even move, per the
  stated rules. Add one later if live results argue for it.
- **Non-repainting**: higher-timeframe levels use the previous *completed* day/week
  (`[1]` offset with lookahead), so backtest signals match what you would have seen live.
- **Point values**: NQ is $20/pt; TradingView applies this automatically on NQ symbols.
  On MNQ ($2/pt) the point-based logic works unchanged.
- This is the offline backtest model only; live-data reinforcement of entries and
  profit-taking is a separate, later layer.
