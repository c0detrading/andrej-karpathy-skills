import asyncio
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from station import config as cfg
from station import llm
from station.engine import Station
from tests.test_indicators_bias import bars

NOW = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)  # Thursday 10:00 New York
FREQ = {"1m": "1min", "5m": "5min", "15m": "15min", "60m": "1h", "1d": "1D"}


def load(station, close, tickers=None):
    tickers = tickers or [a["ticker"] for a in station.assets.values()]
    for ticker in tickers:
        for interval, _, _ in cfg.TIMEFRAMES.values():
            n = 1200 if interval == "60m" else 300  # 4h needs 200 bars after resampling
            station.bars[(ticker, interval)] = bars(np.linspace(*close, n), FREQ[interval])


def headline(id_, title, minutes_ago=0, **impact):
    return {"id": id_, "source": "FinancialJuice", "title": title, "published": NOW - timedelta(minutes=minutes_ago),
            "impact": {"GOLD": 0, "NASDAQ": 0, "BITCOIN": 0, "tags": [], **impact}}


def test_first_computation_is_silent_then_flips_notify():
    s = Station()
    load(s, (100, 200))
    s._recompute(NOW)
    assert set(s.symbols) == {"GOLD", "NASDAQ", "BITCOIN"}
    assert s.symbols["GOLD"]["bias"] == "BULLISH"
    assert s.symbols["GOLD"]["read"] == "All timeframes aligned bullish."
    assert s.notifications == []

    load(s, (200, 100))
    s._recompute(NOW)
    assert s.symbols["GOLD"]["bias"] == "BEARISH"
    titles = [n["title"] for n in s.notifications]
    assert any("daily bias → BEARISH" in t for t in titles)
    assert any(" 1h → BEARISH" in t for t in titles)
    assert not any(" 1m → " in t or " 5m → " in t for t in titles)


def test_accuracy_is_reported_per_timeframe():
    s = Station()
    load(s, (100, 200))
    s._recompute(NOW)
    acc = s.symbols["GOLD"]["timeframes"]["1h"]["accuracy"]
    assert acc["hit_rate"] == 100 and acc["n"] > 0 and acc["horizon"] == cfg.ACCURACY_HORIZON_BARS["1h"]


def test_overall_blends_technical_news_and_macro():
    s = Station()
    load(s, (100, 200))
    load(s, (100, 200), [m["ticker"] for m in cfg.MACRO.values()])  # dollar and yields rising
    s._merge_news([headline("old", "old", GOLD=3)])  # first batch is backlog: stored, not alerted
    s._recompute_macro()
    s._recompute(NOW)
    gold = s.symbols["GOLD"]
    assert s.macro_pressure > 90 and s.macro["DXY"]["direction"] == "RISING"
    assert gold["news"] == 60 and gold["macro"] == -s.macro_pressure
    expected = cfg.TECH_WEIGHT * gold["technical"] + cfg.NEWS_WEIGHT * 60 + cfg.MACRO_WEIGHT * gold["macro"]
    assert gold["score"] == round(expected, 1)
    assert "Macro headwind" in gold["read"]
    assert s.notifications == []


def test_new_headlines_alert_but_stale_ones_do_not():
    s = Station()
    s._merge_news([headline("a", "backlog", GOLD=3)])
    new = s._merge_news([headline("b", "Fed hikes rates", GOLD=-2, NASDAQ=-2, BITCOIN=-2),
                         headline("c", "Fed hikes again", 120, GOLD=-2)])
    s._alert_news(new, NOW)
    assert len(s.notifications) == 1
    assert s.notifications[0]["title"] == "FinancialJuice: Gold ▼ · Nasdaq ▼ · Bitcoin ▼"


def test_claude_rescore_replaces_rule_impact_within_daily_cap(monkeypatch):
    s = Station()
    s.settings.update(claude_scoring=True, anthropic_api_key="sk-test")
    calls = []

    async def fake_score(key, items):
        calls.append([i["id"] for i in items])
        return {i["id"]: {"GOLD": 2.5, "NASDAQ": 0, "BITCOIN": 0, "tags": ["AI: test"]} for i in items}

    monkeypatch.setattr(llm, "score", fake_score)
    monkeypatch.setattr(cfg, "CLAUDE_DAILY_HEADLINE_CAP", 1)
    items = [headline("x", "Fed signals patience"), headline("y", "Gold demand rises"), headline("z", "Celebrity news")]
    asyncio.run(s._claude_rescore(items))
    assert calls == [["x"]]  # capped at 1; "z" is not market-relevant anyway
    assert items[0]["impact"]["tags"] == ["AI: test"] and items[0]["impact_rules"]["tags"] == []
    asyncio.run(s._claude_rescore(items))
    assert len(calls) == 1  # cap reached for today


def test_high_impact_event_alert_fires_once():
    s = Station()
    s.calendar = [{"title": "CPI m/m", "country": "USD", "impact": "High", "time": NOW + timedelta(minutes=10),
                   "forecast": "0.3%", "previous": "0.2%"}]
    s._check_calendar(NOW)
    s._check_calendar(NOW + timedelta(minutes=1))
    assert len(s.notifications) == 1
    assert s.notifications[0]["title"] == "In 10 min: USD CPI m/m"


def test_reaction_measured_after_release():
    s = Station()
    event = pd.Timestamp("2026-09-24 08:30", tz="America/New_York").to_pydatetime()
    idx = pd.date_range(event - timedelta(minutes=30), periods=60, freq="1min")
    close = np.where(idx < event, 100.0, 101.0)
    df = pd.DataFrame({"open": close, "high": close, "low": close, "close": close, "volume": 1.0}, index=idx)
    s.bars[("GC=F", "1m")] = df
    s.calendar = [{"title": "CPI m/m", "country": "USD", "impact": "High", "time": event, "forecast": "", "previous": ""}]
    s._check_reactions(event + timedelta(minutes=10))
    assert s.reactions == {}  # too early
    s._check_reactions(event + timedelta(minutes=20))
    key = next(iter(s.reactions))
    assert s.reactions[key]["GOLD"] == 1.0 and s.reactions[key]["NASDAQ"] is None
    assert s.notifications[-1]["body"] == "Gold (COMEX GC) +1.00%"


def test_live_log_records_once_per_day_in_window():
    s = Station()
    load(s, (100, 200))
    s._recompute(NOW)
    s._live_log(NOW - timedelta(hours=1))  # 09:00 New York: too early
    assert s.live_records == []
    s._live_log(NOW)
    s._live_log(NOW + timedelta(minutes=5))
    assert len(s.live_records) == 3 and {r["asset"] for r in s.live_records} == {"GOLD", "NASDAQ", "BITCOIN"}
    assert Station().live_records == s.live_records  # persisted to disk


def test_briefing_and_telegram_outbox():
    s = Station()
    load(s, (100, 200))
    s._recompute(NOW)
    s.settings["briefing_time"] = "00:00"
    s._maybe_brief(NOW)
    s._maybe_brief(NOW)
    briefs = [n for n in s.notifications if n["kind"] == "briefing"]
    assert len(briefs) == 1 and "Gold (COMEX GC): BULLISH" in briefs[0]["body"]
    assert s._outbox  # queued for Telegram

    asyncio.run(s._flush_telegram(None))  # Telegram not configured: queue dropped
    assert s._outbox == []


def test_settings_change_assets():
    s = Station()
    s.update_settings({"assets": ["SILVER", "GOLD", "NOPE"],
                       "custom_assets": {"xrp": {"ticker": "XRP-USD", "name": "XRP", "cme": False, "news": "BITCOIN", "macro": -0.5}}})
    assert list(s.assets) == ["SILVER", "GOLD"]
    s.update_settings({"assets": ["XRP"]})
    assert s.assets["XRP"]["ticker"] == "XRP-USD"
    with pytest.raises(ValueError):
        s.update_settings({"assets": []})
    with pytest.raises(ValueError):
        s.update_settings({"custom_assets": {"BAD": {"ticker": "a b/c"}}})
