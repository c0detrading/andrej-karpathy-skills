"""Live daily record: snapshot each asset's overall bias once a day, grade it at the close."""

import json

import pandas as pd

from .settings import DATA_DIR

LOG_FILE = DATA_DIR / "bias_log.jsonl"


def load() -> list[dict]:
    try:
        return [json.loads(line) for line in LOG_FILE.read_text().splitlines() if line.strip()]
    except FileNotFoundError:
        return []


def append(record: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")


def grade(records: list[dict], asset: str, daily: pd.DataFrame | None, today: str) -> dict:
    """Compare each finished day's bias with where that day's daily bar closed."""
    closes = {} if daily is None else {ts.date().isoformat(): c for ts, c in daily["close"].items()}
    results = []
    for r in records:
        if r["asset"] != asset or r["date"] >= today or r["date"] not in closes:
            continue
        move = closes[r["date"]] - r["price"]
        if move:
            results.append({"date": r["date"], "bias": r["bias"], "hit": (move > 0) == (r["bias"] == "BULLISH")})
    hits = sum(r["hit"] for r in results)
    return {
        "days": len(results),
        "hits": hits,
        "hit_rate": round(100 * hits / len(results), 1) if results else None,
        "recent": results[-10:],
    }
