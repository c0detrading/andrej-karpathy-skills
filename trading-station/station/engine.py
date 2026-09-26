"""Background loop: fetch prices and news, score the bias, raise notifications."""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import config as cfg
from .bias import next_bias, score_timeframe
from .market import fetch_bars, resample
from .news import dedupe, fetch_ff_calendar, fetch_rss
from .sentiment import news_contributions, news_score

log = logging.getLogger("station")
TICK_SECONDS = 10
EVENT_RISK_MINUTES = 30
MAX_NEWS = 200
MAX_NOTIFICATIONS = 100
NEWS_ALERT_MAX_AGE = timedelta(minutes=15)  # older headlines (e.g. a recovered feed's backlog) don't alert


def _num(x) -> float | None:
    return None if x is None or x != x else round(float(x), 4)  # x != x catches NaN


def _arrow(units: float) -> str:
    return "▲" if units > 0 else "▼"


class Station:
    def __init__(self):
        self.bars = {}            # (ticker, interval) -> DataFrame
        self.fetched_at = {}      # cache key -> monotonic time of last successful fetch
        self.news = []
        self.calendar = []
        self.errors = {}          # source -> last error message
        self.symbols = {}         # public per-symbol state
        self.notifications = []
        self._next_id = 1
        self._bias = {}           # (symbol, timeframe or "overall") -> BULLISH/BEARISH
        self._seen_news = None    # headline ids; None until the first fetch (no alerts for the backlog)
        self._alerted_events = set()

    # ---- fetching -------------------------------------------------------

    def _due(self, key, ttl: float) -> bool:
        return time.monotonic() - self.fetched_at.get(key, float("-inf")) >= ttl

    async def _refresh_market(self, client):
        intervals = {(i, r) for i, r, _ in cfg.TIMEFRAMES.values()}
        for sym in cfg.SYMBOLS.values():
            for interval, range_ in intervals:
                key = (sym["ticker"], interval)
                if not self._due(key, cfg.REFRESH_SECONDS[interval]):
                    continue
                try:
                    self.bars[key] = await fetch_bars(client, sym["ticker"], interval, range_)
                    self.fetched_at[key] = time.monotonic()
                    self.errors.pop(f"Yahoo {key[0]} {interval}", None)
                except Exception as e:  # network/HTTP/parse: keep last good data, show the error
                    self.errors[f"Yahoo {key[0]} {interval}"] = str(e)

    async def _refresh_news(self, client):
        if self._due("news", cfg.NEWS_REFRESH_SECONDS):
            fresh = []
            for source, url in cfg.NEWS_FEEDS.items():
                try:
                    fresh += await fetch_rss(client, url, source)
                    self.errors.pop(source, None)
                except Exception as e:
                    self.errors[source] = str(e)
            self.fetched_at["news"] = time.monotonic()
            self._merge_news(fresh, datetime.now(timezone.utc))
        if self._due("ff", cfg.FF_REFRESH_SECONDS):
            try:
                self.calendar = await fetch_ff_calendar(client, cfg.FF_CALENDAR_URL)
                self.fetched_at["ff"] = time.monotonic()
                self.errors.pop("Forex Factory", None)
            except Exception as e:
                self.errors["Forex Factory"] = str(e)

    def _merge_news(self, fresh: list[dict], now: datetime):
        known = {i["id"] for i in self.news}
        self.news = dedupe(self.news + [i for i in fresh if i["id"] not in known])[:MAX_NEWS]
        if self._seen_news is None:
            self._seen_news = {i["id"] for i in self.news}
            return
        for item in reversed(self.news):
            if item["id"] in self._seen_news:
                continue
            self._seen_news.add(item["id"])
            if now - item["published"] > NEWS_ALERT_MAX_AGE:
                continue
            moves = {s: u for s, u in item["impact"].items() if s in cfg.SYMBOLS and abs(u) >= cfg.NEWS_ALERT_IMPACT}
            if moves:
                what = " · ".join(f"{s.title()} {_arrow(u)}" for s, u in moves.items())
                self._notify("news", f"{item['source']}: {what}", item["title"])

    # ---- scoring --------------------------------------------------------

    def _recompute(self, now: datetime):
        for name, sym in cfg.SYMBOLS.items():
            frames = {}
            for tf, (interval, _, rule) in cfg.TIMEFRAMES.items():
                df = self.bars.get((sym["ticker"], interval))
                if df is None:
                    continue
                if rule:
                    df = resample(df, rule)
                res = score_timeframe(df)
                if res is None:
                    continue
                bias = self._set_bias(name, tf, res["score"], f"{sym['name']} {tf}")
                frames[tf] = {
                    "bias": bias,
                    "score": res["score"],
                    "votes": res["votes"],
                    "values": {k: _num(v) for k, v in res["values"].items()},
                    "bar_time": df.index[-1].isoformat(),
                }
            if not frames:
                continue

            weight = sum(cfg.TIMEFRAME_WEIGHTS[tf] for tf in frames)
            technical = sum(cfg.TIMEFRAME_WEIGHTS[tf] * f["score"] for tf, f in frames.items()) / weight
            contributions = news_contributions(self.news, name, now)
            news = news_score(contributions)
            overall = round((1 - cfg.NEWS_WEIGHT) * technical + cfg.NEWS_WEIGHT * news, 1)
            drivers = [{"points": round(p, 1), "title": i["title"], "source": i["source"]} for p, i in contributions[:3]]
            bias = self._set_bias(name, "overall", overall, f"{sym['name']} daily", technical, news, drivers)

            self.symbols[name] = {
                "name": sym["name"],
                "ticker": sym["ticker"],
                "price": self._price(sym["ticker"]),
                "bias": bias,
                "score": overall,
                "technical": round(technical, 1),
                "news": news,
                "drivers": drivers,
                "timeframes": frames,
            }

    def _price(self, ticker: str) -> dict:
        intraday, daily = self.bars.get((ticker, "1m")), self.bars.get((ticker, "1d"))
        last = intraday["close"].iloc[-1] if intraday is not None and len(intraday) else None
        prev = daily["close"].iloc[-2] if daily is not None and len(daily) > 1 else None
        change = (last / prev - 1) * 100 if last is not None and prev else None
        return {"last": _num(last), "change_pct": _num(change)}

    def _set_bias(self, symbol, tf, score, label, technical=None, news=None, drivers=None) -> str:
        key = (symbol, tf)
        prev = self._bias.get(key)
        bias = next_bias(score, prev)
        self._bias[key] = bias
        if prev is None or prev == bias:
            return bias
        if tf == "overall":
            body = f"Score {score:+.0f} (technical {technical:+.0f}, news {news:+.0f})."
            if (technical >= 0) != (bias == "BULLISH") and drivers:
                body += f" News-driven: {drivers[0]['title']}"
            self._notify("bias", f"{label} bias → {bias}", body)
        elif tf in cfg.ALERT_TIMEFRAMES:
            self._notify("timeframe", f"{label} → {bias}", f"Score {score:+.0f}")
        return bias

    def _check_calendar(self, now: datetime):
        for e in self.calendar:
            key = (e["title"], e["time"].isoformat())
            minutes = (e["time"] - now).total_seconds() / 60
            if e["impact"] == "High" and 0 <= minutes <= cfg.FF_ALERT_MINUTES and key not in self._alerted_events:
                self._alerted_events.add(key)
                detail = ", ".join(f"{k} {e[k]}" for k in ("forecast", "previous") if e[k])
                self._notify("calendar", f"In {minutes:.0f} min: {e['country']} {e['title']}", detail or "High impact")

    def _notify(self, kind: str, title: str, body: str):
        log.info("notify [%s] %s — %s", kind, title, body)
        self.notifications.append({
            "id": self._next_id, "kind": kind, "title": title, "body": body,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        self._next_id += 1
        del self.notifications[:-MAX_NOTIFICATIONS]

    # ---- loop / API -----------------------------------------------------

    async def tick(self, client):
        await self._refresh_news(client)
        await self._refresh_market(client)
        now = datetime.now(timezone.utc)
        self._recompute(now)
        self._check_calendar(now)

    async def run(self):
        async with httpx.AsyncClient(headers=cfg.HTTP_HEADERS, timeout=15, follow_redirects=True) as client:
            while True:
                try:
                    await self.tick(client)
                except Exception:
                    log.exception("tick failed")
                await asyncio.sleep(TICK_SECONDS)

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        risk = next((e for e in self.calendar if e["impact"] == "High"
                     and abs(e["time"] - now) <= timedelta(minutes=EVENT_RISK_MINUTES)), None)
        return {
            "time": now.isoformat(),
            "symbols": self.symbols,
            "news": [{**i, "published": i["published"].isoformat()} for i in self.news],
            "calendar": [{**e, "time": e["time"].isoformat()} for e in self.calendar],
            "event_risk": risk and {**risk, "time": risk["time"].isoformat()},
            "notifications": self.notifications,
            "errors": self.errors,
            "timeframes": list(cfg.TIMEFRAMES),
        }
