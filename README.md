# deckcheck

A [Decky Loader](https://decky.xyz) plugin that records play sessions on a Steam Deck, shows statistics on the
device and exports everything as one documented JSON file.

It needs no account and no internet connection. All data stays in a local SQLite database.

## What it does

- **Tracks sessions**: when each game started and stopped, how long it actually ran, and how long the device
  slept in between. Sleep is never counted as play time.
- **Quick access panel**: what is running now, today, the last 7 days.
- **Statistics page**: totals, most played games, a calendar of the last 26 weeks, time of day, day of week,
  session lengths, a page per game, and the full session list (sessions can be deleted).
- **Export**: writes `~/deckcheck/deckcheck-sessions.json`, and can offer the same file for download on the
  local network for 10 minutes. The format is described [below](#export-format).

Limits: it only sees games played on the device it is installed on, from the day it is installed. Launches
shorter than 10 seconds are ignored.

## Install

1. In Decky's settings, turn on **Developer mode**.
2. Build the plugin (below) or take `deckcheck.zip` from a release, and copy it to the Deck.
3. Decky settings → Developer → **Install plugin from ZIP file**.

## Build

Needs Node.js, pnpm and Python 3.

```sh
pnpm install
pnpm run package     # builds the frontend and writes out/deckcheck.zip
pnpm test            # backend tests (Python standard library only)
pnpm run typecheck
```

## How time is measured

Play time comes from a monotonic clock, which on Linux stands still while the device is suspended. The
difference between that clock and wall-clock time is recorded as time asleep. This means a missed suspend
or resume notification cannot inflate a session.

An open session is saved every minute. If the device loses power, the session ends at the last save rather
than being lost or left running.

## Layout

- `main.py`: the methods Decky exposes to the frontend.
- `py_modules/deckcheck_core/`: tracking (`tracker.py`), statistics (`stats.py`), export (`export.py`) and the
  temporary download server (`share.py`).
- `src/`: the React frontend. `tracking.ts` listens to Steam; `StatsPage.tsx` is the statistics page.
- `tests/`: backend tests.

## Export format

One JSON file, `~/deckcheck/deckcheck-sessions.json`. Every export holds the complete history of finished
sessions, so a reader that has seen an earlier export should skip sessions whose `id` it already knows.

```json
{
  "format": "deckcheck-sessions",
  "version": 1,
  "exportedAt": 1791234567,
  "device": { "id": "b0a1c7de-…", "name": "steamdeck" },
  "sessions": [
    {
      "id": "6f1c2a90-…",
      "steamid": "76561197960287930",
      "appid": 730,
      "name": "Counter-Strike 2",
      "nonSteam": false,
      "start": 1791200000,
      "end": 1791207200,
      "activeSeconds": 6900,
      "suspendedSeconds": 300
    }
  ]
}
```

- Times are Unix seconds (UTC). `activeSeconds` is the play time; `suspendedSeconds` is time asleep during the session.
- `steamid` is the account logged in when the session started, or `null` if it could not be read.
- For non-Steam shortcuts (`nonSteam: true`) the `appid` is local to the device.
- A game still running at export time is left out and appears in the next export.
- `version` rises only when an existing field changes meaning. New fields may appear without a bump; ignore fields you do not know.
