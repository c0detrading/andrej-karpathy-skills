"""FastAPI app: serves the pipeline board, the daily report and their JSON API."""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db, meta, report, settings as settings_mod
from .config import PLATFORMS, STAGES
from .worker import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # its request lines would log the Meta token
worker = Worker()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(worker.run())
    yield
    task.cancel()


app = FastAPI(title="Volstro Pipeline", lifespan=lifespan)

# ---- access control -------------------------------------------------------
# Locally, the app only answers requests addressed to this computer (blocks DNS-rebinding tricks).
# When hosted, VOLSTRO_ALLOWED_HOSTS adds the server's name and VOLSTRO_PASSWORD puts a login in front.
PASSWORD = os.environ.get("VOLSTRO_PASSWORD", "")
EXTRA_HOSTS = [h.strip() for h in os.environ.get("VOLSTRO_ALLOWED_HOSTS", "").split(",") if h.strip()]
COOKIE = "volstro_session"


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
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Volstro login</title>
<link rel="stylesheet" href="/style.css"></head><body>
<main class="narrow"><section class="panel">
<h2>Volstro Pipeline</h2><form method="post" action="/login" class="form-grid">
<label>Password <input name="password" type="password" autofocus autocomplete="current-password"></label>
<button class="primary" type="submit">Log in</button></form><p class="error">{error}</p></section></main></body></html>"""


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
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Expected a JSON object")
    return body


def _clean(fn, *args):
    try:
        return fn(*args)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))


# ---- pipeline -------------------------------------------------------------

@app.get("/api/board")
def board():
    today = date.today()
    with db.connect() as con:
        clients = [report.client_view(con, c, today) for c in db.clients(con)]
    return {"clients": clients, "stages": STAGES, "platforms": PLATFORMS,
            "currency": worker.settings["currency"], "today": today.isoformat()}


@app.post("/api/clients")
async def create_client(request: Request):
    data = _clean(db.clean_client, await _json_body(request))
    with db.connect() as con:
        return {"id": db.create_client(con, data)}


@app.patch("/api/clients/{cid}")
async def update_client(cid: int, request: Request):
    data = _clean(db.clean_client, await _json_body(request), True)
    with db.connect() as con:
        if not db.update_client(con, cid, data):
            raise HTTPException(404, "No such client")
        return db.client(con, cid)


@app.delete("/api/clients/{cid}")
def delete_client(cid: int):
    with db.connect() as con:
        if not db.delete_client(con, cid):
            raise HTTPException(404, "No such client")
    return {"ok": True}


@app.post("/api/clients/{cid}/accounts")
async def add_account(cid: int, request: Request):
    body = await _json_body(request)
    platform = body.get("platform")
    handle = _clean(db.clean_handle, platform, body.get("handle"))
    with db.connect() as con:
        if not db.client(con, cid):
            raise HTTPException(404, "No such client")
        try:
            aid = db.add_account(con, cid, platform, handle)
        except sqlite3.IntegrityError:
            raise HTTPException(400, f"{platform} @{handle} is already added")
    if PLATFORMS[platform] == "auto":
        await worker.fetch([aid])  # show its numbers straight away
    return {"id": aid}


@app.delete("/api/accounts/{aid}")
def delete_account(aid: int):
    with db.connect() as con:
        if not db.delete_account(con, aid):
            raise HTTPException(404, "No such account")
    return {"ok": True}


@app.post("/api/accounts/{aid}/numbers")
async def add_numbers(aid: int, request: Request):
    day, numbers = _clean(db.clean_numbers, await _json_body(request))
    with db.connect() as con:
        if not db.account(con, aid):
            raise HTTPException(404, "No such account")
        db.save_snapshot(con, aid, day, numbers, "manual")
    return {"ok": True}


@app.post("/api/import")
async def import_csv(request: Request):
    body = await _json_body(request)
    with db.connect() as con:
        return _clean(db.import_csv, con, str(body.get("csv", "")))


# ---- daily report ---------------------------------------------------------

@app.get("/api/reports")
def report_dates():
    with db.connect() as con:
        return {"dates": db.report_dates(con)}


@app.get("/api/reports/{day}")
def get_report(day: str):
    with db.connect() as con:
        rep = db.report(con, day)
    if rep is None:
        raise HTTPException(404, "No report for that day")
    return rep


@app.post("/api/report")
async def new_report(request: Request):
    """Fetch today's numbers now and rebuild today's report."""
    await _json_body(request)
    return await worker.daily()


# ---- settings -------------------------------------------------------------

@app.get("/api/settings")
def get_settings():
    return settings_mod.public(worker.settings)


@app.post("/api/settings")
async def post_settings(request: Request):
    _clean(worker.update_settings, await _json_body(request))
    return settings_mod.public(worker.settings)


@app.post("/api/meta/check")
async def meta_check(request: Request):
    """Test the saved Meta token: which Pages it sees and which Instagram account the lookups use."""
    await _json_body(request)
    if not worker.settings["meta_token"]:
        raise HTTPException(400, "Save a Meta access token first")
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            found = await meta.check(client, worker.settings["meta_token"])
        except meta.MetaError as e:
            raise HTTPException(502, f"Meta said: {e}")
    if found["instagram"]:
        worker.settings["ig_user_id"] = found["instagram"]["id"]
        settings_mod.save(worker.settings)
    return found


@app.post("/api/shutdown")
async def shutdown(request: Request):
    """Stop the app (used by the Stop button)."""
    await _json_body(request)
    asyncio.get_running_loop().call_later(0.5, os._exit, 0)
    return {"ok": True}


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
