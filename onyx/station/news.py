"""News sources: FinancialJuice and Yahoo Finance RSS, plus the Forex Factory calendar."""

import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

from .config import FF_COUNTRIES, FF_IMPACTS
from .sentiment import score_headline


def parse_rss(xml_text: str, source: str) -> list[dict]:
    items = []
    for node in ET.fromstring(xml_text).iter("item"):
        title = (node.findtext("title") or "").removeprefix("FinancialJuice: ").strip()
        pub = node.findtext("pubDate")
        if not title or not pub:
            continue
        items.append({
            "id": hashlib.sha1(f"{source}|{title}".encode()).hexdigest()[:16],
            "source": source,
            "title": title,
            "link": node.findtext("link"),
            "published": parsedate_to_datetime(pub),
            "impact": score_headline(title),
        })
    return items


def parse_ff_calendar(events: list[dict]) -> list[dict]:
    """Keep the Forex Factory events that move gold, Nasdaq and Bitcoin (USD, high/medium impact)."""
    return sorted(
        (
            {
                "title": e["title"],
                "country": e["country"],
                "impact": e["impact"],
                "time": datetime.fromisoformat(e["date"]),
                "forecast": e.get("forecast", ""),
                "previous": e.get("previous", ""),
            }
            for e in events
            if e.get("country") in FF_COUNTRIES and e.get("impact") in FF_IMPACTS
        ),
        key=lambda e: e["time"],
    )


def dedupe(items: list[dict]) -> list[dict]:
    """Newest first, one entry per headline text (FinancialJuice often reposts)."""
    seen, out = set(), []
    for item in sorted(items, key=lambda i: i["published"], reverse=True):
        key = item["title"].lower().rstrip(".")
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


async def fetch_rss(client, url: str, source: str) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()
    return parse_rss(resp.text, source)


async def fetch_ff_calendar(client, url: str) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()
    return parse_ff_calendar(resp.json())
