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

## Backtest findings (Python replication, NQ=F, June-Aug 2026)

Replicated bar-for-bar on 60 days of 15m data and 3 months of 1h data
(conservative fills: stop counts first when a bar touches both stop and target):

- Original spec (all hours, 15-pt proximity): ~11% win rate, profit factor 0.73-0.78 — losing.
  ~88% of entries stop out; a 10-pt stop is inside normal NQ intrabar noise.
- Restricting entries to 09:30-11:30 ET cut losses ~85% in every variant tested
  (now the default). Tightening proximity 15 -> 5 pts helped marginally (now default).
- No variant was profitable on 15m data (best: stop 25 / TP 125-175, PF 0.94).
  1h data showed PF 2.0+ with the session filter, but on only ~24 setups —
  too small and too coarse to trust.
- Conclusion: the 10-pt stop is the binding constraint.
- ATR-scaled stops (stop = k * ATR(14), targets 5x/7x the stop, session filter on)
  were the first profitable configuration on 15m data: k=1.5 -> PF 1.24, k=2.0 ->
  PF 1.38 (+10R over 60 days), confirmed directionally on 1h/3mo (PF 2.2-2.4).
  Now the default (ATR-scaled, mult 2.0). Caveat: only 16-20 setups in the
  sample, and the resulting stops are ~100-140 pts, far larger than the
  original 10-pt spec - risk per trade must be sized accordingly (e.g. MNQ).

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
