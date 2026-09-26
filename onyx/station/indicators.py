"""Standard indicators, computed the way TradingView does (Wilder smoothing for RSI/DMI)."""

import pandas as pd


def ema(close: pd.Series, length: int) -> pd.Series:
    return close.ewm(span=length, adjust=False).mean()


def _wilder(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0), length)
    loss = _wilder(-delta.clip(upper=0), length)
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0)


def bollinger(close: pd.Series, length: int = 20, mult: float = 2.0) -> pd.DataFrame:
    mid = close.rolling(length).mean()
    std = close.rolling(length).std(ddof=0)
    upper, lower = mid + mult * std, mid - mult * std
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pct_b": (close - lower) / (upper - lower)})


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift()
    return pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1
    ).max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return _wilder(true_range(df), length)


def dmi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr_avg = atr(df, length)
    plus_di = 100 * _wilder(plus_dm, length) / tr_avg
    minus_di = 100 * _wilder(minus_dm, length) / tr_avg
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": _wilder(dx, length)})
