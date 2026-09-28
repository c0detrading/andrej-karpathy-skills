"""User settings, saved to data/settings.json next to the app."""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
SECRETS = ("meta_token",)
MASK = "••••••••"

DEFAULTS = {
    "meta_token": "",        # Meta access token, used for Instagram and Facebook numbers
    "ig_user_id": "",        # Instagram business account the lookups run from; found from the token
    "report_time": "08:00",  # local time of this computer
    "currency": "€",
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
    """Settings as the browser sees them: secrets masked."""
    return {k: (MASK if k in SECRETS and v else v) for k, v in settings.items()}


def update(current: dict, changes: dict) -> dict:
    """Validate and apply changes from the Settings page. Masked or empty secrets are kept."""
    new = dict(current)
    for k, v in changes.items():
        if k in SECRETS:
            if v and v != MASK:
                new[k] = str(v).strip()
            elif v == "":
                new[k] = ""
        elif k == "report_time":
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v)):
                raise ValueError("Report time must be HH:MM")
            new[k] = v
        elif k == "currency":
            new[k] = str(v).strip()[:5]
    if new["meta_token"] != current["meta_token"]:
        new["ig_user_id"] = ""  # a new token may belong to another account: look it up again
    return new
