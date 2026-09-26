"""FastAPI app: serves the dashboard and its JSON state."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .engine import Station

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
station = Station()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(station.run())
    yield
    task.cancel()


app = FastAPI(title="ONYX", lifespan=lifespan)


@app.get("/api/state")
def state():
    return station.snapshot()


app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
