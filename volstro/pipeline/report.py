"""Each client's social numbers, and the concerns in current clients that need attention."""

from datetime import date, timedelta
from statistics import mean

from . import config as cfg, db


def _on_or_before(history: list[dict], day: date) -> dict | None:
    return next((s for s in reversed(history) if s["date"] <= day.isoformat()), None)


def _engagement(s: dict) -> float | None:
    """Average likes + comments per post, as a % of followers."""
    if not s["followers"] or s["avg_likes"] is None:
        return None
    return round(100 * (s["avg_likes"] + (s["avg_comments"] or 0)) / s["followers"], 2)


def summarize(account: dict, history: list[dict], today: date) -> dict:
    """One account's row: latest numbers and how they changed. `history` is oldest first."""
    row = {"id": account["id"], "platform": account["platform"], "handle": account["handle"],
           "error": account["last_error"], "followers": None}
    if not history:
        return row
    last = history[-1]
    last_day = date.fromisoformat(last["date"])

    def change(days):
        ref = _on_or_before(history, last_day - timedelta(days=days))
        return None if ref is None else last["followers"] - ref["followers"]

    past = [e for s in history[:-1]
            if s["date"] >= (last_day - timedelta(days=30)).isoformat() and (e := _engagement(s)) is not None]
    return {
        **row,
        "date": last["date"],
        "age_days": (today - last_day).days,
        "source": last["source"],
        "followers": last["followers"],
        "change_1d": change(1),
        "change_7d": change(7),
        "change_30d": change(30),
        "engagement": _engagement(last),
        "engagement_avg": round(mean(past), 2) if past else None,
        "engagement_days": len(past),
        "posts_7d": last["posts_7d"],
        "last_post": last["last_post"],
        "days_since_post": (today - date.fromisoformat(last["last_post"])).days if last["last_post"] else None,
    }


def _level(x: float, thresholds: tuple) -> str | None:
    medium, high = thresholds
    return "high" if x >= high else "medium" if x >= medium else None


def account_concerns(row: dict) -> list[dict]:
    name = f"{cfg.PLATFORM_NAMES[row['platform']]} @{row['handle']}"
    mode = cfg.PLATFORMS[row["platform"]]
    out = []

    def add(level, text):
        out.append({"level": level, "text": f"{name}: {text}"})

    if row["error"]:
        add("high", f"couldn't fetch today's numbers: {row['error']}")
    if row["followers"] is None:
        if not row["error"]:
            add("medium", "no numbers yet" + (", type them in or import a CSV" if mode == "manual" else ""))
        return out
    if row["age_days"] > cfg.STALE_DAYS[mode]:
        add("medium", f"latest numbers are {row['age_days']} days old")

    lost = -(row["change_7d"] or 0)
    if lost >= cfg.FOLLOWER_DROP_MIN:
        pct = 100 * lost / (row["followers"] + lost)
        if level := _level(pct, cfg.FOLLOWER_DROP_PCT):
            add(level, f"lost {lost:,} followers in 7 days ({pct:.1f}%)")
    if row["days_since_post"] is not None and (level := _level(row["days_since_post"], cfg.QUIET_DAYS)):
        add(level, f"no new post for {row['days_since_post']} days")
    if (row["engagement"] is not None and row["engagement_avg"]
            and row["engagement_days"] >= cfg.ENGAGEMENT_MIN_HISTORY):
        pct = 100 * (1 - row["engagement"] / row["engagement_avg"])
        if level := _level(pct, cfg.ENGAGEMENT_DROP_PCT):
            add(level, f"engagement {row['engagement']:.2f}% is {pct:.0f}% below its 30-day average "
                       f"({row['engagement_avg']:.2f}%)")
    return out


def client_concerns(client: dict, today: date) -> list[dict]:
    if client["next_date"] and client["next_date"] < today.isoformat():
        step = client["next_step"] or "next step"
        return [{"level": "medium", "text": f"{step} was due {client['next_date']}"}]
    return []


def client_view(con, client: dict, today: date) -> dict:
    """A client with each account's numbers and, for current clients, their concerns (high first)."""
    since = today - timedelta(days=cfg.HISTORY_DAYS)
    accounts = [summarize(a, db.history(con, a["id"], since), today) for a in db.accounts(con, client["id"])]
    concerns = []
    if client["stage"] == "active":
        concerns = client_concerns(client, today) + [c for a in accounts for c in account_concerns(a)]
        concerns.sort(key=lambda c: c["level"] != "high")
    return {**client, "accounts": accounts, "concerns": concerns}


def build(con, today: date) -> dict:
    """The daily report: every current client, those with high concerns first."""
    clients = [client_view(con, c, today) for c in db.clients(con) if c["stage"] == "active"]
    rank = lambda c: 0 if any(x["level"] == "high" for x in c["concerns"]) else 1 if c["concerns"] else 2
    clients.sort(key=lambda c: (rank(c), c["name"].lower()))
    concerns = [x for c in clients for x in c["concerns"]]
    return {
        "date": today.isoformat(),
        "generated_at": db.now_iso(),
        "totals": {
            "clients": len(clients),
            "attention": sum(1 for c in clients if c["concerns"]),
            "high": sum(1 for x in concerns if x["level"] == "high"),
            "medium": sum(1 for x in concerns if x["level"] == "medium"),
        },
        "clients": clients,
    }
