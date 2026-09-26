from datetime import datetime, timedelta, timezone

import pytest

from station.news import dedupe, parse_ff_calendar, parse_rss
from station.sentiment import news_contributions, news_score, score_headline

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("title, gold, nasdaq", [
    # hawkish Fed / hot data -> both bearish
    ("Fed's Hammack: Underlying inflation is likely above target", -1, -1),
    ("US CPI m/m Actual 0.4% (Forecast 0.3%, Previous 0.2%)", -1, -1),
    ("Fed rules out rate cut", -1, -1),
    # dovish -> both bullish
    ("US Initial Jobless Claims Actual 250K (Forecast 230K, Previous 225K)", 1, 1),
    ("US Nonfarm Payrolls Actual 120K (Forecast 150K, Previous 140K)", 1, 1),
    # risk-off -> gold up, nasdaq down; negated -> the reverse
    ("Trump rejects Iran ceasefire: anticipates increased bombing after midterms - WSJ", 1, -1),
    ("Top Iranian security body denies plans for military action over bans on Iranian flights", -1, 1),
    ("S&P 500, Dow, Nasdaq End Week Higher On Chipmaker Strength, Signs Of Easing US-Iran Conflict", -1, 1),
    # the negator in another clause does not flip the match
    ("Iran rejects plan, launches missile at Israel", 1, -1),
    ("Gold prices tumble as dollar strengthens", -1, -1),
])
def test_headline_direction(title, gold, nasdaq):
    s = score_headline(title)
    assert (s["GOLD"] > 0) - (s["GOLD"] < 0) == gold
    assert (s["NASDAQ"] > 0) - (s["NASDAQ"] < 0) == nasdaq


@pytest.mark.parametrize("title, bitcoin", [
    ("Bitcoin surges past $120,000", 1),
    ("Bitcoin ETFs see $500 million in outflows", -1),
    ("MicroStrategy buys 10,000 bitcoin", 1),
    ("Crypto exchange hacked, $200 million stolen", -1),
    ("Fed rules out rate cut", -1),  # macro: follows risk sentiment
    ("Trump rejects Iran ceasefire: anticipates increased bombing", -1),
    ("US Initial Jobless Claims Actual 250K (Forecast 230K, Previous 225K)", 1),
])
def test_bitcoin_direction(title, bitcoin):
    b = score_headline(title)["BITCOIN"]
    assert (b > 0) - (b < 0) == bitcoin


@pytest.mark.parametrize("title", [
    "ECB's Vujcic: We have started a tightening cycle",  # non-US central bank
    "US Baker Hughes Oil Rig Count Actual 455 (Forecast -, Previous 452)",  # no forecast
    "Stocks Supported by Lower Crude Prices and Strength in Chipmakers",
    "IAU vs. AAAU: Which Physical Gold ETF Is the Better Buy for Investors?",
])
def test_neutral_headlines(title):
    s = score_headline(title)
    assert s["GOLD"] == 0 and s["NASDAQ"] == 0


def test_impact_is_clamped():
    s = score_headline("Hawkish Fed rate hike, higher for longer, hotter-than-expected inflation, dollar surges")
    assert s["GOLD"] == -3 and s["NASDAQ"] == -3


def item(title, minutes_ago, gold=0.0, nasdaq=0.0):
    return {"id": title, "source": "t", "title": title, "published": NOW - timedelta(minutes=minutes_ago),
            "impact": {"GOLD": gold, "NASDAQ": nasdaq, "tags": []}}


def test_news_score_decays_and_ignores_old_items():
    fresh = news_contributions([item("a", 0, gold=1)], "GOLD", NOW)
    half = news_contributions([item("a", 90, gold=1)], "GOLD", NOW)
    old = news_contributions([item("a", 7 * 60, gold=3)], "GOLD", NOW)
    assert news_score(fresh) == 20 and news_score(half) == 10 and news_score(old) == 0


def test_news_score_clamped_and_sorted():
    items = [item(str(i), 0, gold=3) for i in range(5)] + [item("small", 0, gold=-0.5)]
    c = news_contributions(items, "GOLD", NOW)
    assert news_score(c) == 100
    assert abs(c[0][0]) >= abs(c[-1][0])


RSS = """<rss><channel>
<item><title>FinancialJuice: Fed's Hammack: Important to have restrictive policy rates</title>
<link>https://x/1</link><pubDate>Fri, 25 Sep 2026 18:08:13 GMT</pubDate></item>
<item><title>FinancialJuice: Fed's Hammack: Important to have restrictive policy rates.</title>
<link>https://x/2</link><pubDate>Fri, 25 Sep 2026 18:08:10 GMT</pubDate></item>
<item><title></title><pubDate>Fri, 25 Sep 2026 18:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_strips_prefix_and_dedupes():
    items = parse_rss(RSS, "FinancialJuice")
    assert len(items) == 2
    assert items[0]["title"].startswith("Fed's Hammack")
    assert items[0]["impact"]["GOLD"] < 0
    assert len(dedupe(items)) == 1


def test_parse_ff_calendar_filters_usd_high_medium():
    events = [
        {"title": "CPI m/m", "country": "USD", "date": "2026-09-24T08:30:00-04:00", "impact": "High", "forecast": "0.3%", "previous": "0.2%"},
        {"title": "Bank Holiday", "country": "USD", "date": "2026-09-23T00:00:00-04:00", "impact": "Holiday"},
        {"title": "Employment Change", "country": "AUD", "date": "2026-09-23T21:30:00-04:00", "impact": "High"},
        {"title": "Claims", "country": "USD", "date": "2026-09-22T08:30:00-04:00", "impact": "Medium"},
    ]
    out = parse_ff_calendar(events)
    assert [e["title"] for e in out] == ["Claims", "CPI m/m"]
    assert out[1]["time"].utcoffset() == timedelta(hours=-4)
