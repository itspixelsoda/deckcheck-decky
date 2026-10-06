"""Records play sessions in SQLite.

Active time is measured with a monotonic clock. On Linux that clock stands still while the device
sleeps, so sleep is excluded from play time without relying on suspend/resume events arriving.
The gap between wall-clock time and monotonic time is what gets booked as "suspended".
"""

import sqlite3
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    steamid    TEXT,
    appid      INTEGER NOT NULL,
    name       TEXT NOT NULL,
    non_steam  INTEGER NOT NULL DEFAULT 0,
    start      INTEGER NOT NULL,
    last_seen  REAL NOT NULL,
    end        INTEGER,
    active     REAL NOT NULL DEFAULT 0,
    suspended  REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS sessions_end ON sessions (end);
CREATE INDEX IF NOT EXISTS sessions_appid ON sessions (appid);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# Launches that die straight away (crash on start, accidental press) are not sessions.
MIN_SESSION_SECONDS = 10
# After the plugin restarts, an open session is carried on only if it was seen this recently.
RESUME_WINDOW_SECONDS = 300


class Tracker:
    def __init__(self, path, wall=time.time, mono=time.monotonic):
        self._wall = wall
        self._mono = mono
        self._mono_at = None
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self):
        self.db.close()

    # -- meta -------------------------------------------------------------------------------

    def get_meta(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        self.db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
        self.db.commit()

    def device_id(self):
        device = self.get_meta("device_id")
        if not device:
            device = str(uuid.uuid4())
            self.set_meta("device_id", device)
        return device

    # -- tracking ---------------------------------------------------------------------------

    def _open(self):
        return self.db.execute("SELECT * FROM sessions WHERE end IS NULL").fetchall()

    def tick(self):
        """Books the time since the previous tick onto every open session. Call it often and before any change."""
        now_wall = self._wall()
        now_mono = self._mono()
        mono_delta = 0.0 if self._mono_at is None else max(0.0, now_mono - self._mono_at)
        self._mono_at = now_mono
        for row in self._open():
            wall_delta = max(0.0, now_wall - row["last_seen"])
            active = min(mono_delta, wall_delta)
            self.db.execute(
                "UPDATE sessions SET active = active + ?, suspended = suspended + ?, last_seen = ? WHERE id = ?",
                (active, wall_delta - active, now_wall, row["id"]),
            )
        self.db.commit()
        return now_wall

    def start(self, appid, name, non_steam=False, steamid=None):
        now = self.tick()
        existing = self.db.execute("SELECT id FROM sessions WHERE end IS NULL AND appid = ?", (appid,)).fetchone()
        if existing:
            # Steam sometimes announces the same launch twice.
            self.db.execute("UPDATE sessions SET name = ? WHERE id = ? AND name LIKE 'App %'", (name, existing["id"]))
            self.db.commit()
            return existing["id"]
        session_id = str(uuid.uuid4())
        self.db.execute(
            "INSERT INTO sessions (id, steamid, appid, name, non_steam, start, last_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, steamid, appid, name, 1 if non_steam else 0, int(now), now),
        )
        self.db.commit()
        return session_id

    def _finish(self, row, end):
        if row["active"] < MIN_SESSION_SECONDS:
            self.db.execute("DELETE FROM sessions WHERE id = ?", (row["id"],))
        else:
            self.db.execute("UPDATE sessions SET end = ? WHERE id = ?", (int(end), row["id"]))

    def stop(self, appid):
        now = self.tick()
        for row in self.db.execute("SELECT * FROM sessions WHERE end IS NULL AND appid = ?", (appid,)).fetchall():
            self._finish(row, now)
        self.db.commit()

    def reconcile(self, running):
        """Brings the database in line with what is actually running. Called when the plugin (re)starts.

        `running` is a list of dicts with appid, name, non_steam, steamid. A session left open by a
        previous run continues only if its game is still running and it was seen recently (the plugin
        was merely reloaded). Otherwise it ended while nobody was watching - power loss, crash, reboot -
        and is closed at the last moment it was known to be alive.
        """
        now_wall = self._wall()
        first_run_of_process = self._mono_at is None
        self._mono_at = self._mono()
        running_ids = {app["appid"] for app in running}
        for row in self._open():
            gap = now_wall - row["last_seen"]
            if row["appid"] in running_ids and 0 <= gap <= RESUME_WINDOW_SECONDS:
                if first_run_of_process:
                    # The game kept running through the reload, so the short gap was play time.
                    self.db.execute("UPDATE sessions SET active = active + ?, last_seen = ? WHERE id = ?", (gap, now_wall, row["id"]))
            else:
                self._finish(row, row["last_seen"])
        self.db.commit()
        for app in running:
            self.start(app["appid"], app["name"], app.get("non_steam", False), app.get("steamid"))

    def close_all(self):
        now = self.tick()
        for row in self._open():
            self._finish(row, now)
        self.db.commit()

    # -- reading ----------------------------------------------------------------------------

    def sessions(self, include_open=False, appid=None):
        """Sessions as plain dicts, oldest first. Open sessions, when included, end at their last tick."""
        query = "SELECT * FROM sessions"
        clauses, params = [], []
        if not include_open:
            clauses.append("end IS NOT NULL")
        if appid is not None:
            clauses.append("appid = ?")
            params.append(appid)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        rows = self.db.execute(query + " ORDER BY start", params).fetchall()
        return [
            {
                "id": r["id"],
                "steamid": r["steamid"],
                "appid": r["appid"],
                "name": r["name"],
                "nonSteam": bool(r["non_steam"]),
                "start": r["start"],
                "end": r["end"] if r["end"] is not None else int(r["last_seen"]),
                "open": r["end"] is None,
                "activeSeconds": int(round(r["active"])),
                "suspendedSeconds": int(round(r["suspended"])),
            }
            for r in rows
        ]

    def delete(self, session_id):
        self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.db.commit()
