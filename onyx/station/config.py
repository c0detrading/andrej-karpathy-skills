"""All tunable settings in one place."""

# Assets you can pick on the Settings page.
#   cme:   True  -> 4h bars start at the 18:00 New York session open (futures, FX);
#          False -> 4h bars start at 00:00 UTC (24/7 markets like crypto).
#   news:  which headline profile moves it ("GOLD", "NASDAQ", "BITCOIN") or None.
#   macro: how a rising dollar / rising 10y yield affects it (-1 = fully against, 0 = ignore).
#   oanda: the OANDA instrument used instead of Yahoo when an OANDA token is set (real-time).
#          OANDA prices are spot/CFD, so levels differ slightly from the futures on Yahoo.
ASSET_PRESETS = {
    "GOLD": {"ticker": "GC=F", "name": "Gold (COMEX GC)", "cme": True, "news": "GOLD", "macro": -1.0, "oanda": "XAU_USD"},
    "NASDAQ": {"ticker": "NQ=F", "name": "Nasdaq 100 (CME NQ)", "cme": True, "news": "NASDAQ", "macro": -0.5, "oanda": "NAS100_USD"},
    "BITCOIN": {"ticker": "BTC-USD", "name": "Bitcoin", "cme": False, "news": "BITCOIN", "macro": -0.5, "oanda": "BTC_USD"},
    "SILVER": {"ticker": "SI=F", "name": "Silver (COMEX SI)", "cme": True, "news": "GOLD", "macro": -1.0, "oanda": "XAG_USD"},
    "SP500": {"ticker": "ES=F", "name": "S&P 500 (CME ES)", "cme": True, "news": "NASDAQ", "macro": -0.5, "oanda": "SPX500_USD"},
    "DOW": {"ticker": "YM=F", "name": "Dow (CBOT YM)", "cme": True, "news": "NASDAQ", "macro": -0.5, "oanda": "US30_USD"},
    "OIL": {"ticker": "CL=F", "name": "Crude Oil (NYMEX CL)", "cme": True, "news": None, "macro": 0.0, "oanda": "WTICO_USD"},
    "EURUSD": {"ticker": "EURUSD=X", "name": "EUR/USD", "cme": True, "news": None, "macro": -1.0, "oanda": "EUR_USD"},
    "ETHEREUM": {"ticker": "ETH-USD", "name": "Ethereum", "cme": False, "news": "BITCOIN", "macro": -0.5, "oanda": "ETH_USD"},
}
DEFAULT_ASSETS = ["GOLD", "NASDAQ", "BITCOIN"]
NEWS_PROFILES = ["GOLD", "NASDAQ", "BITCOIN"]

# Cross-market inputs: a rising dollar index and 10-year yield pressure most assets.
MACRO = {
    "DXY": {"ticker": "DX-Y.NYB", "name": "US Dollar Index"},
    "US10Y": {"ticker": "^TNX", "name": "US 10Y yield"},
}
MACRO_TIMEFRAME_WEIGHTS = {"1h": 0.3, "4h": 0.3, "1D": 0.4}

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
# The 1m timeframe is shown but not counted: it backtested as the noisiest.
TIMEFRAME_WEIGHTS = {"1m": 0, "5m": 10, "15m": 13, "1h": 20, "4h": 25, "1D": 32}

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
# Scores closer to zero than this are shown as "no clear bias" (the lean is still shown).
WEAK_THRESHOLD = 20

# How the overall daily bias is blended (sums to 1).
TECH_WEIGHT = 0.6
NEWS_WEIGHT = 0.25
MACRO_WEIGHT = 0.15
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
    "Yahoo Finance": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,NQ=F,^NDX,BTC-USD&region=US&lang=en-US",
    "Fed": "https://www.federalreserve.gov/feeds/press_monetary.xml",
    "Fed Speeches": "https://www.federalreserve.gov/feeds/speeches.xml",
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
}
FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_REFRESH_SECONDS = 60
FF_REFRESH_SECONDS = 1800

HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (onyx)"}

# Accuracy: a timeframe's bias is checked against the price this many bars later.
ACCURACY_HORIZON_BARS = {"1m": 15, "5m": 12, "15m": 16, "1h": 8, "4h": 6, "1D": 1}
ACCURACY_MAX_SAMPLES = 1000
# The live daily record snapshots every asset's overall bias at this New York time.
LIVE_LOG_TIME_NY = "09:30"

# Model tuning reruns once a day (see bias.tune).
TUNE_EVERY_HOURS = 24

# Key levels count as "testing" when price is within this many 1h ATRs.
LEVEL_TEST_ATR = 0.25

# After a high-impact event, measure each asset's move over this many minutes.
REACTION_MINUTES = 15

# Claude headline scoring (optional, needs an Anthropic API key in Settings).
CLAUDE_MODEL = "claude-opus-5"
CLAUDE_BATCH_SIZE = 25
CLAUDE_DAILY_HEADLINE_CAP = 200
