"""Turn indicator readings into a bullish/bearish score per timeframe."""

import pandas as pd

from . import indicators as ind
from .config import BIAS_HYSTERESIS, INDICATOR_WEIGHTS

MIN_BARS = 200  # EMA200 needs this many bars to mean anything


def _sign(x: float) -> int:
    return int(x > 0) - int(x < 0)


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def score_timeframe(df: pd.DataFrame) -> dict | None:
    """Score the latest bar from -100 (fully bearish) to +100 (fully bullish).

    Every indicator casts a vote in [-1, 1]; votes are weighted by INDICATOR_WEIGHTS.
    Returns None when there is not enough history.
    """
    if len(df) < MIN_BARS:
        return None
    close = df["close"]
    e = {n: ind.ema(close, n).iloc[-1] for n in (20, 50, 100, 200)}
    rsi = ind.rsi(close).iloc[-1]
    bb = ind.bollinger(close).iloc[-1]
    macd = ind.macd(close).iloc[-1]
    dmi = ind.dmi(df).iloc[-1]
    last = close.iloc[-1]

    votes = {
        "close>ema20": _sign(last - e[20]),
        "close>ema50": _sign(last - e[50]),
        "close>ema100": _sign(last - e[100]),
        "close>ema200": _sign(last - e[200]),
        "ema20>ema50": _sign(e[20] - e[50]),
        "ema50>ema100": _sign(e[50] - e[100]),
        "ema100>ema200": _sign(e[100] - e[200]),
        # RSI 50 is neutral; 70+ counts as fully bullish momentum, 30- fully bearish.
        "rsi": _clamp((rsi - 50) / 20),
        # %B 0.5 is the middle band; riding the upper band is fully bullish.
        "bollinger": _clamp((bb["pct_b"] - 0.5) * 2) if pd.notna(bb["pct_b"]) else 0.0,
        # Half for histogram direction, half for MACD above/below zero.
        "macd": 0.5 * _sign(macd["hist"]) + 0.5 * _sign(macd["macd"]),
        "dmi": _sign(dmi["plus_di"] - dmi["minus_di"]),
    }
    score = sum(INDICATOR_WEIGHTS[k] * v for k, v in votes.items())
    return {
        "score": round(score, 1),
        "votes": votes,
        "values": {
            "close": last,
            "ema20": e[20], "ema50": e[50], "ema100": e[100], "ema200": e[200],
            "rsi": rsi,
            "pct_b": bb["pct_b"],
            "macd_hist": macd["hist"],
            "adx": dmi["adx"],
            "plus_di": dmi["plus_di"],
            "minus_di": dmi["minus_di"],
        },
    }


def next_bias(score: float, previous: str | None) -> str:
    """BULLISH/BEARISH with hysteresis: flip only once the score is BIAS_HYSTERESIS past zero."""
    if score >= BIAS_HYSTERESIS:
        return "BULLISH"
    if score <= -BIAS_HYSTERESIS:
        return "BEARISH"
    if previous:
        return previous
    return "BULLISH" if score >= 0 else "BEARISH"
