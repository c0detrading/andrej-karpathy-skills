"""Background loop: fetch prices and news, score the bias, raise notifications."""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from . import config as cfg
from . import livelog, llm, settings as settings_mod, telegram
from .analysis import alignment, key_levels, reaction, volatility
from .bias import MIN_BARS, VARIANT_LABELS, accuracy, indicator_frame, next_bias, score_frame, score_timeframe, tune
from .market import fetch_bars, fetch_oanda, resample
from .news import dedupe, fetch_ff_calendar, fetch_rss
from .sentiment import news_contributions, news_score

log = logging.getLogger("station")
TICK_SECONDS = 10
EVENT_RISK_MINUTES = 30
MAX_NEWS = 200
MAX_NOTIFICATIONS = 100
NEWS_ALERT_MAX_AGE = timedelta(minutes=15)  # older headlines (e.g. a recovered feed's backlog) don't alert
CHART_BARS = 150
NY = ZoneInfo("America/New_York")


def _num(x) -> float | None:
    return None if x is None or x != x else round(float(x), 4)  # x != x catches NaN


def _arrow(units: float) -> str:
    return "▲" if units > 0 else "▼"


def _signed(x: float) -> str:
    return f"{x:+.0f}"


class Station:
    def __init__(self):
        self.settings = settings_mod.load()
        self.bars = {}            # (ticker, interval) -> DataFrame
        self.fetched_at = {}      # cache key -> monotonic time of last successful fetch
        self.news = []
        self.calendar = []
        self.errors = {}          # source -> last error message
        self.symbols = {}         # public per-asset state
        self.macro = {}           # public DXY / US10Y state
        self.macro_pressure = None  # -100..100: + means dollar and yields rising
        self.reactions = {}       # event key -> {asset: % move}
        self.briefing = None
        self.notifications = []
        self.live_records = livelog.load()
        self._next_id = 1
        self._bias = {}           # (asset, timeframe or "overall") -> BULLISH/BEARISH
        self._seen_news = None    # headline ids; None until the first fetch (no alerts for the backlog)
        self._alerted_events = set()
        self._accuracy_cache = {}
        self._outbox = []         # notifications waiting to go to Telegram
        self._briefed_on = None
        self._claude_used = (None, 0)  # (date, headlines scored that day)
        self.tuning = self._load_tuning()  # {asset: {tf: tune() result}}
        self.version = 0          # bumped after every tick; the live stream waits on it
        self.updated = asyncio.Event()

    @property
    def assets(self) -> dict:
        return settings_mod.assets(self.settings)

    def update_settings(self, changes: dict):
        self.settings = settings_mod.update(self.settings, changes)
        settings_mod.save(self.settings)
        self.symbols = {k: v for k, v in self.symbols.items() if k in self.assets}

    # ---- fetching -------------------------------------------------------

    def _due(self, key, ttl: float) -> bool:
        return time.monotonic() - self.fetched_at.get(key, float("-inf")) >= ttl

    async def _fetch(self, client, ticker: str, interval: str, range_: str):
        key = (ticker, interval)
        if not self._due(key, cfg.REFRESH_SECONDS[interval]):
            return
        label = f"{'OANDA' if ticker.startswith('oanda:') else 'Yahoo'} {ticker.removeprefix('oanda:')} {interval}"
        try:
            if ticker.startswith("oanda:"):
                self.bars[key] = await fetch_oanda(client, self.settings["oanda_token"], self.settings["oanda_env"],
                                                   ticker.removeprefix("oanda:"), interval)
            else:
                self.bars[key] = await fetch_bars(client, ticker, interval, range_)
            self.fetched_at[key] = time.monotonic()
            self.errors.pop(label, None)
        except Exception as e:  # network/HTTP/parse: keep last good data, show the error
            self.errors[label] = str(e)[:200]

    async def _refresh_market(self, client):
        intervals = {(i, r) for i, r, _ in cfg.TIMEFRAMES.values()}
        for a in self.assets.values():
            for interval, range_ in intervals:
                await self._fetch(client, a["src"], interval, range_)
        for m in cfg.MACRO.values():
            for interval, range_ in intervals:
                if interval in ("60m", "1d"):
                    await self._fetch(client, m["ticker"], interval, range_)

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
            new = self._merge_news(fresh)
            await self._claude_rescore(new)
            self._alert_news(new, datetime.now(timezone.utc))
        if self._due("ff", cfg.FF_REFRESH_SECONDS):
            try:
                self.calendar = await fetch_ff_calendar(client, cfg.FF_CALENDAR_URL)
                self.fetched_at["ff"] = time.monotonic()
                self.errors.pop("Forex Factory", None)
            except Exception as e:
                self.errors["Forex Factory"] = str(e)

    def _merge_news(self, fresh: list[dict]) -> list[dict]:
        """Add fresh headlines; return the ones not seen before (none on the first fetch)."""
        known = {i["id"] for i in self.news}
        self.news = dedupe(self.news + [i for i in fresh if i["id"] not in known])[:MAX_NEWS]
        if self._seen_news is None:
            self._seen_news = {i["id"] for i in self.news}
            return []
        new = [i for i in reversed(self.news) if i["id"] not in self._seen_news]
        self._seen_news.update(i["id"] for i in new)
        return new

    async def _claude_rescore(self, items: list[dict]):
        key = self.settings["anthropic_api_key"]
        if not (self.settings["claude_scoring"] and key and items):
            return
        today = datetime.now(timezone.utc).date()
        day, used = self._claude_used
        used = used if day == today else 0
        batch = [i for i in items if llm.worth_scoring(i)][: min(cfg.CLAUDE_BATCH_SIZE, cfg.CLAUDE_DAILY_HEADLINE_CAP - used)]
        if not batch:
            return
        try:
            scores = await llm.score(key, batch)
            self.errors.pop("Claude", None)
        except Exception as e:
            self.errors["Claude"] = f"{type(e).__name__}: {e}"[:200]
            return
        self._claude_used = (today, used + len(batch))
        for item in batch:
            if item["id"] in scores:
                item["impact_rules"] = item["impact"]
                item["impact"] = scores[item["id"]]

    def _alert_news(self, items: list[dict], now: datetime):
        for item in items:
            if now - item["published"] > NEWS_ALERT_MAX_AGE:
                continue
            moves = {s: u for s, u in item["impact"].items() if s in cfg.NEWS_PROFILES and abs(u) >= cfg.NEWS_ALERT_IMPACT}
            if moves:
                what = " · ".join(f"{s.title()} {_arrow(u)}" for s, u in moves.items())
                self._notify("news", f"{item['source']}: {what}", item["title"])

    # ---- scoring --------------------------------------------------------

    def _frame(self, ticker: str, tf: str, cme: bool) -> pd.DataFrame | None:
        interval, _, rule = cfg.TIMEFRAMES[tf]
        df = self.bars.get((ticker, interval))
        if df is not None and rule:
            df = resample(df, rule, cme)
        return df

    def _accuracy(self, ticker: str, tf: str, variant: str, df: pd.DataFrame, frame: pd.DataFrame) -> dict | None:
        key = (ticker, tf, variant, len(df), df.index[-1])
        if key not in self._accuracy_cache:
            h = cfg.ACCURACY_HORIZON_BARS[tf]
            result = accuracy(df["close"], frame["score"], h)
            self._accuracy_cache = {k: v for k, v in self._accuracy_cache.items() if k[:2] != (ticker, tf)}
            self._accuracy_cache[key] = result and {**result, "horizon": h}
        return self._accuracy_cache[key]

    # ---- model tuning -----------------------------------------------------

    def _load_tuning(self) -> dict:
        try:
            return json.loads((settings_mod.DATA_DIR / "tuning.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def variant(self, asset: str, tf: str) -> str:
        if not self.settings["use_tuning"]:
            return "default"
        return self.tuning.get(asset, {}).get(tf, {}).get("variant", "default")

    def retune(self) -> dict:
        """Re-run the walk-forward model choice for every asset and timeframe with data."""
        tuning = {k: dict(v) for k, v in self.tuning.items()}
        for name, a in self.assets.items():
            for tf in cfg.TIMEFRAMES:
                df = self._frame(a["src"], tf, a["cme"])
                if df is None or len(df) < MIN_BARS * 2:
                    continue
                result = tune(df, cfg.ACCURACY_HORIZON_BARS[tf])
                if result:
                    tuning.setdefault(name, {})[tf] = {**result, "tuned_at": datetime.now(timezone.utc).isoformat()}
        self.tuning = tuning  # swapped in whole, so the tick loop never sees a half-built table
        settings_mod.DATA_DIR.mkdir(exist_ok=True)
        (settings_mod.DATA_DIR / "tuning.json").write_text(json.dumps(self.tuning, indent=1))
        self.fetched_at["tune"] = time.monotonic()
        return self.tuning

    def _maybe_tune(self):
        have_data = all((a["src"], "1d") in self.bars for a in self.assets.values())
        if have_data and self._due("tune", cfg.TUNE_EVERY_HOURS * 3600):
            stale = [t.get("tuned_at", "") for per in self.tuning.values() for t in per.values()]
            fresh_enough = stale and min(stale) > (datetime.now(timezone.utc) - timedelta(hours=cfg.TUNE_EVERY_HOURS)).isoformat()
            if fresh_enough and set(self.tuning) >= set(self.assets):
                self.fetched_at["tune"] = time.monotonic()  # loaded from disk and still current
            else:
                self.retune()

    def _recompute_macro(self):
        pressures = []
        for key, m in cfg.MACRO.items():
            scores = {}
            for tf in cfg.MACRO_TIMEFRAME_WEIGHTS:
                df = self._frame(m["ticker"], tf, True)
                res = score_timeframe(df) if df is not None else None
                if res:
                    scores[tf] = res["score"]
            if not scores:
                continue
            w = sum(cfg.MACRO_TIMEFRAME_WEIGHTS[tf] for tf in scores)
            combined = round(sum(cfg.MACRO_TIMEFRAME_WEIGHTS[tf] * s for tf, s in scores.items()) / w, 1)
            pressures.append(combined)
            self.macro[key] = {
                "name": m["name"], "ticker": m["ticker"], "price": self._price(m["ticker"], "60m"),
                "score": combined, "direction": "RISING" if combined >= 0 else "FALLING", "timeframes": scores,
            }
        self.macro_pressure = round(sum(pressures) / len(pressures), 1) if pressures else None

    def _recompute(self, now: datetime):
        for name, a in self.assets.items():
            frames = {}
            for tf in cfg.TIMEFRAMES:
                df = self._frame(a["src"], tf, a["cme"])
                if df is None or len(df) < MIN_BARS:
                    continue
                variant = self.variant(name, tf)
                frame = score_frame(df, variant, indicator_frame(df))
                res = score_timeframe(df, frame)
                bias = self._set_bias(name, tf, res["score"], f"{a['name']} {tf}")
                frames[tf] = {
                    "bias": bias,
                    "strength": "strong" if abs(res["score"]) >= cfg.WEAK_THRESHOLD else "weak",
                    "model": variant,
                    "model_label": VARIANT_LABELS[variant],
                    "counted": cfg.TIMEFRAME_WEIGHTS[tf] > 0,
                    "score": res["score"],
                    "votes": res["votes"],
                    "values": {k: _num(v) for k, v in res["values"].items()},
                    "bar_time": df.index[-1].isoformat(),
                    "accuracy": self._accuracy(a["src"], tf, variant, df, frame),
                }
            if not frames:
                continue

            weight = sum(cfg.TIMEFRAME_WEIGHTS[tf] for tf in frames)
            if not weight:
                continue  # only uncounted timeframes (1m) have data so far
            technical = sum(cfg.TIMEFRAME_WEIGHTS[tf] * f["score"] for tf, f in frames.items()) / weight
            contributions = news_contributions(self.news, a["news"], now) if a["news"] else []
            news = news_score(contributions)
            macro = round(a["macro"] * self.macro_pressure, 1) if self.macro_pressure is not None else 0.0
            overall = round(cfg.TECH_WEIGHT * technical + cfg.NEWS_WEIGHT * news + cfg.MACRO_WEIGHT * macro, 1)
            drivers = [{"points": round(p, 1), "title": i["title"], "source": i["source"], "related": n - 1}
                       for p, i, n in contributions[:3]]
            bias = self._set_bias(name, "overall", overall, f"{a['name']} daily", technical, news, macro, drivers)

            price = self._price(a["src"])
            daily = self.bars.get((a["src"], "1d"))
            read = alignment(frames)
            if abs(macro) >= 30 and (macro > 0) != (bias == "BULLISH"):
                moving = "rising" if (self.macro_pressure or 0) > 0 else "falling"
                read += f" Macro headwind: dollar and yields {moving}, against this bias."
            atr_1h = frames.get("1h", {}).get("values", {}).get("atr")
            self.symbols[name] = {
                "name": a["name"],
                "ticker": a["ticker"],
                "source": "OANDA (real-time)" if a["src"].startswith("oanda:") else "Yahoo (may be delayed)",
                "price": price,
                "bias": bias,
                "strength": "strong" if abs(overall) >= cfg.WEAK_THRESHOLD else "weak",
                "score": overall,
                "technical": round(technical, 1),
                "news": news,
                "macro": macro,
                "news_profile": a["news"],
                "drivers": drivers,
                "timeframes": frames,
                "read": read,
                "volatility": volatility(daily),
                "levels": key_levels(daily, self.bars.get((a["src"], "15m")), price["last"], atr_1h, a["cme"]),
                "live_record": livelog.grade(self.live_records, name, self._daily_by_date(daily, a["cme"]),
                                             now.astimezone(NY).date().isoformat()),
            }

    @staticmethod
    def _daily_by_date(daily, cme: bool):
        """Daily bars re-indexed so .date() is the trading day (Yahoo dates crypto days in UTC)."""
        if daily is None or cme:
            return daily
        return daily.set_axis(daily.index.tz_convert("UTC"))

    def _price(self, ticker: str, interval: str = "1m") -> dict:
        intraday, daily = self.bars.get((ticker, interval)), self.bars.get((ticker, "1d"))
        last = intraday["close"].iloc[-1] if intraday is not None and len(intraday) else None
        prev = daily["close"].iloc[-2] if daily is not None and len(daily) > 1 else None
        change = (last / prev - 1) * 100 if last is not None and prev else None
        return {"last": _num(last), "change_pct": _num(change)}

    def _set_bias(self, asset, tf, score, label, technical=None, news=None, macro=None, drivers=None) -> str:
        key = (asset, tf)
        prev = self._bias.get(key)
        bias = next_bias(score, prev)
        self._bias[key] = bias
        if prev is None or prev == bias:
            return bias
        if tf == "overall":
            body = f"Score {score:+.0f} (technical {technical:+.0f}, news {news:+.0f}, macro {macro:+.0f})."
            if (technical >= 0) != (bias == "BULLISH") and drivers:
                body += f" News-driven: {drivers[0]['title']}"
            self._notify("bias", f"{label} bias → {bias}", body)
        elif tf in cfg.ALERT_TIMEFRAMES:
            self._notify("timeframe", f"{label} → {bias}", f"Score {score:+.0f}")
        return bias

    # ---- calendar, reactions, daily record, briefing ----------------------

    @staticmethod
    def _event_key(e: dict) -> str:
        return f"{e['title']}|{e['time'].isoformat()}"

    def _check_calendar(self, now: datetime):
        for e in self.calendar:
            key = self._event_key(e)
            minutes = (e["time"] - now).total_seconds() / 60
            if e["impact"] == "High" and 0 <= minutes <= cfg.FF_ALERT_MINUTES and key not in self._alerted_events:
                self._alerted_events.add(key)
                detail = ", ".join(f"{k} {e[k]}" for k in ("forecast", "previous") if e[k])
                self._notify("calendar", f"In {minutes:.0f} min: {e['country']} {e['title']}", detail or "High impact")

    def _check_reactions(self, now: datetime):
        """Measure each asset's move in the minutes after a high-impact release."""
        for e in self.calendar:
            key = self._event_key(e)
            done_at = e["time"] + timedelta(minutes=cfg.REACTION_MINUTES + 1)
            if e["impact"] != "High" or key in self.reactions or not (done_at <= now <= e["time"] + timedelta(days=5)):
                continue
            moves = {name: reaction(self.bars.get((a["src"], "1m")), e["time"], cfg.REACTION_MINUTES)
                     for name, a in self.assets.items()}
            self.reactions[key] = moves
            shown = {k: v for k, v in moves.items() if v is not None}
            if shown and now - e["time"] <= timedelta(hours=2):
                what = " · ".join(f"{self.assets[k]['name']} {v:+.2f}%" for k, v in shown.items())
                self._notify("reaction", f"{e['country']} {e['title']}: {cfg.REACTION_MINUTES}-min reaction", what)

    def _live_log(self, now: datetime):
        """Once per weekday, between the New York open and noon, record every asset's bias."""
        ny = now.astimezone(NY)
        if ny.weekday() >= 5 or not (cfg.LIVE_LOG_TIME_NY <= ny.strftime("%H:%M") < "12:00"):
            return
        date = ny.date().isoformat()
        logged = {(r["date"], r["asset"]) for r in self.live_records}
        for name, s in self.symbols.items():
            if (date, name) in logged or s["price"]["last"] is None:
                continue
            record = {"date": date, "time": ny.strftime("%H:%M"), "asset": name,
                      "bias": s["bias"], "score": s["score"], "price": s["price"]["last"]}
            livelog.append(record)
            self.live_records.append(record)

    def build_briefing(self, now: datetime) -> dict:
        local = now.astimezone()
        lines = [f"ONYX briefing · {local.strftime('%a %d %b %Y %H:%M')}"]
        for s in self.symbols.values():
            lines.append("")
            lines.append(f"{s['name']}: {s['bias']} ({_signed(s['score'])}) · technical {_signed(s['technical'])}, "
                         f"news {_signed(s['news'])}, macro {_signed(s['macro'])}")
            lines.append(f"  {s['read']}")
            if s["volatility"]:
                v = s["volatility"]
                lines.append(f"  Volatility {v['regime']}: {v['range_used_pct']}% of daily ATR used")
            near = sorted(s["levels"], key=lambda lv: abs(lv["distance_pct"]))[:2]
            if near:
                lines.append("  Nearest levels: " + ", ".join(
                    f"{lv['name']} {lv['price']:g} ({abs(lv['distance_pct']):.2f}% {'above' if lv['distance_pct'] < 0 else 'below'})"
                    for lv in near))
            if s["drivers"]:
                lines.append(f"  Top news: {s['drivers'][0]['title']}")
        if self.macro:
            lines.append("")
            lines.append("Macro: " + ", ".join(f"{m['name']} {m['direction'].lower()} ({_signed(m['score'])})" for m in self.macro.values()))
        today = [e for e in self.calendar if e["time"].astimezone().date() == local.date() and e["impact"] == "High"]
        if today:
            lines.append("")
            lines.append("High-impact events today:")
            lines += [f"  {e['time'].astimezone().strftime('%H:%M')} {e['country']} {e['title']}"
                      + (f" (F {e['forecast']}, P {e['previous']})" if e["forecast"] else "") for e in today]
        return {"time": now.isoformat(), "text": "\n".join(lines)}

    def _maybe_brief(self, now: datetime):
        at = self.settings["briefing_time"]
        local = now.astimezone()
        if not at or not self.symbols or self._briefed_on == local.date() or local.strftime("%H:%M") < at:
            return
        self._briefed_on = local.date()
        self.briefing = self.build_briefing(now)
        self._notify("briefing", "ONYX morning briefing", self.briefing["text"])

    # ---- notifications ----------------------------------------------------

    def _notify(self, kind: str, title: str, body: str):
        log.info("notify [%s] %s — %s", kind, title, body)
        n = {"id": self._next_id, "kind": kind, "title": title, "body": body,
             "time": datetime.now(timezone.utc).isoformat()}
        self.notifications.append(n)
        self._outbox.append(n)
        self._next_id += 1
        del self.notifications[:-MAX_NOTIFICATIONS]

    async def _flush_telegram(self, client):
        token, chat = self.settings["telegram_token"], self.settings["telegram_chat_id"]
        if not (token and chat):
            self._outbox.clear()
            return
        while self._outbox:
            n = self._outbox[0]
            try:
                await telegram.send(client, token, chat, f"{n['title']}\n{n['body']}")
                self.errors.pop("Telegram", None)
            except Exception as e:
                self.errors["Telegram"] = str(e)
                return  # keep it queued; retry next tick
            self._outbox.pop(0)

    async def send_test_telegram(self):
        async with httpx.AsyncClient(timeout=15) as client:
            await telegram.send(client, self.settings["telegram_token"], self.settings["telegram_chat_id"],
                                "ONYX test message: Telegram alerts are working.")

    # ---- loop / API -----------------------------------------------------

    async def tick(self, client):
        await self._refresh_news(client)
        await self._refresh_market(client)
        now = datetime.now(timezone.utc)
        self._recompute_macro()
        self._recompute(now)
        self._check_calendar(now)
        self._check_reactions(now)
        self._live_log(now)
        self._maybe_brief(now)
        self._maybe_tune()
        await self._flush_telegram(client)
        self.version += 1
        self.updated.set()
        self.updated = asyncio.Event()

    async def run(self):
        async with httpx.AsyncClient(headers=cfg.HTTP_HEADERS, timeout=15, follow_redirects=True) as client:
            while True:
                try:
                    await self.tick(client)
                except Exception:
                    log.exception("tick failed")
                await asyncio.sleep(TICK_SECONDS)

    def chart(self, asset: str, tf: str) -> dict | None:
        a = self.assets.get(asset)
        df = self._frame(a["src"], tf, a["cme"]) if a and tf in cfg.TIMEFRAMES else None
        if df is None or len(df) < MIN_BARS:
            return None
        v = score_frame(df)["values"].iloc[-CHART_BARS:]
        bars = df.iloc[-CHART_BARS:]
        col = lambda s: [_num(x) for x in s]
        return {
            "t": [t.isoformat() for t in bars.index],
            "open": col(bars["open"]), "high": col(bars["high"]), "low": col(bars["low"]), "close": col(bars["close"]),
            "ema20": col(v["ema20"]), "ema50": col(v["ema50"]), "ema200": col(v["ema200"]),
            "bb_upper": col(v["bb_upper"]), "bb_lower": col(v["bb_lower"]),
        }

    def snapshot(self) -> dict:
        now = datetime.now(timezone.utc)
        risk = next((e for e in self.calendar if e["impact"] == "High"
                     and abs(e["time"] - now) <= timedelta(minutes=EVENT_RISK_MINUTES)), None)
        return {
            "time": now.isoformat(),
            "symbols": {k: self.symbols[k] for k in self.assets if k in self.symbols},
            "macro": self.macro,
            "macro_pressure": self.macro_pressure,
            "news": [{k: v for k, v in i.items() if k != "summary"} | {"published": i["published"].isoformat()}
                     for i in self.news],
            "calendar": [{**e, "time": e["time"].isoformat(), "reaction": self.reactions.get(self._event_key(e))}
                         for e in self.calendar],
            "event_risk": risk and {**risk, "time": risk["time"].isoformat()},
            "briefing": self.briefing,
            "notifications": self.notifications,
            "errors": self.errors,
            "timeframes": list(cfg.TIMEFRAMES),
            "asset_names": {k: a["name"] for k, a in self.assets.items()},
            "features": {
                "telegram": bool(self.settings["telegram_token"] and self.settings["telegram_chat_id"]),
                "claude": bool(self.settings["claude_scoring"] and self.settings["anthropic_api_key"]),
            },
        }

