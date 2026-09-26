"""All tunable settings in one place."""

SYMBOLS = {
    "GOLD": {"ticker": "GC=F", "name": "Gold (COMEX GC)"},
    "NASDAQ": {"ticker": "NQ=F", "name": "Nasdaq 100 (CME NQ)"},
}

# Station timeframe -> (Yahoo interval, Yahoo range, resample rule or None).
# Yahoo has no 4h bars, so 4h is resampled from 60m.
TIMEFRAMES = {
    "1m": ("1m", "5d", None),
    "5m": ("5m", "5d", None),
    "15m": ("15m", "1mo", None),
    "1h": ("60m", "6mo", None),
    "4h": ("60m", "6mo", "4h"),
    "1D": ("1d", "2y", None),
}

# How long a fetched Yahoo interval stays fresh, in seconds.
REFRESH_SECONDS = {"1m": 30, "5m": 60, "15m": 120, "60m": 300, "1d": 600}

# Weight of each timeframe in the overall daily bias (sums to 100).
TIMEFRAME_WEIGHTS = {"1m": 5, "5m": 8, "15m": 12, "1h": 20, "4h": 25, "1D": 30}

# Weight of each indicator vote in a timeframe score (sums to 100).
INDICATOR_WEIGHTS = {
    "close>ema20": 5,
    "close>ema50": 5,
    "close>ema100": 5,
    "close>ema200": 10,
    "ema20>ema50": 5,
    "ema50>ema100": 5,
    "ema100>ema200": 10,
    "rsi": 15,
    "bollinger": 15,
    "macd": 15,
    "dmi": 10,
}

# A bias only flips once the score crosses this far past zero (stops flapping).
BIAS_HYSTERESIS = 10

# Share of the overall bias that comes from news (the rest is technical).
NEWS_WEIGHT = 0.3
NEWS_HALF_LIFE_MIN = 90      # a headline's effect halves every 90 minutes
NEWS_WINDOW_HOURS = 6        # headlines older than this are ignored
NEWS_POINTS_PER_UNIT = 20    # rule impact 1.0 == 20 news-score points
NEWS_ALERT_IMPACT = 2.0      # headlines at or above this |impact| trigger a notification

# Timeframes whose bias flips send a notification (1m/5m flip too often).
ALERT_TIMEFRAMES = ["15m", "1h", "4h", "1D"]

# Forex Factory calendar filter and pre-event alert.
FF_COUNTRIES = ["USD"]
FF_IMPACTS = ["High", "Medium"]
FF_ALERT_MINUTES = 15

NEWS_FEEDS = {
    "FinancialJuice": "https://www.financialjuice.com/feed.ashx?xy=rss",
    "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,NQ=F,^NDX&region=US&lang=en-US",
}
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_REFRESH_SECONDS = 60
FF_REFRESH_SECONDS = 1800

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (trading-station)"}
