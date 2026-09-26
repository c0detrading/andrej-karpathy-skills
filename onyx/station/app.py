"""FastAPI app: serves the dashboard and its JSON API."""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import settings as settings_mod
from .engine import Station
from .telegram import TelegramError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
station = Station()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(station.run())
    yield
    task.cancel()


app = FastAPI(title="ONYX", lifespan=lifespan)

# ---- access control -------------------------------------------------------
# Locally, ONYX only answers requests addressed to this computer (blocks DNS-rebinding tricks).
# When hosted, ONYX_ALLOWED_HOSTS adds the server's name and ONYX_PASSWORD puts a login in front.
PASSWORD = os.environ.get("ONYX_PASSWORD", "")
EXTRA_HOSTS = [h.strip() for h in os.environ.get("ONYX_ALLOWED_HOSTS", "").split(",") if h.strip()]
COOKIE = "onyx_session"


def _session_secret() -> bytes:
    path = settings_mod.DATA_DIR / "session.key"
    try:
        return path.read_bytes()
    except FileNotFoundError:
        settings_mod.DATA_DIR.mkdir(exist_ok=True)
        key = secrets.token_bytes(32)
        path.write_bytes(key)
        return key


def _session_token() -> str:
    return hmac.new(_session_secret(), PASSWORD.encode(), hashlib.sha256).hexdigest()


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>ONYX login</title>
<link rel="stylesheet" href="/style.css"></head><body>
<main style="display:block;max-width:360px;margin:12vh auto"><section class="panel">
<h2>ONYX</h2><form method="post" action="/login" class="form-grid">
<label>Password <input name="password" type="password" autofocus autocomplete="current-password"></label>
<button class="on" type="submit">Log in</button></form><p class="bear">{error}</p></section></main></body></html>"""


@app.middleware("http")
async def require_login(request: Request, call_next):
    if PASSWORD and request.url.path not in ("/login", "/style.css"):
        if not hmac.compare_digest(request.cookies.get(COOKIE, ""), _session_token()):
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "Log in first"}, status_code=401)
            return RedirectResponse("/login", status_code=303)
    return await call_next(request)


app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", *EXTRA_HOSTS])


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return LOGIN_PAGE.format(error="")


@app.post("/login")
async def login(request: Request):
    password = parse_qs((await request.body()).decode()).get("password", [""])[0]
    if not PASSWORD or not hmac.compare_digest(password.encode(), PASSWORD.encode()):
        await asyncio.sleep(1)  # slow down guessing
        return HTMLResponse(LOGIN_PAGE.format(error="Wrong password."), status_code=401)
    resp = RedirectResponse("/", status_code=303)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    resp.set_cookie(COOKIE, _session_token(), httponly=True, samesite="strict", secure=https, max_age=30 * 86400)
    return resp


async def _json_body(request: Request) -> dict:
    # Requiring JSON means other websites can't post here without a CORS preflight, which we never allow.
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Expected application/json")
    return await request.json()


@app.get("/api/state")
def state():
    return station.snapshot()


@app.get("/api/stream")
async def stream(request: Request):
    """Server-sent events: the full state after every engine tick (about every 10 seconds)."""
    async def events():
        version = -1
        while not await request.is_disconnected():
            if station.version != version:
                version = station.version
                yield f"data: {json.dumps(jsonable_encoder(station.snapshot()))}\n\n"
            try:
                await asyncio.wait_for(station.updated.wait(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/chart")
def chart(asset: str, tf: str):
    data = station.chart(asset, tf)
    if data is None:
        raise HTTPException(404, "No chart data yet")
    return data


@app.get("/api/settings")
def get_settings():
    return settings_mod.public(station.settings)


@app.post("/api/settings")
async def post_settings(request: Request):
    try:
        station.update_settings(await _json_body(request))
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return settings_mod.public(station.settings)


@app.post("/api/telegram/test")
async def telegram_test(request: Request):
    await _json_body(request)
    if not (station.settings["telegram_token"] and station.settings["telegram_chat_id"]):
        raise HTTPException(400, "Save a bot token and chat ID first")
    try:
        await station.send_test_telegram()
    except TelegramError as e:
        raise HTTPException(502, f"Telegram said: {e}")
    return {"ok": True}


@app.post("/api/briefing")
async def briefing(request: Request):
    await _json_body(request)
    station.briefing = station.build_briefing(datetime.now(timezone.utc))
    return station.briefing


@app.get("/api/tuning")
def tuning():
    return station.tuning


@app.post("/api/tune")
async def retune(request: Request):
    await _json_body(request)
    return await asyncio.to_thread(station.retune)


@app.post("/api/shutdown")
async def shutdown(request: Request):
    """Stop ONYX (used by the Stop button when it runs in the background)."""
    await _json_body(request)
    asyncio.get_running_loop().call_later(0.5, os._exit, 0)
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
