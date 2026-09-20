"""
Job length, and the bit that matches a job to whoever is free.

None of this touches the database directly except through db.query, so it is
easy to reason about on its own.
"""

from datetime import date, datetime, timedelta

import config
from db import query

# ------------------------------------------------------------ time helpers --


def fmt_time(minutes):
    """540 -> '9:00am'."""
    if minutes is None:
        return ""
    hour, minute = divmod(int(minutes), 60)
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d}{suffix}"


def fmt_range(start, end):
    return f"{fmt_time(start)} - {fmt_time(end)}"


def parse_day(value):
    """'2026-04-18' -> date, or None if it isn't a real date."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def fmt_day(value):
    """'2026-04-18' -> 'Sat, Apr 18'."""
    day = parse_day(value)
    return day.strftime("%a, %b %-d") if day else value


def week_bounds(day):
    """Monday and Sunday of the week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


# ------------------------------------------------------------ job length --


def job_duration(service_keys, size):
    """
    Minutes to block off. Extra services are faster once the gear is already
    set up, so they count for 70%. Rounded up to the next half hour.
    """
    size = size if size in config.SIZES else "medium"
    total = 0.0
    for index, key in enumerate(service_keys):
        service = config.SERVICES.get(key)
        if not service:
            continue
        total += service["minutes"].get(size, 120) * (0.7 if index else 1.0)

    total = max(total, 60)
    return int(-(-total // 30) * 30)


# ---------------------------------------------------------------- matching --


def _busy_intervals(crew_id, day_str, ignore_appointment_id=None):
    """Booked time for one person on one day, padded with travel time."""
    rows = query(
        """SELECT id, start_min, end_min FROM appointments
           WHERE crew_id = ? AND day = ? AND status != 'cancelled'""",
        (crew_id, day_str),
    )
    intervals = []
    for row in rows:
        if ignore_appointment_id and row["id"] == ignore_appointment_id:
            continue
        intervals.append(
            (
                row["start_min"] - config.TRAVEL_BUFFER_MIN,
                row["end_min"] + config.TRAVEL_BUFFER_MIN,
            )
        )
    return sorted(intervals)


def _first_free_slot(window_start, window_end, duration, busy):
    """
    Earliest start time inside [window_start, window_end] where `duration`
    minutes fit without hitting anything in `busy`. None if it doesn't fit.
    """
    cursor = window_start
    for busy_start, busy_end in busy:
        if busy_end <= cursor:
            continue
        if busy_start >= cursor + duration:
            break  # gap in front of this job is big enough
        cursor = max(cursor, busy_end)
    return cursor if cursor + duration <= window_end else None


def _has_skills(crew_row, service_keys):
    skills = [s for s in crew_row["skills"].split(",") if s]
    if not skills:
        return True  # nothing listed means they'll do anything
    return all(key in skills for key in service_keys)


def find_matches(day_str, window_key, duration, service_keys, ignore_appointment_id=None):
    """
    Who can take this job, soonest first, least busy first.

    Returns a list of dicts: crew row, the slot we'd give them, and how loaded
    their week already is. The admin picks one; nothing is booked here.
    """
    day = parse_day(day_str)
    if not day:
        return []

    weekday = day.weekday()
    window = config.WINDOWS.get(window_key)
    day_start, day_end = (window["start"], window["end"]) if window else (6 * 60, 21 * 60)

    monday, sunday = week_bounds(day)
    matches = []

    for member in query("SELECT * FROM crew WHERE active = 1 ORDER BY name"):
        if not _has_skills(member, service_keys):
            continue

        off = query(
            "SELECT 1 FROM crew_time_off WHERE crew_id = ? AND day = ?",
            (member["id"], day_str),
            one=True,
        )
        if off:
            continue

        jobs_today = query(
            """SELECT COUNT(*) AS n FROM appointments
               WHERE crew_id = ? AND day = ? AND status != 'cancelled' AND id IS NOT ?""",
            (member["id"], day_str, ignore_appointment_id),
            one=True,
        )["n"]
        if jobs_today >= member["max_jobs_day"]:
            continue

        busy = _busy_intervals(member["id"], day_str, ignore_appointment_id)
        blocks = query(
            """SELECT start_min, end_min FROM crew_availability
               WHERE crew_id = ? AND weekday = ? ORDER BY start_min""",
            (member["id"], weekday),
        )

        best_start = None
        for block in blocks:
            start = max(block["start_min"], day_start)
            end = min(block["end_min"], day_end)
            if end - start < duration:
                continue
            slot = _first_free_slot(start, end, duration, busy)
            if slot is not None and (best_start is None or slot < best_start):
                best_start = slot

        if best_start is None:
            continue

        jobs_week = query(
            """SELECT COUNT(*) AS n FROM appointments
               WHERE crew_id = ? AND day BETWEEN ? AND ? AND status != 'cancelled'""",
            (member["id"], monday.isoformat(), sunday.isoformat()),
            one=True,
        )["n"]

        matches.append(
            {
                "crew": member,
                "start_min": best_start,
                "end_min": best_start + duration,
                "jobs_today": jobs_today,
                "jobs_week": jobs_week,
            }
        )

    # Spread the work around: whoever has the lightest week goes first.
    matches.sort(key=lambda m: (m["jobs_week"], m["start_min"], m["crew"]["name"]))
    return matches


def next_open_days(window_key, duration, service_keys, days_ahead=21, limit=5):
    """
    Scan forward for days that have at least one match. Used when a customer
    didn't pick a date, or the date they wanted is full.
    """
    found = []
    today = date.today()
    for offset in range(1, days_ahead + 1):
        day_str = (today + timedelta(days=offset)).isoformat()
        matches = find_matches(day_str, window_key, duration, service_keys)
        if matches:
            found.append({"day": day_str, "matches": matches})
        if len(found) >= limit:
            break
    return found
