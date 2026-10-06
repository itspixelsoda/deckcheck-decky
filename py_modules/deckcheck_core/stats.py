"""Turns a list of sessions into the numbers the UI shows. Pure functions, no I/O."""

from collections import defaultdict
from datetime import datetime, timedelta

LENGTH_BUCKETS = [("< 15 min", 15 * 60), ("15-30 min", 30 * 60), ("30-60 min", 3600), ("1-2 h", 2 * 3600), ("2-4 h", 4 * 3600), ("4 h +", None)]


def hourly_buckets(sessions, tz=None):
    """Spreads each session's active time over the local hours it spanned.

    Returns {(iso_date, hour): seconds}. Active time is spread evenly across the session's wall-clock
    span; where exactly a mid-session sleep happened is not recorded, so this is an approximation
    for sessions that include one.
    """
    buckets = defaultdict(float)
    for s in sessions:
        start, end, active = s["start"], s["end"], s["activeSeconds"]
        if active <= 0:
            continue
        if end <= start:
            local = datetime.fromtimestamp(start, tz) if tz else datetime.fromtimestamp(start)
            buckets[(local.date().isoformat(), local.hour)] += active
            continue
        ratio = active / (end - start)
        t = float(start)
        while t < end:
            local = datetime.fromtimestamp(t, tz) if tz else datetime.fromtimestamp(t)
            boundary = (local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)).timestamp()
            # A clock change can make the next local hour start at or before `t`; always move forward.
            nxt = min(end, boundary if boundary > t else t + 3600)
            buckets[(local.date().isoformat(), local.hour)] += (nxt - t) * ratio
            t = nxt
    return buckets


def summarize(sessions, now, tz=None, since=None, calendar_days=182):
    """Everything one screen needs. `since` (unix seconds) limits totals, games and patterns; the calendar always shows `calendar_days`."""
    today = (datetime.fromtimestamp(now, tz) if tz else datetime.fromtimestamp(now)).date()
    buckets = hourly_buckets(sessions, tz)

    per_day = defaultdict(float)
    for (date, _hour), seconds in buckets.items():
        per_day[date] += seconds

    calendar = []
    for offset in range(calendar_days - 1, -1, -1):
        day = today - timedelta(days=offset)
        calendar.append({"date": day.isoformat(), "weekday": day.weekday(), "seconds": int(round(per_day.get(day.isoformat(), 0)))})

    week_start = (today - timedelta(days=6)).isoformat()
    today_seconds = per_day.get(today.isoformat(), 0)
    week_seconds = sum(v for d, v in per_day.items() if week_start <= d <= today.isoformat())

    selected = [s for s in sessions if since is None or s["end"] >= since]
    selected_buckets = hourly_buckets(selected, tz) if since is not None else buckets
    since_date = None if since is None else (datetime.fromtimestamp(since, tz) if tz else datetime.fromtimestamp(since)).date().isoformat()

    hours = [0.0] * 24
    weekdays = [0.0] * 7
    grid = [[0.0] * 24 for _ in range(7)]
    days_played = set()
    for (date, hour), seconds in selected_buckets.items():
        if since_date is not None and date < since_date:
            continue
        weekday = datetime.strptime(date, "%Y-%m-%d").weekday()
        hours[hour] += seconds
        weekdays[weekday] += seconds
        grid[weekday][hour] += seconds
        if seconds >= 60:
            days_played.add(date)

    games = {}
    for s in selected:
        g = games.setdefault((s["appid"], s["nonSteam"]), {"appid": s["appid"], "name": s["name"], "nonSteam": s["nonSteam"], "seconds": 0, "sessions": 0, "first": s["start"], "last": s["end"]})
        g["seconds"] += s["activeSeconds"]
        g["sessions"] += 1
        g["first"] = min(g["first"], s["start"])
        if s["end"] >= g["last"]:
            g["last"] = s["end"]
            g["name"] = s["name"]  # games get renamed; show the latest name

    lengths = [{"label": label, "sessions": 0} for label, _ in LENGTH_BUCKETS]
    for s in selected:
        for i, (_label, limit) in enumerate(LENGTH_BUCKETS):
            if limit is None or s["activeSeconds"] < limit:
                lengths[i]["sessions"] += 1
                break

    total = sum(s["activeSeconds"] for s in selected)
    longest = max(selected, key=lambda s: s["activeSeconds"], default=None)
    return {
        "today": int(round(today_seconds)),
        "week": int(round(week_seconds)),
        "totals": {
            "seconds": total,
            "sessions": len(selected),
            "games": len(games),
            "daysPlayed": len(days_played),
            "averageSession": int(total / len(selected)) if selected else 0,
            "first": min((s["start"] for s in sessions), default=None),
        },
        "longest": longest,
        "calendar": calendar,
        "hours": [int(round(v)) for v in hours],
        "weekdays": [int(round(v)) for v in weekdays],
        "grid": [[int(round(v)) for v in row] for row in grid],
        "games": sorted(games.values(), key=lambda g: g["seconds"], reverse=True),
        "lengths": lengths,
    }
