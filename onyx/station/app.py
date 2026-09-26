"""FastAPI app: serves the dashboard and its JSON API."""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
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
# Only answer requests addressed to this computer (blocks DNS-rebinding tricks from other sites).
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])


async def _json_body(request: Request) -> dict:
    # Requiring JSON means other websites can't post here without a CORS preflight, which we never allow.
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Expected application/json")
    return await request.json()


@app.get("/api/state")
def state():
    return station.snapshot()


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


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
