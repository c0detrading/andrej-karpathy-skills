"""Optional Claude re-scoring of market-relevant headlines (needs an Anthropic API key)."""

import json
import re

import anthropic

from .config import CLAUDE_MODEL
from .sentiment import MAX_IMPACT, SYMBOLS

# Only headlines that plausibly move markets are sent, to keep cost down.
RELEVANT = re.compile(
    r"\b(fed|fomc|powell|inflation|cpi|pce|ppi|payrolls?|jobs|unemployment|yields?|treasur\w*|dollar|"
    r"tariffs?|war|iran|israel|russia|ukraine|china|taiwan|sanctions?|recession|bitcoin|btc|crypto\w*|"
    r"etf|gold|nasdaq|stocks|earnings|rates?|opec|oil|gdp|stimulus|default)\b",
    re.I,
)

SYSTEM = (
    "You are a markets desk analyst. For each headline, estimate its likely short-term (next few hours) "
    "price impact on gold (XAU), the Nasdaq 100, and Bitcoin, each from -3 (strongly bearish) to +3 "
    "(strongly bullish); 0 means no meaningful effect. Most headlines are 0 for most assets. Consider the "
    "usual transmission: Fed policy and US data move yields and the dollar; geopolitical risk lifts gold "
    "and hurts risk assets. Give a reason of at most 12 words."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    **{s: {"type": "number"} for s in SYMBOLS},
                    "reason": {"type": "string"},
                },
                "required": ["id", *SYMBOLS, "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_clients: dict[str, anthropic.AsyncAnthropic] = {}


def worth_scoring(item: dict) -> bool:
    return bool(item["impact"]["tags"]) or item["source"].startswith("Fed") or bool(RELEVANT.search(item["title"]))


async def score(api_key: str, items: list[dict]) -> dict[str, dict]:
    """Return {item id: {"GOLD": x, "NASDAQ": y, "BITCOIN": z, "tags": ["AI: reason"]}}."""
    client = _clients.setdefault(api_key, anthropic.AsyncAnthropic(api_key=api_key))
    headlines = [
        {"id": i["id"], "source": i["source"], "title": i["title"], "summary": (i.get("summary") or "")[:300]}
        for i in items
    ]
    response = await client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=8000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(headlines, ensure_ascii=False)}],
    )
    if response.stop_reason in ("refusal", "max_tokens"):
        return {}
    text = next((b.text for b in response.content if b.type == "text"), "")
    clamp = lambda x: max(-MAX_IMPACT, min(MAX_IMPACT, round(float(x) * 2) / 2))
    return {
        r["id"]: {**{s: clamp(r[s]) for s in SYMBOLS}, "tags": [f"AI: {r['reason']}"]}
        for r in json.loads(text)["items"]
    }
