"""Background job: once a day, fetch Instagram and Facebook numbers, then save the daily report."""

import asyncio
import logging
from datetime import date, datetime, timezone

import httpx

from . import db, meta, report, settings as settings_mod
from .config import PLATFORMS

log = logging.getLogger("volstro")


class Worker:
    def __init__(self):
        self.settings = settings_mod.load()
        self.lock = asyncio.Lock()  # one fetch at a time

    async def run(self):
        while True:
            try:
                if self._due():
                    await self.daily()
            except Exception:
                log.exception("Daily report failed")
            await asyncio.sleep(60)

    def _due(self) -> bool:
        """Past the report time and no report yet today (also catches up when started late)."""
        now = datetime.now()
        if now.strftime("%H:%M") < self.settings["report_time"]:
            return False
        with db.connect() as con:
            return db.report(con, now.date().isoformat()) is None

    async def daily(self) -> dict:
        async with self.lock:
            await self._fetch()
            with db.connect() as con:
                rep = report.build(con, date.today())
                if not self.settings["meta_token"] and any(
                        PLATFORMS[a["platform"]] == "auto" for c in rep["clients"] for a in c["accounts"]):
                    rep["notice"] = "Instagram and Facebook numbers aren't fetched until a Meta access token is added in Settings."
                db.save_report(con, rep)
        log.info("Daily report saved: %s", rep["totals"])
        return rep

    async def fetch(self, account_ids: list[int]):
        async with self.lock:
            await self._fetch(account_ids)

    def update_settings(self, changes: dict):
        self.settings = settings_mod.update(self.settings, changes)
        settings_mod.save(self.settings)

    async def _fetch(self, account_ids: list[int] | None = None):
        """Today's numbers for every Instagram/Facebook account of a client that isn't lost."""
        token = self.settings["meta_token"]
        if not token:
            return  # the report says so once, instead of an error on every account
        with db.connect() as con:
            todo = [a for a in db.accounts(con)
                    if PLATFORMS[a["platform"]] == "auto" and a["stage"] != "lost"
                    and (account_ids is None or a["id"] in account_ids)]
        if not todo:
            return
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=20) as client:
            for a in todo:
                numbers, error = None, ""
                try:
                    if a["platform"] == "instagram":
                        numbers = await meta.instagram(client, token, await self._ig_user_id(client), a["handle"], now)
                    else:
                        numbers = await meta.facebook(client, token, a["handle"], now)
                except meta.MetaError as e:
                    error = str(e)
                except (KeyError, TypeError, ValueError) as e:  # a reply shaped differently than documented
                    error = f"unexpected reply from Meta ({type(e).__name__}: {e})"
                if error:
                    log.warning("%s @%s: %s", a["platform"], a["handle"], error)
                with db.connect() as con:
                    if numbers:
                        db.save_snapshot(con, a["id"], date.today(), numbers, "auto")
                    db.set_fetch_error(con, a["id"], error)

    async def _ig_user_id(self, client) -> str:
        if not self.settings["ig_user_id"]:
            found = await meta.check(client, self.settings["meta_token"])
            if not found["instagram"]:
                raise meta.MetaError("no Instagram business account is linked to the Pages this Meta token can see")
            self.settings["ig_user_id"] = found["instagram"]["id"]
            settings_mod.save(self.settings)
        return self.settings["ig_user_id"]
