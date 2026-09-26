import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    def make(password=""):
        monkeypatch.setenv("ONYX_PASSWORD", password)
        import station.app as app_mod
        app_mod = importlib.reload(app_mod)
        app_mod.station.run = lambda: _noop()  # don't hit the network from tests
        return TestClient(app_mod.app, base_url="http://localhost")
    return make


async def _noop():
    return None


def test_local_mode_needs_json_and_known_host(client):
    c = client()
    with c:
        assert c.get("/api/state").status_code == 200
        assert c.post("/api/settings", content="{}", headers={"Content-Type": "text/plain"}).status_code == 415
        assert c.get("/api/state", headers={"Host": "evil.example"}).status_code == 400
        r = c.post("/api/settings", json={"oanda_token": "tok", "use_tuning": False})
        assert r.status_code == 200 and r.json()["oanda_token"] == "••••••••" and r.json()["use_tuning"] is False


def test_password_mode(client):
    c = client("pw")
    with c:
        assert c.get("/api/state").status_code == 401
        assert c.get("/", follow_redirects=False).status_code == 303
        assert c.post("/login", content="password=bad", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 401
        r = c.post("/login", content="password=pw", headers={"Content-Type": "application/x-www-form-urlencoded"}, follow_redirects=False)
        assert r.status_code == 303 and "onyx_session" in r.cookies
        assert c.get("/api/state").status_code == 200
