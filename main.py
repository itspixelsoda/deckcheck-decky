import asyncio
import os
import socket
import sys
import time

import decky

# Decky adds py_modules to the path on current versions; doing it here as well keeps older loaders working.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "py_modules"))

from deckcheck_core import export, stats  # noqa: E402
from deckcheck_core.share import Share  # noqa: E402
from deckcheck_core.tracker import Tracker  # noqa: E402

HEARTBEAT_SECONDS = 60
SHARE_SECONDS = 600
RANGE_DAYS = {"7d": 7, "30d": 30, "year": 365, "all": None}


class Plugin:
    tracker = None
    share = None
    heartbeat = None

    def _tracker(self):
        # Created on first use: the frontend may call in before _main has run.
        if self.tracker is None:
            os.makedirs(decky.DECKY_PLUGIN_RUNTIME_DIR, exist_ok=True)
            self.tracker = Tracker(os.path.join(decky.DECKY_PLUGIN_RUNTIME_DIR, "sessions.db"))
        return self.tracker

    async def _beat(self):
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            try:
                self._tracker().tick()
            except Exception:
                decky.logger.exception("heartbeat failed")

    async def _main(self):
        self._tracker()
        self.share = Share()
        self.heartbeat = asyncio.get_event_loop().create_task(self._beat())
        decky.logger.info("deckcheck loaded")

    async def _unload(self):
        # Sessions stay open on purpose: a game may still be running, and reconcile() sorts it out on the next load.
        if self.heartbeat:
            self.heartbeat.cancel()
        if self.share:
            self.share.stop()
        if self.tracker:
            self.tracker.tick()
            self.tracker.close()
            self.tracker = None

    async def _uninstall(self):
        pass

    # -- tracking, called by the frontend when Steam reports a change -------------------------

    async def game_started(self, appid: int, name: str, non_steam: bool, steamid):
        self._tracker().start(appid, name, non_steam, steamid)

    async def game_stopped(self, appid: int):
        self._tracker().stop(appid)

    async def reconcile(self, running: list):
        self._tracker().reconcile(running)

    # -- reading ------------------------------------------------------------------------------

    async def get_live(self):
        tracker = self._tracker()
        tracker.tick()
        sessions = tracker.sessions(include_open=True)
        summary = stats.summarize(sessions, time.time(), calendar_days=7)
        return {
            "playing": [s for s in sessions if s["open"]],
            "today": summary["today"],
            "week": summary["week"],
            "sessions": len([s for s in sessions if not s["open"]]),
        }

    async def get_summary(self, range_key: str, appid=None):
        tracker = self._tracker()
        tracker.tick()
        days = RANGE_DAYS.get(range_key)
        now = time.time()
        since = None if days is None else now - days * 86400
        return stats.summarize(tracker.sessions(include_open=True, appid=appid), now, since=since)

    async def get_sessions(self, limit: int, offset: int, appid=None):
        sessions = self._tracker().sessions(include_open=True, appid=appid)
        sessions.reverse()
        return {"total": len(sessions), "sessions": sessions[offset : offset + limit]}

    async def delete_session(self, session_id: str):
        self._tracker().delete(session_id)

    # -- export -------------------------------------------------------------------------------

    def _export(self):
        tracker = self._tracker()
        tracker.tick()
        document = export.build(tracker, time.time(), socket.gethostname())
        path = export.write(document, os.path.join(decky.DECKY_USER_HOME, "deckcheck"))
        return path, len(document["sessions"])

    async def export_sessions(self):
        path, count = self._export()
        return {"path": path, "sessions": count}

    async def start_share(self):
        path, count = self._export()
        url = self.share.start(path, export.FILE_NAME, SHARE_SECONDS)
        return {"url": url, "seconds": SHARE_SECONDS, "path": path, "sessions": count}

    async def stop_share(self):
        self.share.stop()
