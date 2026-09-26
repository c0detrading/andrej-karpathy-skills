import numpy as np
import pandas as pd
import pytest

from station import indicators as ind
from station.bias import next_bias, score_timeframe
from station.market import parse_chart, resample


def bars(close, freq="1min"):
    close = pd.Series(close, dtype=float)
    idx = pd.date_range("2026-09-01 18:00", periods=len(close), freq=freq, tz="America/New_York")
    return pd.DataFrame({"open": close.values, "high": close.values + 1, "low": close.values - 1,
                         "close": close.values, "volume": 1.0}, index=idx)


def test_ema_of_constant_is_constant():
    assert ind.ema(pd.Series([5.0] * 50), 20).iloc[-1] == pytest.approx(5.0)


def test_rsi_extremes():
    assert ind.rsi(pd.Series(np.arange(1, 60, dtype=float))).iloc[-1] == 100
    assert ind.rsi(pd.Series(np.arange(60, 1, -1, dtype=float))).iloc[-1] == pytest.approx(0)


def test_bollinger_mid_and_pct_b():
    close = pd.Series([1.0, 3.0] * 10)
    bb = ind.bollinger(close).iloc[-1]
    assert bb["mid"] == pytest.approx(2.0)
    # std (ddof=0) is 1, so bands are 0..4 and the last close 3 sits at %B 0.75
    assert bb["pct_b"] == pytest.approx(0.75)


def test_uptrend_scores_bullish_downtrend_bearish():
    up = score_timeframe(bars(np.linspace(100, 200, 300)))
    down = score_timeframe(bars(np.linspace(200, 100, 300)))
    assert up["score"] > 90 and down["score"] < -90
    assert next_bias(up["score"], None) == "BULLISH"
    assert next_bias(down["score"], None) == "BEARISH"


def test_needs_200_bars():
    assert score_timeframe(bars(np.linspace(100, 200, 199))) is None


def test_hysteresis_keeps_previous_bias_near_zero():
    assert next_bias(5, "BEARISH") == "BEARISH"
    assert next_bias(-5, "BULLISH") == "BULLISH"
    assert next_bias(10, "BEARISH") == "BULLISH"
    assert next_bias(-10, "BULLISH") == "BEARISH"
    assert next_bias(-3, None) == "BEARISH"


def test_4h_bins_start_at_cme_session_open():
    df = bars(np.arange(48, dtype=float), freq="1h")  # starts 18:00 NY
    out = resample(df, "4h")
    assert [t.hour for t in out.index[:6]] == [18, 22, 2, 6, 10, 14]
    assert out["open"].iloc[0] == 0 and out["close"].iloc[0] == 3
    assert out["high"].iloc[0] == 4 and out["low"].iloc[0] == -1


def test_4h_bins_for_24_7_markets_start_at_utc_midnight():
    df = bars(np.arange(48, dtype=float), freq="1h")  # 18:00 NY == 22:00 UTC
    out = resample(df, "4h", cme=False)
    assert [t.tz_convert("UTC").hour for t in out.index[:3]] == [20, 0, 4]
    assert str(out.index.tz) == "America/New_York"


def test_parse_chart_drops_empty_bars():
    payload = {"chart": {"result": [{"timestamp": [1790370000, 1790370060], "indicators": {"quote": [
        {"open": [1, None], "high": [2, None], "low": [0.5, None], "close": [1.5, None], "volume": [10, None]}]}}]}}
    df = parse_chart(payload)
    assert len(df) == 1 and df["close"].iloc[0] == 1.5
    assert str(df.index.tz) == "America/New_York"


def test_accuracy_counts_hits_against_future_price():
    from station.bias import accuracy
    close = pd.Series(np.linspace(100, 200, 400))
    assert accuracy(close, pd.Series([50.0] * 400), 5)["hit_rate"] == 100
    assert accuracy(close, pd.Series([-50.0] * 400), 5)["hit_rate"] == 0
    assert accuracy(close[:150], pd.Series([50.0] * 150), 5) is None


def test_evaluate_edge_and_strong_split():
    from station.bias import evaluate
    s = pd.DataFrame({"i": range(4), "direction": [1, 1, -1, -1], "fwd_pct": [0.2, -0.1, -0.3, 0.1],
                      "score": [50, 5, -50, -5]})
    e = evaluate(s)
    assert e["n"] == 4 and e["hit_rate"] == 50
    assert e["edge_pct"] == pytest.approx((0.2 - 0.1 + 0.3 - 0.1) / 4)
    assert e["strong_n"] == 2 and e["strong_hit_rate"] == 100  # the two |score| >= 20 calls were right
    assert e["bull_avg_pct"] == pytest.approx(0.05) and e["bear_avg_pct"] == pytest.approx(-0.1)


def test_tune_keeps_default_unless_alternative_wins_out_of_sample():
    from station.bias import tune
    # A zig-zag market: trend-following loses, fading wins, both in and out of sample.
    t = np.arange(1500)
    close = 100 + 5 * np.sin(t / 8)
    df = bars(close)
    result = tune(df, horizon=8)
    assert set(result["results"]) >= {"default", "contrarian", "trend"}
    assert result["variant"] == result["best_on_train"]
    chosen = result["results"][result["variant"]]["test"]["edge_pct"]
    assert chosen > result["results"]["default"]["test"]["edge_pct"] and chosen >= 0.01
    # A steady uptrend: the default already wins, so nothing is switched.
    assert tune(bars(np.linspace(100, 200, 1500)), horizon=8)["variant"] in ("default", "trend", "momentum", "adx-filter")


def test_parse_oanda_candles():
    from station.market import parse_oanda
    df = parse_oanda({"candles": [
        {"complete": True, "volume": 10, "time": "2026-09-25T13:00:00.000000000Z", "mid": {"o": "1.1", "h": "1.3", "l": "1.0", "c": "1.2"}},
        {"complete": False, "volume": 3, "time": "2026-09-25T13:01:00.000000000Z", "mid": {"o": "1.2", "h": "1.25", "l": "1.15", "c": "1.22"}},
    ]})
    assert list(df["close"]) == [1.2, 1.22] and str(df.index.tz) == "America/New_York"
    assert df.index[0].hour == 9  # 13:00 UTC is 09:00 New York (EDT)
