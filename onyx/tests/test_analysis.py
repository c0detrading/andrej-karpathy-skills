from datetime import timedelta

import numpy as np
import pandas as pd

from station.analysis import alignment, key_levels, volatility
from station.livelog import grade


def test_alignment_reads():
    f = lambda **b: {tf: {"bias": v} for tf, v in b.items()}
    B, S = "BULLISH", "BEARISH"
    assert alignment(f(**{"1m": S, "5m": S, "15m": S, "1h": B, "4h": B, "1D": B})).startswith("Pullback in an uptrend")
    assert alignment(f(**{"1m": B, "5m": B, "15m": B, "1h": S, "4h": S, "1D": S})).startswith("Bounce in a downtrend")
    assert alignment(f(**{"1m": B, "5m": B, "15m": B, "1h": B, "4h": B, "1D": B})) == "All timeframes aligned bullish."


def test_key_levels_prev_day_weekly_open_overnight():
    daily = pd.DataFrame({"open": [1, 2], "high": [110.0, 120], "low": [90.0, 95], "close": [100.0, 105]},
                         index=pd.date_range("2026-09-23", periods=2, freq="1D", tz="America/New_York"))
    # 15m bars from Sunday 18:00 (week open 50) through Tuesday
    idx = pd.date_range("2026-09-20 18:00", "2026-09-22 12:00", freq="15min", tz="America/New_York")
    intraday = pd.DataFrame({"open": 50.0, "high": 60.0, "low": 40.0, "close": 55.0}, index=idx)
    intraday.loc[intraday.index >= "2026-09-21 18:00", ["high", "low"]] = [104.0, 99.6]
    levels = {lv["name"]: lv for lv in key_levels(daily, intraday, 100.0, 2.0, cme=True)}
    assert levels["Prev day high"]["price"] == 110 and levels["Prev day close"]["testing"]
    assert levels["Weekly open"]["price"] == 50
    assert levels["Overnight high"]["price"] == 104 and levels["Overnight low"]["price"] == 99.6
    assert levels["Overnight low"]["testing"]  # within 0.25 * ATR 2.0 of price
    assert not levels["Prev day high"]["testing"]


def test_volatility_regime():
    n = 30
    idx = pd.date_range("2026-08-01", periods=n, freq="1D", tz="America/New_York")
    df = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=idx)
    df.iloc[-1, df.columns.get_indexer(["high", "low"])] = [100.2, 99.8]  # today: 0.4 of a 2.0 ATR
    v = volatility(df)
    assert v["regime"] == "quiet" and v["range_used_pct"] == 20


def test_live_record_grading():
    idx = pd.date_range("2026-09-21", periods=3, freq="1D", tz="America/New_York")
    daily = pd.DataFrame({"close": [110.0, 90.0, 100.0]}, index=idx)
    records = [
        {"date": "2026-09-21", "asset": "GOLD", "bias": "BULLISH", "price": 100.0},  # closed 110: hit
        {"date": "2026-09-22", "asset": "GOLD", "bias": "BULLISH", "price": 100.0},  # closed 90: miss
        {"date": "2026-09-23", "asset": "GOLD", "bias": "BEARISH", "price": 100.0},  # today: pending
        {"date": "2026-09-21", "asset": "NASDAQ", "bias": "BEARISH", "price": 1.0},
    ]
    g = grade(records, "GOLD", daily, today="2026-09-23")
    assert (g["days"], g["hits"], g["hit_rate"]) == (2, 1, 50.0)
