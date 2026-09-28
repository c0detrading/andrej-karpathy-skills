import importlib
from datetime import date

import pytest
from fastapi.testclient import TestClient

from pipeline import meta


@pytest.fixture
def client(monkeypatch):
    def make(password=""):
        monkeypatch.setenv("VOLSTRO_PASSWORD", password)
        import pipeline.app as app_mod
        app_mod = importlib.reload(app_mod)
        app_mod.worker.run = _noop  # no background job in tests
        return TestClient(app_mod.app, base_url="http://localhost"), app_mod
    return make


async def _noop():
    return None


def test_local_mode_needs_json_and_known_host(client):
    c, _ = client()
    with c:
        assert c.get("/api/board").status_code == 200
        assert c.post("/api/clients", content='{"name": "x"}', headers={"Content-Type": "text/plain"}).status_code == 415
        assert c.get("/api/board", headers={"Host": "evil.example"}).status_code == 400
        r = c.post("/api/settings", json={"meta_token": "tok", "report_time": "07:30"})
        assert r.status_code == 200 and r.json()["meta_token"] == "••••••••" and r.json()["report_time"] == "07:30"
        assert c.post("/api/settings", json={"report_time": "7am"}).status_code == 400


def test_password_mode(client):
    c, _ = client("pw")
    with c:
        assert c.get("/api/board").status_code == 401
        assert c.get("/", follow_redirects=False).status_code == 303
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        assert c.post("/login", content="password=bad", headers=form).status_code == 401
        r = c.post("/login", content="password=pw", headers=form, follow_redirects=False)
        assert r.status_code == 303 and "volstro_session" in r.cookies
        assert c.get("/api/board").status_code == 200


def test_clients_accounts_and_numbers(client):
    c, _ = client()
    with c:
        assert c.post("/api/clients", json={"name": " "}).status_code == 400
        assert c.post("/api/clients", json={"name": "Acme", "stage": "nope"}).status_code == 400
        cid = c.post("/api/clients", json={"name": "Acme", "value": 1500, "next_date": "2026-10-01"}).json()["id"]
        assert c.patch(f"/api/clients/{cid}", json={"stage": "active"}).json()["stage"] == "active"
        assert c.patch("/api/clients/999", json={"stage": "active"}).status_code == 404

        r = c.post(f"/api/clients/{cid}/accounts", json={"platform": "tiktok", "handle": "https://www.tiktok.com/@Acme.Studio"})
        aid = r.json()["id"]
        assert c.post(f"/api/clients/{cid}/accounts", json={"platform": "tiktok", "handle": "@acme.studio"}).status_code == 400
        assert c.post(f"/api/clients/{cid}/accounts", json={"platform": "myspace", "handle": "acme"}).status_code == 400
        assert c.post(f"/api/accounts/{aid}/numbers", json={"followers": "abc"}).status_code == 400
        assert c.post(f"/api/accounts/{aid}/numbers", json={"followers": "12,450", "avg_likes": "310"}).status_code == 200

        acme = c.get("/api/board").json()["clients"][0]
        assert acme["value"] == 1500 and acme["accounts"][0]["handle"] == "acme.studio"
        assert acme["accounts"][0]["followers"] == 12450 and acme["accounts"][0]["source"] == "manual"

        assert c.delete(f"/api/clients/{cid}").status_code == 200
        assert c.get("/api/board").json()["clients"] == []


def test_instagram_account_fetches_on_add_and_reports(client, monkeypatch):
    c, app_mod = client()

    async def fake_check(http, token):
        return {"pages": ["Volstro"], "instagram": {"id": "178", "username": "volstro"}}

    async def fake_instagram(http, token, ig_user_id, username, now):
        assert (token, ig_user_id) == ("tok", "178")
        return {"followers": 900, "posts_7d": 2, "avg_likes": 50.0, "avg_comments": 4.0, "last_post": "2026-09-01"}

    monkeypatch.setattr(meta, "check", fake_check)
    monkeypatch.setattr(meta, "instagram", fake_instagram)
    with c:
        cid = c.post("/api/clients", json={"name": "Acme", "stage": "active"}).json()["id"]
        # No token yet: the account is added and the report says once why it has no numbers.
        c.post(f"/api/clients/{cid}/accounts", json={"platform": "instagram", "handle": "@acme"})
        rep = c.post("/api/report", json={}).json()
        assert "Meta access token" in rep["notice"]
        assert rep["clients"][0]["concerns"] == [{"level": "medium", "text": "Instagram @acme: no numbers yet"}]

        c.post("/api/settings", json={"meta_token": "tok"})
        rep = c.post("/api/report", json={}).json()
        account = rep["clients"][0]["accounts"][0]
        assert account["followers"] == 900 and account["error"] == "" and "notice" not in rep
        assert app_mod.worker.settings["ig_user_id"] == "178"
        assert c.get("/api/reports").json()["dates"] == [date.today().isoformat()]
        assert c.get(f"/api/reports/{date.today().isoformat()}").json()["totals"]["clients"] == 1


def test_csv_import(client):
    c, _ = client()
    with c:
        cid = c.post("/api/clients", json={"name": "Acme", "stage": "active"}).json()["id"]
        c.post(f"/api/clients/{cid}/accounts", json={"platform": "tiktok", "handle": "acme"})
        # Semicolons, as Excel saves CSVs in many European locales.
        csv = ("﻿date;platform;handle;followers;posts_7d;avg_likes;avg_comments;last_post\n"
               "2026-09-27;TikTok;@acme;3200;4;410;22;2026-09-26\n"
               "2026-09-27;tiktok;someoneelse;100;;;;\n")
        r = c.post("/api/import", json={"csv": csv}).json()
        assert r["imported"] == 1 and len(r["skipped"]) == 1 and "someoneelse" in r["skipped"][0]
        assert c.post("/api/import", json={"csv": "a,b\n1,2\n"}).status_code == 400
        assert c.get("/api/board").json()["clients"][0]["accounts"][0]["followers"] == 3200


def test_unexpected_meta_reply_is_reported_not_fatal(client, monkeypatch):
    c, _ = client()

    async def fake_facebook(http, token, page, now):
        return {}["followers_count"]  # a reply without the field we expect

    monkeypatch.setattr(meta, "facebook", fake_facebook)
    with c:
        c.post("/api/settings", json={"meta_token": "tok"})
        cid = c.post("/api/clients", json={"name": "Acme", "stage": "active"}).json()["id"]
        c.post(f"/api/clients/{cid}/accounts", json={"platform": "facebook", "handle": "acme"})
        rep = c.post("/api/report", json={}).json()
        assert "unexpected reply from Meta (KeyError" in rep["clients"][0]["concerns"][0]["text"]
