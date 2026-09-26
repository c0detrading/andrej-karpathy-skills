"""User settings, saved to data/settings.json next to the app."""

import json
import re
from pathlib import Path

from .config import ASSET_PRESETS, DEFAULT_ASSETS, NEWS_PROFILES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
SECRETS = ("telegram_token", "anthropic_api_key")
MASK = "••••••••"

DEFAULTS = {
    "assets": DEFAULT_ASSETS,
    "custom_assets": {},          # key -> same shape as an ASSET_PRESETS entry
    "telegram_token": "",
    "telegram_chat_id": "",
    "anthropic_api_key": "",
    "claude_scoring": False,
    "briefing_time": "08:00",     # local time of this computer, "" = off
}


def load() -> dict:
    try:
        saved = json.loads(SETTINGS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        saved = {}
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def save(settings: dict):
    DATA_DIR.mkdir(exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))


def public(settings: dict) -> dict:
    """Settings as the browser sees them: secrets masked, plus the preset list."""
    out = {k: (MASK if k in SECRETS and v else v) for k, v in settings.items()}
    return {**out, "presets": ASSET_PRESETS, "news_profiles": NEWS_PROFILES}


def assets(settings: dict) -> dict:
    """The chosen assets, in order, as key -> asset config."""
    catalog = {**ASSET_PRESETS, **settings["custom_assets"]}
    return {k: catalog[k] for k in settings["assets"] if k in catalog}


def _custom_asset(key: str, a: dict) -> dict:
    ticker = str(a.get("ticker", "")).strip()
    if not re.fullmatch(r"[\w.^=\-]{1,20}", ticker):
        raise ValueError(f"Invalid ticker for {key}: {ticker!r}")
    news = a.get("news") or None
    if news not in (None, *NEWS_PROFILES):
        raise ValueError(f"Unknown news profile {news!r}")
    return {
        "ticker": ticker,
        "name": str(a.get("name") or ticker)[:40],
        "cme": bool(a.get("cme", True)),
        "news": news,
        "macro": max(-1.0, min(1.0, float(a.get("macro", 0)))),
    }


def update(current: dict, changes: dict) -> dict:
    """Validate and apply changes from the Settings page. Masked or empty secrets are kept."""
    new = dict(current)
    for k, v in changes.items():
        if k not in DEFAULTS:
            continue
        if k in SECRETS:
            if v and v != MASK:
                new[k] = str(v).strip()
            elif v == "":
                new[k] = ""
        elif k == "custom_assets":
            new[k] = {re.sub(r"\W", "", key.upper())[:16]: _custom_asset(key, a) for key, a in v.items() if key}
        elif k == "assets":
            new[k] = [str(x) for x in v]
        elif k == "briefing_time":
            if v and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
                raise ValueError("Briefing time must be HH:MM")
            new[k] = v
        elif k == "claude_scoring":
            new[k] = bool(v)
        else:
            new[k] = str(v).strip()
    catalog = {**ASSET_PRESETS, **new["custom_assets"]}
    new["assets"] = [k for k in dict.fromkeys(new["assets"]) if k in catalog]
    if not new["assets"]:
        raise ValueError("Pick at least one asset")
    return new
