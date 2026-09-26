"""Turn indicator readings into a bullish/bearish score per timeframe."""

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import ACCURACY_MAX_SAMPLES, BIAS_HYSTERESIS, INDICATOR_WEIGHTS

MIN_BARS = 200  # EMA200 needs this many bars to mean anything


def score_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Votes, score and indicator values for every bar.

    Every indicator casts a vote in [-1, 1]; votes are weighted by INDICATOR_WEIGHTS
    into a score from -100 (fully bearish) to +100 (fully bullish).
    """
    close = df["close"]
    e = {n: ind.ema(close, n) for n in (20, 50, 100, 200)}
    rsi = ind.rsi(close)
    bb = ind.bollinger(close)
    macd = ind.macd(close)
    dmi = ind.dmi(df)
    sign = np.sign

    votes = pd.DataFrame({
        "close>ema20": sign(close - e[20]),
        "close>ema50": sign(close - e[50]),
        "close>ema100": sign(close - e[100]),
        "close>ema200": sign(close - e[200]),
        "ema20>ema50": sign(e[20] - e[50]),
        "ema50>ema100": sign(e[50] - e[100]),
        "ema100>ema200": sign(e[100] - e[200]),
        # RSI 50 is neutral; 70+ counts as fully bullish momentum, 30- fully bearish.
        "rsi": ((rsi - 50) / 20).clip(-1, 1),
        # %B 0.5 is the middle band; riding the upper band is fully bullish.
        "bollinger": ((bb["pct_b"] - 0.5) * 2).clip(-1, 1),
        # Half for histogram direction, half for MACD above/below zero.
        "macd": 0.5 * sign(macd["hist"]) + 0.5 * sign(macd["macd"]),
        "dmi": sign(dmi["plus_di"] - dmi["minus_di"]),
    }).fillna(0.0)
    score = sum(INDICATOR_WEIGHTS[k] * votes[k] for k in votes)
    values = pd.DataFrame({
        "close": close,
        "ema20": e[20], "ema50": e[50], "ema100": e[100], "ema200": e[200],
        "rsi": rsi, "pct_b": bb["pct_b"], "bb_upper": bb["upper"], "bb_lower": bb["lower"],
        "macd_hist": macd["hist"], "adx": dmi["adx"], "plus_di": dmi["plus_di"], "minus_di": dmi["minus_di"],
        "atr": ind.atr(df),
    })
    return pd.concat({"votes": votes, "values": values}, axis=1).assign(score=score.round(1))


def score_timeframe(df: pd.DataFrame, frame: pd.DataFrame | None = None) -> dict | None:
    """Score the latest bar, or None when there is not enough history."""
    if len(df) < MIN_BARS:
        return None
    frame = score_frame(df) if frame is None else frame
    last = frame.iloc[-1]
    return {
        "score": float(last["score"].iloc[0]),
        "votes": {k: float(v) for k, v in last["votes"].items()},
        "values": {k: float(v) for k, v in last["values"].items()},
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


def accuracy(close: pd.Series, score: pd.Series, horizon: int) -> dict | None:
    """How often the bias called the direction of price `horizon` bars later.

    Replays the bias bar by bar (with hysteresis) over up to ACCURACY_MAX_SAMPLES recent
    bars that have both 200 bars of history and a known outcome.
    """
    fwd = close.shift(-horizon) - close
    start = max(MIN_BARS, len(close) - horizon - ACCURACY_MAX_SAMPLES)
    bias, hits, n = None, 0, 0
    for i in range(MIN_BARS - 1, len(close) - horizon):
        bias = next_bias(score.iloc[i], bias)
        move = fwd.iloc[i]
        if i < start or move == 0:
            continue
        n += 1
        hits += (move > 0) == (bias == "BULLISH")
    return {"hit_rate": round(100 * hits / n, 1), "n": n} if n else None
