"""Price bars from the Yahoo Finance chart API."""

import pandas as pd

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def parse_chart(payload: dict) -> pd.DataFrame:
    """Turn a Yahoo chart response into an OHLCV frame indexed by New York time."""
    result = payload["chart"]["result"][0]
    quote = result["indicators"]["quote"][0]
    index = pd.to_datetime(result.get("timestamp", []), unit="s", utc=True).tz_convert("America/New_York")
    df = pd.DataFrame(
        {k: quote.get(k, []) for k in ("open", "high", "low", "close", "volume")},
        index=index,
        dtype=float,
    )
    return df.dropna(subset=["open", "high", "low", "close"])


def resample(df: pd.DataFrame, rule: str, cme: bool = True) -> pd.DataFrame:
    """Resample bars. For CME futures 4h bins start at 18:00 New York (the session open);
    for 24/7 markets like Bitcoin they start at 00:00 UTC, as on most crypto charts."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if cme:
        out = df.resample(rule, offset="2h" if rule == "4h" else None).agg(agg)
    else:
        out = df.tz_convert("UTC").resample(rule).agg(agg).tz_convert(df.index.tz)
    return out.dropna(subset=["close"])


# Yahoo interval -> (OANDA granularity, candles to request). 4h is still resampled from 1h.
OANDA_GRANULARITY = {"1m": ("M1", 5000), "5m": ("M5", 2000), "15m": ("M15", 2000), "60m": ("H1", 4000), "1d": ("D", 500)}
OANDA_HOSTS = {"practice": "https://api-fxpractice.oanda.com", "live": "https://api-fxtrade.oanda.com"}


def parse_oanda(payload: dict) -> pd.DataFrame:
    """Turn an OANDA v20 candles response (mid prices) into an OHLCV frame in New York time."""
    candles = payload.get("candles", [])
    index = pd.to_datetime([c["time"] for c in candles], utc=True).tz_convert("America/New_York")
    return pd.DataFrame(
        {
            "open": [float(c["mid"]["o"]) for c in candles],
            "high": [float(c["mid"]["h"]) for c in candles],
            "low": [float(c["mid"]["l"]) for c in candles],
            "close": [float(c["mid"]["c"]) for c in candles],
            "volume": [float(c.get("volume", 0)) for c in candles],
        },
        index=index,
    )


async def fetch_oanda(client, token: str, env: str, instrument: str, interval: str) -> pd.DataFrame:
    granularity, count = OANDA_GRANULARITY[interval]
    resp = await client.get(
        f"{OANDA_HOSTS[env]}/v3/instruments/{instrument}/candles",
        params={"granularity": granularity, "count": count, "price": "M",
                "dailyAlignment": 17, "alignmentTimezone": "America/New_York"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        try:
            detail = resp.json().get("errorMessage", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"OANDA HTTP {resp.status_code} {detail}".strip())
    return parse_oanda(resp.json())


async def fetch_bars(client, ticker: str, interval: str, range_: str) -> pd.DataFrame:
    resp = await client.get(
        YAHOO_CHART_URL.format(ticker=ticker),
        params={"interval": interval, "range": range_, "includePrePost": "true"},
    )
    resp.raise_for_status()
    return parse_chart(resp.json())
