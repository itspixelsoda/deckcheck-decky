import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py_modules"))

from deckcheck_core import export, stats  # noqa: E402
from deckcheck_core.share import Share  # noqa: E402
from deckcheck_core.tracker import Tracker  # noqa: E402

UTC = timezone.utc
T0 = int(datetime(2026, 10, 6, 20, 0, tzinfo=UTC).timestamp())


class Clock:
    """Wall and monotonic clocks that the test moves by hand. Sleeping advances only the wall clock."""

    def __init__(self):
        self.wall_now = float(T0)
        self.mono_now = 1000.0

    def play(self, seconds):
        self.wall_now += seconds
        self.mono_now += seconds

    def sleep(self, seconds):
        self.wall_now += seconds

    def reboot(self):
        self.mono_now = 5.0


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "sessions.db")
        self.clock = Clock()
        self.tracker = self.open()

    def tearDown(self):
        self.tracker.close()
        self.dir.cleanup()

    def open(self):
        return Tracker(self.path, wall=lambda: self.clock.wall_now, mono=lambda: self.clock.mono_now)

    def restart(self):
        self.tracker.close()
        self.tracker = self.open()

    def test_counts_a_plain_session(self):
        self.tracker.start(730, "Counter-Strike 2", steamid="7656")
        self.clock.play(3600)
        self.tracker.stop(730)
        (s,) = self.tracker.sessions()
        self.assertEqual((s["appid"], s["name"], s["steamid"], s["open"]), (730, "Counter-Strike 2", "7656", False))
        self.assertEqual((s["start"], s["end"], s["activeSeconds"], s["suspendedSeconds"]), (T0, T0 + 3600, 3600, 0))

    def test_sleep_is_not_play_time_even_without_any_suspend_event(self):
        self.tracker.start(1, "Game")
        self.clock.play(600)
        self.clock.sleep(8 * 3600)
        self.clock.play(300)
        self.tracker.stop(1)
        (s,) = self.tracker.sessions()
        self.assertEqual(s["activeSeconds"], 900)
        self.assertEqual(s["suspendedSeconds"], 8 * 3600)
        self.assertEqual(s["end"] - s["start"], 900 + 8 * 3600)

    def test_heartbeats_do_not_change_the_result(self):
        self.tracker.start(1, "Game")
        for _ in range(30):
            self.clock.play(60)
            self.tracker.tick()
        self.clock.sleep(1000)
        self.tracker.tick()
        self.clock.play(120)
        self.tracker.stop(1)
        (s,) = self.tracker.sessions()
        self.assertEqual((s["activeSeconds"], s["suspendedSeconds"]), (1920, 1000))

    def test_drops_launches_that_end_immediately(self):
        self.tracker.start(1, "Crashy")
        self.clock.play(4)
        self.tracker.stop(1)
        self.assertEqual(self.tracker.sessions(), [])

    def test_duplicate_start_and_unknown_stop_are_harmless(self):
        first = self.tracker.start(1, "App 1")
        self.clock.play(100)
        self.assertEqual(self.tracker.start(1, "Real Name"), first)
        self.tracker.stop(999)
        self.clock.play(100)
        self.tracker.stop(1)
        (s,) = self.tracker.sessions()
        self.assertEqual((s["activeSeconds"], s["name"]), (200, "Real Name"))

    def test_two_games_at_once_are_tracked_separately(self):
        self.tracker.start(1, "A")
        self.clock.play(100)
        self.tracker.start(2, "B")
        self.clock.play(50)
        self.tracker.stop(1)
        self.clock.play(25)
        self.tracker.stop(2)
        by_name = {s["name"]: s["activeSeconds"] for s in self.tracker.sessions()}
        self.assertEqual(by_name, {"A": 150, "B": 75})

    def test_power_loss_closes_the_session_at_the_last_heartbeat(self):
        self.tracker.start(1, "Game")
        self.clock.play(600)
        self.tracker.tick()
        self.clock.play(40)  # dies here, before the next heartbeat
        self.clock.sleep(3 * 86400)
        self.clock.reboot()
        self.restart()
        self.tracker.reconcile([])
        (s,) = self.tracker.sessions()
        self.assertEqual((s["activeSeconds"], s["end"], s["open"]), (600, T0 + 600, False))

    def test_plugin_reload_while_the_game_runs_keeps_the_session(self):
        first = self.tracker.start(1, "Game")
        self.clock.play(600)
        self.tracker.tick()
        self.clock.play(20)
        self.restart()
        self.tracker.reconcile([{"appid": 1, "name": "Game"}])
        self.clock.play(100)
        self.tracker.stop(1)
        (s,) = self.tracker.sessions()
        self.assertEqual((s["id"], s["activeSeconds"]), (first, 720))

    def test_reconcile_starts_sessions_for_games_already_running(self):
        self.tracker.reconcile([{"appid": 5, "name": "Already Running", "non_steam": True, "steamid": "7656"}])
        self.clock.play(60)
        (s,) = self.tracker.sessions(include_open=True)
        self.assertEqual((s["open"], s["nonSteam"], s["steamid"]), (True, True, "7656"))
        self.tracker.reconcile([{"appid": 5, "name": "Already Running"}])
        self.assertEqual(len(self.tracker.sessions(include_open=True)), 1)

    def test_stale_open_session_is_closed_even_if_the_same_game_runs_again(self):
        self.tracker.start(1, "Game")
        self.clock.play(600)
        self.tracker.tick()
        self.clock.sleep(86400)
        self.clock.reboot()
        self.restart()
        self.tracker.reconcile([{"appid": 1, "name": "Game"}])
        sessions = self.tracker.sessions(include_open=True)
        self.assertEqual([s["open"] for s in sessions], [False, True])

    def test_export_contains_closed_sessions_only_and_a_stable_device_id(self):
        self.tracker.start(1, "Done")
        self.clock.play(100)
        self.tracker.stop(1)
        self.tracker.start(2, "Still Running")
        self.clock.play(100)
        doc = export.build(self.tracker, self.clock.wall_now, "steamdeck")
        self.assertEqual((doc["format"], doc["version"], doc["device"]["name"]), ("deckcheck-sessions", 1, "steamdeck"))
        self.assertEqual([s["name"] for s in doc["sessions"]], ["Done"])
        self.assertEqual(set(doc["sessions"][0]), {"id", "steamid", "appid", "name", "nonSteam", "start", "end", "activeSeconds", "suspendedSeconds"})
        self.restart()
        self.assertEqual(export.build(self.tracker, 0, "x")["device"]["id"], doc["device"]["id"])
        path = export.write(doc, os.path.join(self.dir.name, "out"))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), doc)


def session(start, minutes, appid=1, name="Game", suspended=0, non_steam=False):
    start_ts = int(start.timestamp())
    return {"id": "x", "steamid": None, "appid": appid, "name": name, "nonSteam": non_steam, "start": start_ts,
            "end": start_ts + minutes * 60 + suspended, "open": False, "activeSeconds": minutes * 60, "suspendedSeconds": suspended}


class StatsTest(unittest.TestCase):
    now = datetime(2026, 10, 6, 22, 0, tzinfo=UTC)

    def test_splits_a_session_across_hours_and_midnight(self):
        buckets = stats.hourly_buckets([session(datetime(2026, 10, 5, 23, 30, tzinfo=UTC), 90)], UTC)
        self.assertEqual({k: round(v) for k, v in buckets.items()}, {("2026-10-05", 23): 1800, ("2026-10-06", 0): 3600})

    def test_respects_the_time_zone(self):
        warsaw = timezone(timedelta(hours=2))
        buckets = stats.hourly_buckets([session(datetime(2026, 10, 5, 21, 30, tzinfo=UTC), 60)], warsaw)
        self.assertEqual({k: round(v) for k, v in buckets.items()}, {("2026-10-05", 23): 1800, ("2026-10-06", 0): 1800})

    def test_bucket_totals_equal_active_time_even_with_a_sleep_inside(self):
        s = session(datetime(2026, 10, 5, 10, 0, tzinfo=UTC), 60, suspended=5 * 3600)
        self.assertAlmostEqual(sum(stats.hourly_buckets([s], UTC).values()), 3600, places=3)

    def test_summary(self):
        sessions = [
            session(datetime(2026, 10, 6, 20, 0, tzinfo=UTC), 60, appid=1, name="A"),
            session(datetime(2026, 10, 3, 9, 0, tzinfo=UTC), 20, appid=1, name="A"),
            session(datetime(2026, 9, 1, 12, 0, tzinfo=UTC), 180, appid=2, name="B"),
        ]
        out = stats.summarize(sessions, self.now.timestamp(), UTC)
        self.assertEqual((out["today"], out["week"]), (3600, 4800))
        self.assertEqual(out["totals"]["seconds"], 260 * 60)
        self.assertEqual((out["totals"]["sessions"], out["totals"]["games"], out["totals"]["daysPlayed"]), (3, 2, 3))
        self.assertEqual([g["name"] for g in out["games"]], ["B", "A"])
        self.assertEqual(out["games"][1]["sessions"], 2)
        self.assertEqual(out["longest"]["name"], "B")
        self.assertEqual(out["hours"][20], 3600)
        self.assertEqual(out["weekdays"][1], 3600 + 180 * 60)  # both Oct 6 and Sep 1, 2026 are Tuesdays
        self.assertEqual(out["grid"][1][20], 3600)
        self.assertEqual(len(out["calendar"]), 182)
        self.assertEqual(out["calendar"][-1], {"date": "2026-10-06", "weekday": 1, "seconds": 3600})
        self.assertEqual([b["sessions"] for b in out["lengths"]], [0, 1, 0, 1, 1, 0])

    def test_since_limits_totals_but_not_the_calendar(self):
        sessions = [
            session(datetime(2026, 10, 6, 20, 0, tzinfo=UTC), 60, appid=1, name="A"),
            session(datetime(2026, 9, 1, 12, 0, tzinfo=UTC), 180, appid=2, name="B"),
        ]
        out = stats.summarize(sessions, self.now.timestamp(), UTC, since=(self.now - timedelta(days=7)).timestamp())
        self.assertEqual((out["totals"]["seconds"], [g["name"] for g in out["games"]]), (3600, ["A"]))
        self.assertEqual(sum(d["seconds"] for d in out["calendar"]), 240 * 60)

    def test_empty(self):
        out = stats.summarize([], self.now.timestamp(), UTC)
        self.assertEqual((out["today"], out["totals"]["sessions"], out["games"], out["longest"]), (0, 0, [], None))


class ShareTest(unittest.TestCase):
    def test_serves_only_the_secret_url_and_stops(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "deckcheck-sessions.json")
            with open(path, "w") as f:
                f.write('{"ok": true}')
            share = Share()
            url = share.start(path, "deckcheck-sessions.json", host="127.0.0.1")
            port = url.split(":")[2].split("/")[0]
            secret_path = url.split(port, 1)[1]
            base = "http://127.0.0.1:" + port
            with urllib.request.urlopen(base + secret_path) as res:
                self.assertEqual(res.read(), b'{"ok": true}')
                self.assertIn("attachment", res.headers["Content-Disposition"])
            for wrong in ("/", "/deckcheck-sessions.json", secret_path + "x", "/../" + path):
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(base + wrong)
                self.assertEqual(ctx.exception.code, 404)
            share.stop()
            self.assertIsNone(share.url)
            with self.assertRaises(urllib.error.URLError):
                urllib.request.urlopen(base + secret_path, timeout=2)


if __name__ == "__main__":
    unittest.main()
