"""Rule-based headline scoring for gold, Nasdaq and Bitcoin.

Each rule is (regex, gold, nasdaq, bitcoin effect, label). Effects are in "units":
1 is a normal nudge, 2 a strong one. A headline's total is clamped to +/-3.
"""

import math
import re
from datetime import datetime, timedelta

from .config import NEWS_HALF_LIFE_MIN, NEWS_POINTS_PER_UNIT, NEWS_WINDOW_HOURS

MAX_IMPACT = 3.0

# Rate-policy rules: skipped when the headline is about a non-US central bank.
MONETARY_RULES = [
    (r"\bhawkish", -1.5, -1.5, -1.5, "hawkish"),
    (r"\brate hikes?\b|\bhik(e|es|ed|ing) (interest )?rates\b|\brais(e|es|ed|ing) (interest )?rates\b", -2, -2, -2, "rate hike"),
    (r"higher for longer", -1.5, -1.5, -1.5, "higher for longer"),
    (r"\brestrictive\b|\btighten(ing)?\b", -1, -1, -1, "tightening"),
    (r"hotter[- ]than[- ]expected|inflation (rises|jumps|accelerates|surges)|(persistent(ly)? high|sticky|elevated|above[- ]target) inflation|inflation\b.{0,20}\babove target", -1.5, -1.5, -1.5, "hot inflation"),
    (r"\bdovish", 1.5, 1.5, 1.5, "dovish"),
    (r"\brate cuts?\b|\bcut(s|ting)? (interest )?rates\b|\blower (interest )?rates\b", 2, 2, 2, "rate cut"),
    (r"\b(monetary|policy) easing\b|\beasing cycle\b|\bpaus(e|es|ed|ing) (rate )?hikes\b", 1, 1, 1, "easing"),
    (r"cooler[- ]than[- ]expected|inflation (eases|cools|slows|falls|drops)|disinflation", 1.5, 1.5, 1.5, "cooling inflation"),
]

_UP = r"(rall(y|ies|ied)|surg(e|es|ed)|jump(s|ed)?|climb(s|ed)?|gain(s|ed)?|ris(e|es)|rose|soar(s|ed)?|hits? (a )?record|(end|close|settle|finish|trade)(s|d|ed)? (the )?(week |day |session )?higher)"
_DOWN = r"(fall(s)?|fell|drop(s|ped)?|slid(e|es)?|slump(s|ed)?|tumbl(e|es|ed)|declin(e|es|ed)|plung(e|es|ed)|sink(s)?|sank|(end|close|settle|finish|trade)(s|d|ed)? (the )?(week |day |session )?lower)"
_GOLD = r"\bgold( prices?| futures)?\s+"
_CRYPTO = r"\b(bitcoin|btc|crypto(currenc(y|ies)|s)?|ether(eum)?)\s+"
_STOCKS = r"\b(nasdaq( 100)?|tech stocks?|stocks|equities|wall street|megacaps?|chipmakers?)\s+"

MARKET_RULES = [
    (r"(yields?|treasur(y|ies)) (rise|rises|rising|jump|jumps|surge|surges|climb|climbs|spike|spikes)|pressur\w* up (bond )?yields|rising (bond )?yields", -1.5, -1, -1, "yields up"),
    (r"(yields?|treasur(y|ies)) (fall|falls|drop|drops|slide|slides|tumble|tumbles|decline|declines)", 1.5, 1, 1, "yields down"),
    (r"dollar (strengthens|rallies|jumps|surges|gains|rises)|strong(er)? dollar", -1.5, -0.5, -1, "USD up"),
    (r"dollar (weakens|falls|slides|drops|slumps|tumbles)|weak(er)? dollar", 1.5, 0.5, 1, "USD down"),
    # Geopolitics / risk sentiment
    (r"\b(war|missiles?|airstrikes?|strikes? on|bombing|attacks?|invasion|military action|troops|drones?|hostilities)\b", 1.5, -1, -1, "geopolitical risk"),
    (r"(?<![-\w])escalat\w*|\btensions?\b|\bconflict\b", 1, -0.5, -0.5, "tensions"),
    (r"\bsanctions?\b|\btariffs?\b|trade war|export (ban|controls|curbs)", 1, -1, -0.5, "trade/sanctions"),
    (r"recession|slowdown fears|sell-?off|\bcrash|\bpanic|safe[- ]haven|risk[- ]off", 1, -1.5, -1.5, "risk-off"),
    (r"\bceasefire\b|peace (deal|talks|agreement|plan)|\btruce\b|de-?escalat\w*", -1, 1, 1, "de-escalation"),
    (r"trade (deal|agreement|pact)|free[- ]trade", -0.5, 1, 0.5, "trade deal"),
    # Gold-specific
    (_GOLD + _UP, 1, 0, 0, "gold up"),
    (_GOLD + _DOWN, -1, 0, 0, "gold down"),
    (r"central banks? (buy|buying|purchas\w*|add\w*) (of )?gold|gold (demand|buying|imports?)|imported .*\bgold", 1, 0, 0, "gold demand"),
    (r"gold (etf )?outflows", -1, 0, 0, "gold outflows"),
    # Nasdaq-specific
    (_STOCKS + _UP, 0, 1, 0, "stocks up"),
    (_STOCKS + _DOWN, 0, -1, 0, "stocks down"),
    (r"beats? (estimates|expectations)|tops estimates|raises (guidance|outlook|forecast)|strong (earnings|results)", 0, 1, 0, "earnings beat"),
    (r"miss(es)? (estimates|expectations)|cuts? (guidance|outlook|forecast)|weak (earnings|results)|profit warning", 0, -1, 0, "earnings miss"),
    (r"\bantitrust\b|chip export", 0, -1, 0, "tech regulation"),
    # Bitcoin-specific
    (_CRYPTO + _UP, 0, 0, 1, "crypto up"),
    (_CRYPTO + _DOWN, 0, 0, -1, "crypto down"),
    (r"(bitcoin|btc|crypto|ether) etfs?\b.{0,30}\binflows?|inflows? into (bitcoin|btc|crypto)", 0, 0, 1, "crypto ETF inflows"),
    (r"(bitcoin|btc|crypto|ether) etfs?\b.{0,30}\boutflows?|outflows? from (bitcoin|btc|crypto)", 0, 0, -1, "crypto ETF outflows"),
    (r"\b(buys?|bought|adds?|purchas\w*)\b.{0,30}\bbitcoin|bitcoin reserve", 0, 0, 1, "BTC buying"),
    (r"\b(exchange|crypto|defi|bridge|wallet)\b.{0,30}\b(hack(ed|s)?|exploit(ed)?|breach(ed)?|stolen)\b", 0, 0, -1.5, "crypto hack"),
    (r"\bsec\b.{0,40}\b(sues|lawsuit|charges)\b|crypto (ban|crackdown)", 0, 0, -1, "crypto enforcement"),
    (r"\bapprov\w*\b.{0,25}\b(bitcoin|crypto|spot)\b|crypto (bill|legislation)\b.{0,15}\b(passes|signed)", 0, 0, 1, "crypto approval"),
]

NON_US_CENTRAL_BANK = re.compile(
    r"\b(ecb|boe|boj|snb|rba|rbnz|boc|pboc|rbi|norges|riksbank|bank of (england|japan|canada)|"
    r"swiss national bank|nb chairman|lagarde|bailey|ueda|schlegel|bullock)\b|ecb's",
    re.I,
)
NEGATOR = re.compile(
    r"\b(no|not|never|den(y|ies|ied)|reject(s|ed)?|rule[sd]? out|won'?t|without|against|unlikely|avoid\w*|"
    r"call(s|ed)? off|end(s|ed)?|eas(e|es|ed|ing)|cool(s|ed|ing)?)\b",
    re.I,
)

_compiled = [(re.compile(p, re.I), (g, n, b), label, monetary)
             for rules, monetary in ((MONETARY_RULES, True), (MARKET_RULES, False))
             for p, g, n, b, label in rules]
SYMBOLS = ("GOLD", "NASDAQ", "BITCOIN")

# FinancialJuice data releases: "US CPI m/m Actual 0.4% (Forecast 0.3%, Previous 0.2%)"
RELEASE = re.compile(r"^(?P<name>.+?)\s+Actual\s+(?P<actual>\S+)\s*\(Forecast\s+(?P<forecast>[^,]+),", re.I)

# (keywords, gold, nasdaq, bitcoin) for a release above forecast; below forecast flips the sign.
# Checked in order, so "unemployment" is matched before "employment".
RELEASE_CATEGORIES = [
    (("unemployment", "jobless", "claims"), 1.5, 1, 1),
    (("cpi", "pce", "ppi", "inflation", "price", "average hourly earnings"), -2, -2, -2),
    (("nonfarm", "payrolls", "adp", "employment change", "jolts"), -2, -1.5, -1.5),
    (("gdp", "retail sales", "ism", "pmi", "durable goods", "industrial production", "confidence", "sentiment"), -1, 0, 0),
]


def _number(text: str) -> float | None:
    try:
        return float(re.sub(r"[%$,KMBT]", "", text.strip(), flags=re.I))
    except ValueError:
        return None


def _score_release(title: str) -> tuple[tuple, str] | None:
    """Score a US data release by its surprise vs forecast, or None if not a scorable release."""
    m = RELEASE.match(title)
    if not m or not re.match(r"(US|U\.S\.)\b", m["name"]):
        return None
    actual, forecast = _number(m["actual"]), _number(m["forecast"])
    if actual is None or forecast is None or actual == forecast:
        return None
    name = m["name"].lower()
    for keywords, *effects in RELEASE_CATEGORIES:
        if any(k in name for k in keywords):
            s = 1 if actual > forecast else -1
            return tuple(s * e for e in effects), f"{m['name']} {'above' if s > 0 else 'below'} forecast"
    return None


def _negated(text: str, start: int) -> bool:
    """True when one of the four words before the match, within the same clause, is a
    negator: "rejects ceasefire", "easing US-Iran conflict"."""
    clause = re.split(r"[,:;.!?\u2014\u2013]", text[:start])[-1]
    before = " ".join(clause.split()[-4:])
    return bool(NEGATOR.search(before))


def score_headline(title: str) -> dict:
    """Return {"GOLD": units, "NASDAQ": units, "BITCOIN": units, "tags": [...]} for one headline."""
    title = title.removeprefix("FinancialJuice: ").strip()
    release = _score_release(title)
    if release:
        effects, label = release
        return {**dict(zip(SYMBOLS, effects)), "tags": [label]}

    skip_monetary = bool(NON_US_CENTRAL_BANK.search(title))
    totals = [0.0] * len(SYMBOLS)
    tags = []
    for rx, effects, label, monetary in _compiled:
        if monetary and skip_monetary:
            continue
        m = rx.search(title)
        if not m:
            continue
        sign = -1 if _negated(title, m.start()) else 1
        totals = [t + sign * e for t, e in zip(totals, effects)]
        tags.append(("not " if sign < 0 else "") + label)
    clamp = lambda x: max(-MAX_IMPACT, min(MAX_IMPACT, x))
    return {**{sym: clamp(t) for sym, t in zip(SYMBOLS, totals)}, "tags": tags}


def news_contributions(items: list[dict], symbol: str, now: datetime) -> list[tuple[float, dict]]:
    """(points, item) for every recent headline that moves this symbol, biggest first."""
    out = []
    for item in items:
        age = now - item["published"]
        if age > timedelta(hours=NEWS_WINDOW_HOURS) or age < timedelta(0) or not item["impact"][symbol]:
            continue
        decay = math.pow(0.5, age.total_seconds() / 60 / NEWS_HALF_LIFE_MIN)
        out.append((item["impact"][symbol] * decay * NEWS_POINTS_PER_UNIT, item))
    return sorted(out, key=lambda c: abs(c[0]), reverse=True)


def news_score(contributions: list[tuple[float, dict]]) -> float:
    """Sum of contributions, clamped to -100..+100 points."""
    return max(-100.0, min(100.0, round(sum(p for p, _ in contributions), 1)))
