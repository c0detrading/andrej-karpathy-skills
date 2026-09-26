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


async def fetch_bars(client, ticker: str, interval: str, range_: str) -> pd.DataFrame:
    resp = await client.get(
        YAHOO_CHART_URL.format(ticker=ticker),
        params={"interval": interval, "range": range_, "includePrePost": "true"},
    )
    resp.raise_for_status()
    return parse_chart(resp.json())
