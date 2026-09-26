from datetime import datetime, timedelta, timezone

import numpy as np

from station import config as cfg
from station.engine import Station
from tests.test_indicators_bias import bars

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def load(station, close):
    for sym in cfg.SYMBOLS.values():
        for interval, _, _ in cfg.TIMEFRAMES.values():
            freq = {"1m": "1min", "5m": "5min", "15m": "15min", "60m": "1h", "1d": "1D"}[interval]
            n = 1200 if interval == "60m" else 300  # 4h needs 200 bars after resampling
            station.bars[(sym["ticker"], interval)] = bars(np.linspace(*close, n), freq)


def test_first_computation_is_silent_then_flips_notify():
    s = Station()
    load(s, (100, 200))
    s._recompute(NOW)
    assert s.symbols["GOLD"]["bias"] == "BULLISH"
    assert all(f["bias"] == "BULLISH" for f in s.symbols["GOLD"]["timeframes"].values())
    assert s.notifications == []

    load(s, (200, 100))
    s._recompute(NOW)
    assert s.symbols["GOLD"]["bias"] == "BEARISH"
    titles = [n["title"] for n in s.notifications]
    assert any("daily bias → BEARISH" in t for t in titles)
    # only ALERT_TIMEFRAMES notify; 1m/5m flips are silent
    assert any(" 1h → BEARISH" in t for t in titles)
    assert not any(" 1m → " in t or " 5m → " in t for t in titles)


def test_news_shifts_overall_and_backlog_is_silent():
    s = Station()
    load(s, (100, 200))
    old = {"id": "old", "source": "t", "title": "old", "published": NOW,
           "impact": {"GOLD": 3, "NASDAQ": 0, "tags": []}}
    s._merge_news([old], NOW)
    assert s.notifications == []  # first batch is backlog

    s._recompute(NOW)
    gold = s.symbols["GOLD"]
    assert gold["news"] == 60
    assert gold["score"] == round((1 - cfg.NEWS_WEIGHT) * gold["technical"] + cfg.NEWS_WEIGHT * 60, 1)
    assert gold["drivers"][0]["title"] == "old"

    new = {**old, "id": "new", "title": "Fed hikes rates", "impact": {"GOLD": -2, "NASDAQ": -2, "tags": []}}
    stale = {**new, "id": "stale", "title": "Fed hikes rates again", "published": NOW - timedelta(hours=2)}
    s._merge_news([new, stale], NOW)
    assert len(s.notifications) == 1 and "Gold ▼" in s.notifications[0]["title"]


def test_high_impact_event_alert_fires_once():
    s = Station()
    s.calendar = [{"title": "CPI m/m", "country": "USD", "impact": "High", "time": NOW + timedelta(minutes=10),
                   "forecast": "0.3%", "previous": "0.2%"}]
    s._check_calendar(NOW)
    s._check_calendar(NOW + timedelta(minutes=1))
    assert len(s.notifications) == 1
    assert s.notifications[0]["title"] == "In 10 min: USD CPI m/m"
