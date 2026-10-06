"""Runs main.py's Plugin against a stand-in for the `decky` module, the way the loader would call it."""

import asyncio
import json
import logging
import os
import sys
import tempfile
import types
import unittest
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        fake = types.ModuleType("decky")
        fake.DECKY_PLUGIN_RUNTIME_DIR = os.path.join(self.dir.name, "data")
        fake.DECKY_USER_HOME = os.path.join(self.dir.name, "home")
        fake.logger = logging.getLogger("deckcheck-test")
        sys.modules["decky"] = fake
        sys.path.insert(0, ROOT)
        sys.modules.pop("main", None)
        import main

        self.main = main

    def tearDown(self):
        sys.modules.pop("decky", None)
        sys.path.remove(ROOT)
        self.dir.cleanup()

    def test_full_cycle(self):
        async def run():
            plugin = self.main.Plugin()
            # The frontend can call before _main has finished.
            await plugin.reconcile([{"appid": 730, "name": "Counter-Strike 2", "non_steam": False, "steamid": "76561197960287930"}])
            await plugin._main()
            live = await plugin.get_live()
            self.assertEqual([s["name"] for s in live["playing"]], ["Counter-Strike 2"])

            # Pretend 20 minutes of play by moving the session's start and booked time back.
            plugin.tracker.db.execute("UPDATE sessions SET start = start - 1200, active = 1200")
            plugin.tracker.db.commit()
            await plugin.game_stopped(730)
            await plugin.game_started(999, "Too Short", True, None)
            await plugin.game_stopped(999)

            summary = await plugin.get_summary("7d", None)
            self.assertEqual((summary["totals"]["sessions"], summary["totals"]["seconds"] >= 1200), (1, True))
            json.dumps(summary)  # everything returned to the frontend must be JSON-serialisable
            self.assertEqual((await plugin.get_summary("all", 12345))["totals"]["sessions"], 0)
            listed = await plugin.get_sessions(10, 0, None)
            self.assertEqual(listed["total"], 1)

            exported = await plugin.export_sessions()
            self.assertTrue(exported["path"].endswith(os.path.join("home", "deckcheck", "deckcheck-sessions.json")))
            with open(exported["path"], encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual((doc["format"], doc["version"], len(doc["sessions"])), ("deckcheck-sessions", 1, 1))
            self.assertEqual(doc["sessions"][0]["steamid"], "76561197960287930")

            shared = await plugin.start_share()
            port = shared["url"].split(":")[2].split("/")[0]
            local = "http://127.0.0.1:" + port + shared["url"].split(port, 1)[1]
            body = await asyncio.get_event_loop().run_in_executor(None, lambda: urllib.request.urlopen(local, timeout=5).read())
            self.assertEqual(json.loads(body), doc)
            await plugin.stop_share()

            await plugin.delete_session(listed["sessions"][0]["id"])
            self.assertEqual((await plugin.get_sessions(10, 0, None))["total"], 0)
            await plugin._unload()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
