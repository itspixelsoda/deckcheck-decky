"""Writes the session export file. The format is described in the README and is the plugin's only public interface."""

import json
import os

FORMAT = "deckcheck-sessions"
VERSION = 1
FILE_NAME = "deckcheck-sessions.json"


def build(tracker, now, device_name):
    sessions = [
        {key: s[key] for key in ("id", "steamid", "appid", "name", "nonSteam", "start", "end", "activeSeconds", "suspendedSeconds")}
        for s in tracker.sessions(include_open=False)
    ]
    return {
        "format": FORMAT,
        "version": VERSION,
        "exportedAt": int(now),
        "device": {"id": tracker.device_id(), "name": device_name},
        "sessions": sessions,
    }


def write(document, directory):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, FILE_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(document, f, ensure_ascii=False)
    os.replace(tmp, path)
    return path
