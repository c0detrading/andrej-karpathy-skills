"""Context around the bias: key levels, volatility, timeframe alignment, event reactions."""

from datetime import datetime, timedelta

import pandas as pd

from . import indicators as ind
from .config import LEVEL_TEST_ATR

NY = "America/New_York"


def _week_key(index: pd.DatetimeIndex, cme: bool) -> pd.Index:
    """Monday date of each bar's trading week (CME weeks open Sunday 18:00 New York)."""
    t = index + pd.Timedelta(hours=6) if cme else index.tz_convert("UTC")
    days = t.normalize()
    return days - pd.to_timedelta(t.weekday, unit="D")


def key_levels(daily: pd.DataFrame | None, intraday: pd.DataFrame | None, price: float | None,
               atr_1h: float | None, cme: bool) -> list[dict]:
    """Previous day high/low/close, weekly open and (CME) overnight high/low."""
    if price is None:
        return []
    levels = []
    if daily is not None and len(daily) > 1:
        prev = daily.iloc[-2]
        levels += [("Prev day high", prev["high"]), ("Prev day low", prev["low"]), ("Prev day close", prev["close"])]
    if intraday is not None and len(intraday):
        week = _week_key(intraday.index, cme)
        levels.append(("Weekly open", intraday["open"][week == week[-1]].iloc[0]))
        if cme:
            last = intraday.index[-1]
            session = last.normalize() + pd.Timedelta(hours=18)
            if session > last:
                session -= pd.Timedelta(days=1)
            overnight = intraday[(intraday.index >= session) & (intraday.index < session + pd.Timedelta(hours=15.5))]
            if len(overnight):
                levels += [("Overnight high", overnight["high"].max()), ("Overnight low", overnight["low"].min())]
    out = []
    for name, level in levels:
        dist = price - level
        out.append({
            "name": name,
            "price": round(float(level), 4),
            "distance_pct": round(100 * dist / level, 2),
            "testing": bool(atr_1h and abs(dist) <= LEVEL_TEST_ATR * atr_1h),
        })
    return out


def volatility(daily: pd.DataFrame | None) -> dict | None:
    """Daily ATR and how much of it today's range has used so far."""
    if daily is None or len(daily) < 16:
        return None
    atr = ind.atr(daily).iloc[-2]  # yesterday's ATR, so today's partial bar doesn't skew it
    today = daily.iloc[-1]
    used = (today["high"] - today["low"]) / atr if atr else 0
    regime = "quiet" if used < 0.5 else "normal" if used < 1.0 else "active" if used < 1.5 else "wild"
    return {
        "atr": round(float(atr), 4),
        "atr_pct": round(float(100 * atr / today["close"]), 2),
        "range_used_pct": round(float(100 * used)),
        "regime": regime,
    }


def alignment(frames: dict) -> str:
    """A one-line read of how the lower (1m-15m) and higher (1h-1D) timeframes line up."""
    def side(tfs):
        biases = [frames[t]["bias"] for t in tfs if t in frames]
        if not biases:
            return None
        bull = biases.count("BULLISH")
        return "BULLISH" if bull > len(biases) / 2 else "BEARISH" if bull < len(biases) / 2 else None

    low, high = side(["1m", "5m", "15m"]), side(["1h", "4h", "1D"])
    all_biases = {f["bias"] for f in frames.values()}
    if len(all_biases) == 1:
        return f"All timeframes aligned {all_biases.pop().lower()}."
    if high == "BULLISH" and low == "BEARISH":
        return "Pullback in an uptrend: higher timeframes bullish, lower timeframes bearish."
    if high == "BEARISH" and low == "BULLISH":
        return "Bounce in a downtrend: higher timeframes bearish, lower timeframes bullish."
    if high and high == low:
        return f"Mostly {high.lower()}, with some timeframes disagreeing."
    return "Mixed: no clear agreement between timeframes."


def reaction(bars_1m: pd.DataFrame | None, event_time: datetime, minutes: int) -> float | None:
    """% move from just before an event to `minutes` after it, from 1m bars."""
    if bars_1m is None or not len(bars_1m):
        return None
    before = bars_1m[bars_1m.index < event_time]
    after = bars_1m[bars_1m.index <= event_time + timedelta(minutes=minutes)]
    if not len(before) or event_time - before.index[-1] > timedelta(minutes=5) or after.index[-1] < event_time:
        return None  # market closed or no data around the release
    start, end = before["close"].iloc[-1], after["close"].iloc[-1]
    return round(float(100 * (end / start - 1)), 2)
