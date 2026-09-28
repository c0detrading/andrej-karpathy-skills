from datetime import date, timedelta

import pytest

from pipeline import db, report

TODAY = date(2026, 9, 28)


def snaps(followers, likes=None, comments=0, last_post="2026-09-27", posts_7d=3):
    """Daily snapshots ending today, one per value in `followers` (and `likes`)."""
    likes = likes or [100] * len(followers)
    start = TODAY - timedelta(days=len(followers) - 1)
    return [{"date": (start + timedelta(days=i)).isoformat(), "followers": f, "avg_likes": l,
             "avg_comments": comments, "posts_7d": posts_7d, "last_post": last_post, "source": "auto"}
            for i, (f, l) in enumerate(zip(followers, likes))]


def row(history, platform="instagram", error=""):
    account = {"id": 1, "platform": platform, "handle": "acme", "last_error": error}
    return report.summarize(account, history, TODAY)


def texts(r):
    return [(c["level"], c["text"]) for c in report.account_concerns(r)]


def test_summary_changes_and_engagement():
    r = row(snaps([1000] * 23 + [1005, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080]))
    assert r["followers"] == 1080 and r["change_1d"] == 10 and r["change_7d"] == 70 and r["change_30d"] == 80
    assert r["engagement"] == pytest.approx(9.26, abs=0.01)  # 100 likes / 1080 followers
    assert r["days_since_post"] == 1 and r["age_days"] == 0
    assert texts(r) == []


def test_changes_need_enough_history():
    r = row(snaps([1000, 990]))
    assert r["change_1d"] == -10 and r["change_7d"] is None and r["change_30d"] is None


def test_follower_drop_levels():
    assert texts(row(snaps([10000] * 7 + [9850]))) == [
        ("medium", "Instagram @acme: lost 150 followers in 7 days (1.5%)")]
    assert texts(row(snaps([10000] * 7 + [9600])))[0][0] == "high"
    # A small account losing a few followers is noise, even as a big percentage.
    assert texts(row(snaps([300] * 7 + [292]))) == []


def test_quiet_account():
    assert texts(row(snaps([500], last_post="2026-09-20"))) == [("medium", "Instagram @acme: no new post for 8 days")]
    assert texts(row(snaps([500], last_post="2026-09-10")))[0][0] == "high"


def test_engagement_drop_needs_history():
    few = snaps([1000] * 5, likes=[100, 100, 100, 100, 40])
    assert texts(row(few)) == []  # only 4 earlier days: not enough to judge
    many = snaps([1000] * 10, likes=[100] * 9 + [60])
    assert texts(row(many)) == [
        ("medium", "Instagram @acme: engagement 6.00% is 40% below its 30-day average (10.00%)")]
    assert texts(row(snaps([1000] * 10, likes=[100] * 9 + [40])))[0][0] == "high"


def test_stale_and_missing_numbers():
    old = snaps([1000])
    old[0]["date"] = "2026-09-24"
    assert ("medium", "Instagram @acme: latest numbers are 4 days old") in texts(row(old))
    # TikTok numbers are typed in, so a weekly update isn't stale.
    assert texts(row(old, platform="tiktok")) == []
    assert texts(row([], platform="tiktok")) == [
        ("medium", "TikTok @acme: no numbers yet, type them in or import a CSV")]
    assert texts(row([], error="Invalid token")) == [
        ("high", "Instagram @acme: couldn't fetch today's numbers: Invalid token")]


def test_report_lists_current_clients_worst_first():
    with db.connect() as con:
        calm = db.create_client(con, db.clean_client({"name": "Calm Co", "stage": "active"}))
        late = db.create_client(con, db.clean_client(
            {"name": "Late Co", "stage": "active", "next_step": "Send invoice", "next_date": "2026-09-20"}))
        db.create_client(con, db.clean_client({"name": "Prospect Co", "stage": "proposal"}))
        broken = db.create_client(con, db.clean_client({"name": "Broken Co", "stage": "active"}))
        aid = db.add_account(con, broken, "instagram", "broken")
        db.set_fetch_error(con, aid, "Invalid token")
        rep = report.build(con, TODAY)
    assert [c["name"] for c in rep["clients"]] == ["Broken Co", "Late Co", "Calm Co"]
    assert rep["clients"][1]["concerns"] == [{"level": "medium", "text": "Send invoice was due 2026-09-20"}]
    assert rep["totals"] == {"clients": 3, "attention": 2, "high": 1, "medium": 1}
    assert calm and late
