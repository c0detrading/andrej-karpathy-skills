"""SQLite storage in data/volstro.db: clients, their social accounts, daily numbers and saved reports."""

import csv
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime

from . import settings
from .config import PLATFORMS, STAGES

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    stage TEXT NOT NULL,
    contact TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    value REAL NOT NULL DEFAULT 0,
    monthly INTEGER NOT NULL DEFAULT 1,
    next_step TEXT NOT NULL DEFAULT '',
    next_date TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    handle TEXT NOT NULL,
    last_error TEXT NOT NULL DEFAULT '',
    UNIQUE (client_id, platform, handle)
);
CREATE TABLE IF NOT EXISTS snapshots (
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    followers INTEGER NOT NULL,
    posts_7d INTEGER,
    avg_likes REAL,
    avg_comments REAL,
    last_post TEXT,
    source TEXT NOT NULL,
    PRIMARY KEY (account_id, date)
);
CREATE TABLE IF NOT EXISTS reports (date TEXT PRIMARY KEY, body TEXT NOT NULL);
"""

CLIENT_FIELDS = ("name", "stage", "contact", "email", "phone", "website", "value", "monthly",
                 "next_step", "next_date", "notes")
NUMBER_FIELDS = ("followers", "posts_7d", "avg_likes", "avg_comments", "last_post")


@contextmanager
def connect():
    settings.DATA_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(settings.DATA_DIR / "volstro.db")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    try:
        with con:  # commit on success, roll back on error
            yield con
    finally:
        con.close()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---- validation -----------------------------------------------------------

def clean_client(data: dict, partial: bool = False) -> dict:
    """Client fields from the browser, validated. `partial` allows updating only some fields."""
    out = {}
    for k in CLIENT_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k == "stage":
            if v not in STAGES:
                raise ValueError(f"Unknown stage {v!r}")
        elif k == "value":
            v = _number(v, float, "Value") or 0.0
        elif k == "monthly":
            v = bool(v)
        elif k == "next_date":
            v = _date(v, "Next step date") or ""
        else:
            v = str(v or "").strip()[:5000 if k == "notes" else 200]
        out[k] = v
    if ("name" in out or not partial) and not out.get("name"):
        raise ValueError("Name is required")
    if not partial:
        out.setdefault("stage", "lead")
    return out


def clean_handle(platform: str, handle) -> str:
    """A username from what people paste: '@name', 'instagram.com/name/', a Facebook page link..."""
    if platform not in PLATFORMS:
        raise ValueError(f"Unknown platform {platform!r}")
    h = str(handle or "").strip()
    page_id = re.search(r"[?&]id=(\d+)", h)  # facebook.com/profile.php?id=123
    if page_id:
        h = page_id.group(1)
    h = re.sub(r"^(https?://)?([a-z]+\.)?(instagram|facebook|tiktok)\.com/", "", h, flags=re.I)
    h = h.split("?")[0].strip("/").split("/")[0].lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9._-]{1,100}", h):
        raise ValueError(f"That doesn't look like a {platform} username: {handle!r}")
    return h


def clean_numbers(data: dict) -> tuple[date, dict]:
    """(date, numbers) for a snapshot typed in or imported from a CSV."""
    day = _date(data.get("date"), "Date") or date.today().isoformat()
    if day > date.today().isoformat():
        raise ValueError("Date can't be in the future")
    numbers = {
        "followers": _number(data.get("followers"), int, "Followers"),
        "posts_7d": _number(data.get("posts_7d"), int, "Posts in the last 7 days"),
        "avg_likes": _number(data.get("avg_likes"), float, "Average likes"),
        "avg_comments": _number(data.get("avg_comments"), float, "Average comments"),
        "last_post": _date(data.get("last_post"), "Last post date"),
    }
    if numbers["followers"] is None:
        raise ValueError("Followers is required")
    return date.fromisoformat(day), numbers


def _number(v, cast, label):
    if v is None or str(v).strip() == "":
        return None
    try:
        # Thousands separators are fine in whole numbers ("12,450").
        x = cast(str(v).replace(",", "").replace(" ", "") if cast is int else str(v).strip())
    except ValueError:
        raise ValueError(f"{label} must be a number, not {v!r}") from None
    if x < 0:
        raise ValueError(f"{label} can't be negative")
    return x


def _date(v, label) -> str | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return date.fromisoformat(str(v).strip()).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be a date like 2026-09-28, not {v!r}") from None


# ---- clients and accounts -------------------------------------------------

def clients(con) -> list[dict]:
    return [dict(r) for r in con.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE")]


def client(con, cid: int) -> dict | None:
    row = con.execute("SELECT * FROM clients WHERE id = ?", (cid,)).fetchone()
    return dict(row) if row else None


def create_client(con, data: dict) -> int:
    now = now_iso()
    data = {**data, "created_at": now, "updated_at": now}
    cols = ", ".join(data)
    return con.execute(f"INSERT INTO clients ({cols}) VALUES ({', '.join('?' * len(data))})",
                       tuple(data.values())).lastrowid


def update_client(con, cid: int, data: dict) -> bool:
    data = {**data, "updated_at": now_iso()}
    sets = ", ".join(f"{k} = ?" for k in data)  # keys come from CLIENT_FIELDS only
    return con.execute(f"UPDATE clients SET {sets} WHERE id = ?", (*data.values(), cid)).rowcount > 0


def delete_client(con, cid: int) -> bool:
    return con.execute("DELETE FROM clients WHERE id = ?", (cid,)).rowcount > 0


def accounts(con, client_id: int | None = None) -> list[dict]:
    """Social accounts with their client's stage, one client's or everyone's."""
    sql = "SELECT a.*, c.stage FROM accounts a JOIN clients c ON c.id = a.client_id"
    args = ()
    if client_id is not None:
        sql, args = sql + " WHERE a.client_id = ?", (client_id,)
    return [dict(r) for r in con.execute(sql + " ORDER BY a.platform, a.handle", args)]


def account(con, aid: int) -> dict | None:
    row = con.execute("SELECT * FROM accounts WHERE id = ?", (aid,)).fetchone()
    return dict(row) if row else None


def add_account(con, client_id: int, platform: str, handle: str) -> int:
    return con.execute("INSERT INTO accounts (client_id, platform, handle) VALUES (?, ?, ?)",
                       (client_id, platform, handle)).lastrowid


def delete_account(con, aid: int) -> bool:
    return con.execute("DELETE FROM accounts WHERE id = ?", (aid,)).rowcount > 0


def set_fetch_error(con, aid: int, error: str):
    con.execute("UPDATE accounts SET last_error = ? WHERE id = ?", (error, aid))


# ---- numbers --------------------------------------------------------------

def save_snapshot(con, aid: int, day: date, numbers: dict, source: str):
    """One row per account per day: saving the same day again replaces it."""
    con.execute(
        f"INSERT OR REPLACE INTO snapshots (account_id, date, {', '.join(NUMBER_FIELDS)}, source) "
        f"VALUES (?, ?, {', '.join('?' * len(NUMBER_FIELDS))}, ?)",
        (aid, day.isoformat(), *(numbers[k] for k in NUMBER_FIELDS), source),
    )


def history(con, aid: int, since: date) -> list[dict]:
    """Snapshots from `since` on, oldest first."""
    rows = con.execute("SELECT * FROM snapshots WHERE account_id = ? AND date >= ? ORDER BY date",
                       (aid, since.isoformat()))
    return [dict(r) for r in rows]


def import_csv(con, text: str) -> dict:
    """Import numbers from a CSV (columns as in static/numbers-template.csv), matched by platform + username."""
    text = text.lstrip("﻿")  # Excel adds a byte-order mark
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")  # Excel in many countries saves with ;
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    missing = {"platform", "handle", "followers"} - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"The CSV needs these columns: {', '.join(sorted(missing))}")
    imported, skipped = 0, []
    for n, row in enumerate(reader, start=2):
        try:
            platform = str(row.get("platform") or "").strip().lower()
            handle = clean_handle(platform, row.get("handle"))
            day, numbers = clean_numbers(row)
            matches = con.execute("SELECT id FROM accounts WHERE platform = ? AND handle = ?",
                                  (platform, handle)).fetchall()
            if not matches:
                raise ValueError(f"no client has {platform} @{handle} (add it to the client first)")
            for m in matches:
                save_snapshot(con, m["id"], day, numbers, "csv")
            imported += 1
        except ValueError as e:
            skipped.append(f"Row {n}: {e}")
    return {"imported": imported, "skipped": skipped}


# ---- reports --------------------------------------------------------------

def save_report(con, report: dict):
    con.execute("INSERT OR REPLACE INTO reports (date, body) VALUES (?, ?)", (report["date"], json.dumps(report)))


def report(con, day: str) -> dict | None:
    row = con.execute("SELECT body FROM reports WHERE date = ?", (day,)).fetchone()
    return json.loads(row["body"]) if row else None


def report_dates(con) -> list[str]:
    return [r["date"] for r in con.execute("SELECT date FROM reports ORDER BY date DESC")]
