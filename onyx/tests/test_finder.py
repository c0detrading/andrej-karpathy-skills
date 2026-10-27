import asyncio
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import numpy as np
import pytest

from station import config as cfg
from station import finder, settings
from station.engine import Station
from station.market import parse_chart

TODAY = date.today()
CSV = """Symbol,Security,GICS Sector,GICS Sub-Industry,Headquarters Location,Date added,CIK,Founded
GROW,Grower Inc,Information Technology,Software,"Austin, Texas",2001-01-01,111,1990
SHRK,Shrinker Corp,Industrials,Machinery,"Ohio",2002-01-01,222,1950
BRK.B,Berkshire Hathaway,Financials,Insurance,"Omaha, Nebraska",2010-02-16,1067983,1839
NOFX,No Facts Ltd,Energy,Oil,"Texas",2003-01-01,333,1980
GRWB,Grower Inc Class B,Information Technology,Software,"Austin, Texas",2001-01-01,111,1990
"""


def companyfacts(revenue, net_income, eps):
    """SEC company facts with five 3-month quarters, the latest ending 60 days ago."""
    ends = [TODAY - timedelta(days=60 + 91 * i) for i in range(5)][::-1]

    def facts(values):
        return [{"start": (e - timedelta(days=90)).isoformat(), "end": e.isoformat(), "val": v, "fy": e.year,
                 "fp": "Q", "form": "10-Q", "filed": (e + timedelta(days=30)).isoformat(), "accn": f"a{i}"}
                for i, (e, v) in enumerate(zip(ends, values))]

    return {"cik": 1, "entityName": "X", "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": facts(revenue)}},
        "NetIncomeLoss": {"units": {"USD": facts(net_income)}},
        "EarningsPerShareDiluted": {"units": {"USD/shares": facts(eps)}},
    }}}


def chart(close):
    """A Yahoo chart payload of daily bars."""
    start = int(datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp())
    close = [float(c) for c in close]
    return {"chart": {"result": [{"timestamp": [start + 86400 * i for i in range(len(close))],
                                  "indicators": {"quote": [{"open": close, "high": [c * 1.01 for c in close],
                                                            "low": [c * 0.99 for c in close], "close": close,
                                                            "volume": [1e6] * len(close)}]}}]}}


def cooled_uptrend(n=320):
    """A long uptrend whose last month chops sideways: above the 200 EMA with a middling RSI."""
    up = 100 * 1.003 ** np.arange(n - 30)
    chop = up[-1] * (1 + 0.012 * np.tile([1, -1, -0.6], 10)).cumprod()
    return np.concatenate([up, chop])


GROW = companyfacts([100, 110, 120, 130, 140], [15, 17, 19, 21, 23], [1.5, 1.7, 1.9, 2.1, 2.3])
SHRINK = companyfacts([100, 98, 95, 92, 90], [10, 9, 8, 7, 6], [1.0, 0.9, 0.8, 0.7, 0.6])


def transport(requests, sec_status=200):
    def handle(request):
        requests.append(request)
        url = str(request.url)
        if url == cfg.FINDER_UNIVERSE_URL:
            return httpx.Response(200, text=CSV)
        if "data.sec.gov" in url:
            if sec_status != 200:
                return httpx.Response(sec_status)
            if "CIK0000000333" in url:
                return httpx.Response(404)
            return httpx.Response(200, json=GROW if "CIK0000000111" in url else SHRINK)
        if "finance.yahoo.com" in url:
            return httpx.Response(200, json=chart(cooled_uptrend()))
        return httpx.Response(500)
    return httpx.MockTransport(handle)


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    monkeypatch.setattr(cfg, "FINDER_SEC_PAUSE", 0)
    monkeypatch.setattr(cfg, "FINDER_YAHOO_PAUSE", 0)


def run_scan(cache, requests, sec_status=200):
    async def go():
        async with httpx.AsyncClient(transport=transport(requests, sec_status)) as client:
            return await finder.scan(client, "Jane Doe jane@example.com", cache)
    return asyncio.run(go())


def test_parse_constituents_reads_ticker_sector_and_padded_cik():
    rows = finder.parse_constituents(CSV)
    assert rows[0] == {"ticker": "GROW", "name": "Grower Inc", "sector": "Information Technology", "cik": "0000000111"}
    assert rows[2]["ticker"] == "BRK.B"


def test_technicals_on_a_cooled_uptrend():
    t = finder.technicals(parse_chart(chart(cooled_uptrend())))
    assert t["pct_vs_ema200"] > 0 and t["ema50_vs_ema200"] > 0
    assert 35 <= t["rsi14"] <= 60
    assert t["pct_from_high"] < 0


def test_scan_ranks_quality_and_explains_why(tmp_path):
    cache, requests = {}, []
    result = run_scan(cache, requests)
    assert result["companies"] == 5 and result["scanned"] == 4 and result["passed"] == 1  # GRWB: same company as GROW
    assert [f["ticker"] for f in result["failed"]] == ["NOFX"]  # no XBRL facts: skipped, scan goes on
    pick = result["picks"][0]
    assert pick["ticker"] in ("GROW", "GRWB") and pick["cik"] == "0000000111"
    assert pick["revenue_growth_yoy"] == 40.0 and pick["eps_ttm"] == 8.0
    assert pick["pe"] == round(pick["price"] / 8.0, 1)
    assert any(w.startswith("pe ") for w in pick["why"])
    # SEC was asked with the user's contact; Yahoo gets BRK-B, not BRK.B
    sec = [r for r in requests if "data.sec.gov" in str(r.url)]
    assert {r.headers["User-Agent"] for r in sec} == {"Jane Doe jane@example.com"}
    assert any("BRK-B" in str(r.url) for r in requests)
    assert (tmp_path / "sp500.csv").read_text() == CSV


def test_fundamentals_are_cached_for_a_week():
    cache, requests = {}, []
    run_scan(cache, requests)
    assert set(cache) == {"GROW", "GRWB", "SHRK", "BRK.B"} and cache["GROW"]["fetched"] == TODAY.isoformat()
    requests.clear()
    run_scan(cache, requests)
    assert [r for r in requests if "CIK0000000111" in str(r.url)] == []  # cached
    cache["GROW"]["fetched"] = (TODAY - timedelta(days=cfg.FINDER_FUNDAMENTALS_MAX_AGE_DAYS)).isoformat()
    requests.clear()
    run_scan(cache, requests)
    assert len([r for r in requests if "CIK0000000111" in str(r.url)]) == 1


def test_impossible_margins_and_one_off_gains_fail():
    tech = finder.technicals(parse_chart(chart(cooled_uptrend())))
    base = {"eps_ttm": tech["price"] / 20, "revenue_growth_yoy": 12.0, "eps_growth_yoy": 10.0,
            "period_end": (TODAY - timedelta(days=60)).isoformat()}
    funds = {"OK": {**base, "net_margin": 20.0, "operating_margin": 25.0},
             "BANK": {**base, "net_margin": 20.0, "operating_margin": None},        # unknown: not flagged
             "FEES": {**base, "net_margin": 130.0, "operating_margin": None},       # revenue tag is fee income only
             "GAIN": {**base, "net_margin": 60.0, "operating_margin": 30.0}}        # investment gain in net income
    rows = [finder.candidate({"ticker": t, "name": t, "sector": "X", "cik": t}, f, tech, TODAY) for t, f in funds.items()]
    results = {r["ticker"]: r for r in finder.skill("trader-screener", "screen").screen(rows, cfg.FINDER_RULES)}
    assert results["OK"]["passed"] and results["BANK"]["passed"]
    assert results["FEES"]["fails"] == ["net_margin 130 is outside 5 to 100"]
    assert results["GAIN"]["fails"] == ["one_off_gains True, needs == False"]


def test_sec_refusal_stops_the_scan():
    with pytest.raises(finder.SecRefused):
        run_scan({}, [], sec_status=403)


def test_scan_with_nothing_readable_fails_instead_of_emptying_the_list():
    def handle(request):
        if str(request.url) == cfg.FINDER_UNIVERSE_URL:
            return httpx.Response(200, text=CSV)
        raise httpx.ConnectError("offline")

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await finder.scan(client, "Jane Doe jane@example.com", {})
    with pytest.raises(finder.FinderError, match="No company could be read"):
        asyncio.run(go())


def test_universe_falls_back_to_last_good_list(tmp_path):
    (tmp_path / "sp500.csv").write_text(CSV)

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
            return await finder.universe(client)
    assert len(asyncio.run(go())) == 5


def test_due_after_each_weekday_close():
    ny = finder.NY
    fri_close = datetime(2026, 10, 23, 16, 15, tzinfo=ny)
    assert finder.due(None, fri_close)
    scanned = (fri_close + timedelta(minutes=5)).isoformat()
    assert not finder.due(scanned, datetime(2026, 10, 24, 12, 0, tzinfo=ny))  # Saturday
    assert not finder.due(scanned, datetime(2026, 10, 26, 16, 0, tzinfo=ny))  # Monday before the close
    assert finder.due(scanned, datetime(2026, 10, 26, 16, 20, tzinfo=ny))     # Monday after the close
    assert finder.due((fri_close - timedelta(hours=1)).isoformat(), datetime(2026, 10, 25, 9, 0, tzinfo=ny))


def test_settings_validate_sec_contact():
    assert settings.update(settings.DEFAULTS, {"sec_user_agent": " Jane Doe jane@example.com "})["sec_user_agent"] == "Jane Doe jane@example.com"
    with pytest.raises(ValueError):
        settings.update(settings.DEFAULTS, {"sec_user_agent": "jane@example.com"})


def pick(ticker):
    return {"ticker": ticker, "name": ticker.title(), "pe": 20.0, "revenue_growth_yoy": 12.0, "rsi14": 48.0}


def test_station_scan_alerts_only_new_picks(monkeypatch, tmp_path):
    results = iter([{"time": "t1", "picks": [pick("AAA"), pick("BBB")], "failed": []},
                    {"time": "t2", "picks": [pick("BBB"), pick("CCC")], "failed": []}])

    async def fake_run(ua, progress):
        progress(1, 2)
        return next(results)

    monkeypatch.setattr(finder, "run", fake_run)
    s = Station()
    s.settings["sec_user_agent"] = "Jane Doe jane@example.com"

    async def go():
        assert s.start_scan() and not s.start_scan()  # one scan at a time
        await s._finder_task
        s.start_scan()
        await s._finder_task
    asyncio.run(go())
    titles = [n["title"] for n in s.notifications]
    assert titles == ["Stock finder: 2 new candidates", "Stock finder: 1 new candidate"]
    assert s.notifications[1]["body"].startswith("CCC Ccc (P/E 20, revenue +12%, RSI 48)")
    snap = s.snapshot()["finder"]
    assert snap["enabled"] and not snap["running"] and snap["result"]["time"] == "t2" and snap["result"]["failed"] == 0


def test_failed_scan_is_reported_and_not_retried_every_tick(monkeypatch):
    async def broken(ua, progress):
        raise finder.SecRefused("SEC refused the request: check the name and email in Settings")

    monkeypatch.setattr(finder, "run", broken)
    s = Station()
    s.settings["sec_user_agent"] = "Jane Doe jane@example.com"
    now = datetime.now(timezone.utc)

    async def go():
        s._maybe_scan(now)
        await s._finder_task
        s._maybe_scan(now)  # within FINDER_RETRY_SECONDS: no new attempt
        assert s._finder_task is None
    asyncio.run(go())
    assert "SEC refused" in s.errors["Stock finder"] and "SEC refused" in s.finder_status["error"]


def test_no_scan_without_sec_contact():
    s = Station()
    s._maybe_scan(datetime.now(timezone.utc))
    assert s._finder_task is None and s.snapshot()["finder"]["enabled"] is False


def test_results_survive_a_restart(tmp_path):
    finder.save({"time": "t", "picks": [pick("AAA")], "failed": []}, {"AAA": {"fetched": "2026-10-27"}})
    assert Station().finder["picks"][0]["ticker"] == "AAA"
    assert json.loads((tmp_path / "finder_fundamentals.json").read_text()) == {"AAA": {"fetched": "2026-10-27"}}
