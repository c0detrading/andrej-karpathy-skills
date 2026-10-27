"""Stock finder: scan the S&P 500 for quality companies whose uptrend has cooled off.

Fundamentals are read from SEC filings by the trader-analyst skill (facts.py) and the shortlist is
ranked by the trader-screener skill (screen.py). Both live in .claude/skills at the repo root.
A screen is a filter on reported numbers and prices, not a recommendation.
"""

import asyncio
import csv
import importlib.util
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from . import config as cfg
from . import settings as settings_mod
from .indicators import ema, rsi
from .market import fetch_bars

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
NY = ZoneInfo("America/New_York")
_skills = {}


class FinderError(Exception):
    pass


class SecRefused(FinderError):
    """SEC blocks every request without a real name and email: stop the scan, don't fail 500 companies."""


def skill(folder: str, module: str):
    """Load a trader skill's Python tool as a module (once)."""
    if module not in _skills:
        path = SKILLS_DIR / folder / f"{module}.py"
        if not path.is_file():
            raise FinderError(f"Trader skill not found at {path}")
        spec = importlib.util.spec_from_file_location(f"trader_{module}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _skills[module] = mod
    return _skills[module]


# ---- inputs -------------------------------------------------------------------

def parse_constituents(text: str) -> list[dict]:
    """The S&P 500 list (datasets/s-and-p-500-companies CSV) as ticker, name, sector and CIK."""
    out = [{"ticker": r["Symbol"].strip().upper(), "name": r["Security"].strip(), "sector": r["GICS Sector"].strip(),
            "cik": r["CIK"].strip().zfill(10)}
           for r in csv.DictReader(io.StringIO(text)) if r.get("Symbol") and r.get("CIK")]
    if not out:
        raise FinderError("The S&P 500 list is empty")
    return out


async def universe(client) -> list[dict]:
    """Today's S&P 500 list; the last good copy if the download fails."""
    path = settings_mod.DATA_DIR / "sp500.csv"
    try:
        resp = await client.get(cfg.FINDER_UNIVERSE_URL)
        resp.raise_for_status()
        companies = parse_constituents(resp.text)
    except Exception:
        if not path.is_file():
            raise
        return parse_constituents(path.read_text())
    settings_mod.DATA_DIR.mkdir(exist_ok=True)
    path.write_text(resp.text)
    return companies


def fundamentals(payload: bytes, company: dict) -> dict:
    """trader-analyst's metrics row (TTM EPS, growth, margins) from SEC company facts."""
    facts = skill("trader-analyst", "facts")
    return facts.metrics_row(company["ticker"], facts.analyse(json.loads(payload), name=company["name"]))


async def fetch_fundamentals(client, user_agent: str, company: dict) -> dict:
    resp = await client.get(SEC_FACTS_URL.format(cik=company["cik"]), headers={"User-Agent": user_agent})
    if resp.status_code == 403:
        raise SecRefused("SEC refused the request: check the name and email in Settings")
    resp.raise_for_status()
    return await asyncio.to_thread(fundamentals, resp.content, company)


def technicals(daily) -> dict | None:
    """Trend and momentum on daily bars: needs 200 bars for the 200-day EMA."""
    close = daily["close"]
    if len(close) < 200:
        return None
    last, e50, e200 = close.iloc[-1], ema(close, 50).iloc[-1], ema(close, 200).iloc[-1]
    return {
        "price": round(float(last), 2),
        "rsi14": round(float(rsi(close).iloc[-1]), 1),
        "pct_vs_ema200": round(float(last / e200 - 1) * 100, 1),
        "ema50_vs_ema200": round(float(e50 / e200 - 1) * 100, 1),
        "pct_from_high": round(float(last / daily["high"].iloc[-252:].max() - 1) * 100, 1),
        "bar_date": daily.index[-1].date().isoformat(),
    }


def candidate(company: dict, fund: dict, tech: dict, today: date) -> dict:
    """One screener row: SEC numbers + chart, with P/E and earnings yield as trader-screener computes them."""
    row = {**fund, **tech, "ticker": company["ticker"], "name": company["name"], "sector": company["sector"],
           "cik": company["cik"]}
    eps = fund.get("eps_ttm")
    if eps is not None:
        row["earnings_yield"] = round(100 * eps / tech["price"], 2)
        if eps > 0:
            row["pe"] = round(tech["price"] / eps, 1)
    if fund.get("period_end"):
        row["fundamentals_age_days"] = (today - date.fromisoformat(fund["period_end"])).days
    # trader-analyst's one-off flag: net income above operating income means gains outside the business
    net, operating = fund.get("net_margin"), fund.get("operating_margin")
    row["one_off_gains"] = net is not None and operating is not None and net > operating
    return row


# ---- the scan -----------------------------------------------------------------

async def scan(client, user_agent: str, cache: dict, progress=lambda done, total: None) -> dict:
    """Screen every S&P 500 company. `cache` (ticker -> fundamentals row) is updated in place."""
    today = date.today()
    screener = skill("trader-screener", "screen")
    skill("trader-analyst", "facts")  # load it here, before worker threads use it (and fail fast if missing)
    screener.check_rules(cfg.FINDER_RULES)
    companies = await universe(client)
    rows, failed = [], []
    for i, c in enumerate(companies):
        progress(i, len(companies))
        try:
            fund = cache.get(c["ticker"])
            if not fund or (today - date.fromisoformat(fund["fetched"])).days >= cfg.FINDER_FUNDAMENTALS_MAX_AGE_DAYS:
                fund = {**await fetch_fundamentals(client, user_agent, c), "fetched": today.isoformat()}
                cache[c["ticker"]] = fund
                await asyncio.sleep(cfg.FINDER_SEC_PAUSE)
            tech = technicals(await fetch_bars(client, c["ticker"].replace(".", "-"), "1d", "2y"))
            await asyncio.sleep(cfg.FINDER_YAHOO_PAUSE)
            if tech is None:
                raise FinderError("fewer than 200 days of prices")
            rows.append(candidate(c, fund, tech, today))
        except SecRefused:
            raise
        except Exception as e:  # one company's bad data or a network blip: skip it, keep scanning
            failed.append({"ticker": c["ticker"], "error": f"{type(e).__name__}: {e}"[:120]})
    progress(len(companies), len(companies))
    if not rows:  # offline, or Yahoo is down: keep the last good results
        raise FinderError(f"No company could be read ({failed[0]['error']})")
    passed, companies_seen = [], set()
    for r in screener.screen(rows, cfg.FINDER_RULES):
        if r["passed"] and r["metrics"]["cik"] not in companies_seen:  # one share class per company (FOX/FOXA)
            companies_seen.add(r["metrics"]["cik"])
            passed.append(r)
    return {
        "time": datetime.now(timezone.utc).isoformat(),
        "universe": "S&P 500",
        "companies": len(companies),
        "scanned": len(rows),
        "passed": len(passed),
        "failed": failed,
        "picks": [{**r["metrics"], "score": r["score"], "why": r["passes"]} for r in passed[:cfg.FINDER_TOP]],
    }


def due(last_scan: str | None, now: datetime) -> bool:
    """True when no scan has run since the most recent weekday close (16:15 New York)."""
    if not last_scan:
        return True
    ny = now.astimezone(NY)
    mark = ny.replace(hour=cfg.FINDER_SCAN_TIME_NY[0], minute=cfg.FINDER_SCAN_TIME_NY[1], second=0, microsecond=0)
    while mark > ny or mark.weekday() >= 5:
        mark -= timedelta(days=1)
    return datetime.fromisoformat(last_scan) < mark


def new_picks(previous: dict | None, current: dict) -> list[dict]:
    before = {p["ticker"] for p in (previous or {}).get("picks", [])}
    return [p for p in current["picks"] if p["ticker"] not in before]


def describe(p: dict) -> str:
    return f"{p['ticker']} {p['name']} (P/E {p['pe']:g}, revenue {p['revenue_growth_yoy']:+.0f}%, RSI {p['rsi14']:g})"


# ---- storage ------------------------------------------------------------------

def _read(name: str, default):
    try:
        return json.loads((settings_mod.DATA_DIR / name).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def load_results() -> dict | None:
    return _read("finder.json", None)


def load_cache() -> dict:
    return _read("finder_fundamentals.json", {})


def save(result: dict, cache: dict):
    settings_mod.DATA_DIR.mkdir(exist_ok=True)
    (settings_mod.DATA_DIR / "finder.json").write_text(json.dumps(result, indent=1))
    (settings_mod.DATA_DIR / "finder_fundamentals.json").write_text(json.dumps(cache))


async def run(user_agent: str, progress) -> dict:
    """One full scan with its own HTTP client, so it never holds up the station's 10-second loop."""
    cache = load_cache()
    async with httpx.AsyncClient(headers=cfg.HTTP_HEADERS, timeout=30, follow_redirects=True) as client:
        result = await scan(client, user_agent, cache, progress)
    save(result, cache)
    return result
