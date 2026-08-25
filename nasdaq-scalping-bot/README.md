# Nasdaq Ultra-Scalping Bot (MetaTrader 5)

An Expert Advisor (EA) for MetaTrader 5 that scalps the Nasdaq 100 index with
fixed exits:

- **Take profit: +5.0 index points**
- **Stop loss: −2.5 index points**

It opens at most one position at a time and evaluates entries once per bar.

## Assumptions made

You specified the exits but not the platform or the entry rule, so this
implementation assumes:

1. **Platform: MetaTrader 5** (MQL5 EA). This is the most common retail setup
   for trading the Nasdaq index as a CFD (symbol usually named `US100`,
   `NAS100` or `USTEC`). It also works on brokers offering NQ/MNQ futures
   symbols in MT5.
2. **Entry rule: 9/21 EMA crossover on the chart timeframe (M1 recommended).**
   A fast EMA crossing above the slow EMA opens a buy; crossing below opens a
   sell. The entry logic is isolated in one function (`GetSignal()` in
   `NasdaqScalper.mq5`) so you can swap in your own signal without touching
   the 5.0 / 2.5 point exit handling.
3. **"Points" means index points** (e.g. Nasdaq moving from 23500.00 to
   23505.00 is 5 points). On US100-style symbols 1 index point equals 1.0 of
   quoted price, which is how the EA applies it. This is *not* the same as
   MQL5's `_Point` (often 0.01 or 0.1 depending on the broker's digits).

If you wanted a different platform (Interactive Brokers, NinjaTrader,
Tradovate, a Python/broker-API bot) or a different entry rule, say so and it
can be ported — the exit spec carries over unchanged.

## Installation

1. Open MetaTrader 5 → `File` → `Open Data Folder`.
2. Copy `NasdaqScalper.mq5` into `MQL5/Experts/`.
3. In MetaEditor press **Compile** (or restart the terminal).
4. Open an **M1 chart** of your Nasdaq symbol (`US100` / `NAS100` / `USTEC`).
5. Drag `NasdaqScalper` onto the chart, enable **Algo Trading**, and confirm.

**Backtest first:** use the built-in Strategy Tester (`View` → `Strategy
Tester`) with "Every tick based on real ticks" modeling before running on any
live or demo account. With a 2.5-point stop, tick-level modeling matters.

## Parameters

| Input | Default | Meaning |
|---|---|---|
| `InpTakeProfitPts` | `5.0` | Take profit in index points |
| `InpStopLossPts` | `2.5` | Stop loss in index points |
| `InpLots` | `0.1` | Position size in lots |
| `InpFastEMA` / `InpSlowEMA` | `9` / `21` | Entry crossover periods |
| `InpMaxSpreadPts` | `1.5` | Skip entries when spread exceeds this (0 = off) |
| `InpUseTimeFilter` | `true` | Restrict trading to set hours |
| `InpStartHour` / `InpEndHour` | `15` / `21` | Trading window, **server time** (defaults roughly cover the US cash session on GMT+2/+3 brokers — adjust to your broker) |
| `InpMagic` | `20260825` | Magic number identifying this EA's trades |

## Read this before going live

With TP 5 / SL 2.5 the risk:reward is 1:2, so ignoring costs you break even
at a **33.3% win rate**. Costs dominate at this scale, though: with a typical
1.5-point US100 spread, a buy actually needs +6.5 points of bid movement to
hit TP and only −1.0 to hit SL — the breakeven win rate jumps to roughly
**57%**, before commission and slippage. Concretely:

- Trade this only on an account with **tight spreads** (well under 1 point if
  possible) and keep `InpMaxSpreadPts` strict.
- The default EMA-crossover entry is a placeholder demonstrating the
  execution machinery, **not** a proven edge. Backtest and forward-test on a
  demo account; expect to replace `GetSignal()` with your own logic.
- Some brokers enforce a minimum stop distance larger than 2.5 points
  (`SYMBOL_TRADE_STOPS_LEVEL`); the EA logs a warning at startup if yours
  does, and such orders will be rejected rather than silently widened.
- Nothing here is financial advice. Automated scalping of leveraged index
  products can lose money quickly; use money you can afford to lose.
