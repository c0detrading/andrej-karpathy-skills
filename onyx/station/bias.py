"""Turn indicator readings into a bullish/bearish score per timeframe, and measure how well it works."""

import numpy as np
import pandas as pd

from . import indicators as ind
from .config import ACCURACY_MAX_SAMPLES, BIAS_HYSTERESIS, INDICATOR_WEIGHTS, WEAK_THRESHOLD

MIN_BARS = 200  # EMA200 needs this many bars to mean anything
TRAIN_SHARE = 0.7
MIN_SPLIT_SAMPLES = 50
MIN_EDGE_PCT = 0.01  # roughly a round-trip spread; smaller edges are not worth switching for

TREND_KEYS = [k for k in INDICATOR_WEIGHTS if "ema" in k]
MOMENTUM_KEYS = [k for k in INDICATOR_WEIGHTS if "ema" not in k]


def _weighted(votes: pd.DataFrame, keys) -> pd.Series:
    """Weighted vote over `keys`, rescaled so the full range is still -100..+100."""
    total = sum(INDICATOR_WEIGHTS[k] for k in keys)
    return sum(INDICATOR_WEIGHTS[k] * votes[k] for k in keys) * (100 / total)


# Alternative models the tuner tries. A score of exactly 0 means "no call".
VARIANTS = {
    "default": lambda v, x: _weighted(v, INDICATOR_WEIGHTS),
    "trend": lambda v, x: _weighted(v, TREND_KEYS),
    "momentum": lambda v, x: _weighted(v, MOMENTUM_KEYS),
    "adx-filter": lambda v, x: _weighted(v, INDICATOR_WEIGHTS).where(x["adx"] >= 20, 0.0),
    "contrarian": lambda v, x: -_weighted(v, INDICATOR_WEIGHTS),
}
VARIANT_LABELS = {
    "default": "all indicators",
    "trend": "EMAs only",
    "momentum": "RSI/Bollinger/MACD/DMI only",
    "adx-filter": "all indicators, only when trending (ADX ≥ 20)",
    "contrarian": "fade the indicators",
}


def indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Votes (-1..1 per indicator) and raw indicator values for every bar."""
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
    values = pd.DataFrame({
        "close": close,
        "ema20": e[20], "ema50": e[50], "ema100": e[100], "ema200": e[200],
        "rsi": rsi, "pct_b": bb["pct_b"], "bb_upper": bb["upper"], "bb_lower": bb["lower"],
        "macd_hist": macd["hist"], "adx": dmi["adx"], "plus_di": dmi["plus_di"], "minus_di": dmi["minus_di"],
        "atr": ind.atr(df),
    })
    return pd.concat({"votes": votes, "values": values}, axis=1)


def score_frame(df: pd.DataFrame, variant: str = "default", frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Indicator frame plus a "score" column from -100 (fully bearish) to +100 (fully bullish)."""
    frame = indicator_frame(df) if frame is None else frame
    score = VARIANTS[variant](frame["votes"], frame["values"])
    return frame.assign(score=score.round(1))


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


def samples(close: pd.Series, score: pd.Series, horizon: int) -> pd.DataFrame:
    """Replay the bias bar by bar. One row per bar that made a call and has a known outcome:
    direction (+1/-1), the % move `horizon` bars later, and the score."""
    fwd = (close.shift(-horizon) / close - 1).to_numpy() * 100
    sc = score.to_numpy()
    rows, bias = [], None
    for i in range(MIN_BARS - 1, len(close) - horizon):
        bias = next_bias(sc[i], bias)
        if sc[i] != 0 and fwd[i] == fwd[i]:  # skip "no call" bars and NaN outcomes
            rows.append((i, 1 if bias == "BULLISH" else -1, fwd[i], sc[i]))
    return pd.DataFrame(rows, columns=["i", "direction", "fwd_pct", "score"])


def evaluate(s: pd.DataFrame) -> dict | None:
    """Hit rate and edge (average % move in the bias direction) for a set of samples."""
    s = s[s["fwd_pct"] != 0]
    if s.empty:
        return None
    signed = s["direction"] * s["fwd_pct"]
    bull, bear = s[s["direction"] > 0]["fwd_pct"], s[s["direction"] < 0]["fwd_pct"]
    strong = s[s["score"].abs() >= WEAK_THRESHOLD]
    strong_signed = strong["direction"] * strong["fwd_pct"]
    r = lambda x, d=3: None if x != x else round(float(x), d)
    return {
        "n": len(s),
        "hit_rate": r(100 * (signed > 0).mean(), 1),
        "edge_pct": r(signed.mean()),
        "bull_avg_pct": r(bull.mean()) if len(bull) else None,
        "bear_avg_pct": r(bear.mean()) if len(bear) else None,
        "baseline_pct": r(s["fwd_pct"].mean()),  # what always-long would have made
        "strong_n": len(strong),
        "strong_hit_rate": r(100 * (strong_signed > 0).mean(), 1) if len(strong) else None,
        "strong_edge_pct": r(strong_signed.mean()) if len(strong) else None,
    }


def accuracy(close: pd.Series, score: pd.Series, horizon: int) -> dict | None:
    """Evaluate the most recent ACCURACY_MAX_SAMPLES calls."""
    return evaluate(samples(close, score, horizon).tail(ACCURACY_MAX_SAMPLES))


def tune(df: pd.DataFrame, horizon: int, frame: pd.DataFrame | None = None) -> dict | None:
    """Walk-forward model choice: pick the variant with the best edge on the older 70% of
    history, and keep it only if it also beats the default on the newest 30% it never saw."""
    frame = indicator_frame(df) if frame is None else frame
    results = {}
    for name in VARIANTS:
        s = samples(df["close"], VARIANTS[name](frame["votes"], frame["values"]), horizon)
        split = MIN_BARS + TRAIN_SHARE * (len(df) - horizon - MIN_BARS)
        train, test = evaluate(s[s["i"] < split]), evaluate(s[s["i"] >= split])
        if train and test and train["n"] >= MIN_SPLIT_SAMPLES and test["n"] >= MIN_SPLIT_SAMPLES:
            results[name] = {"train": train, "test": test}
    if "default" not in results:
        return None
    best = max(results, key=lambda k: results[k]["train"]["edge_pct"])
    test_edge = results[best]["test"]["edge_pct"]
    chosen = best if test_edge >= MIN_EDGE_PCT and test_edge > results["default"]["test"]["edge_pct"] else "default"
    return {"variant": chosen, "best_on_train": best, "results": results}
