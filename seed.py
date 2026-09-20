"""
Fill the database with a plausible week so the ops side isn't empty.

    python seed.py          # add sample data (keeps what's already there)
    python seed.py --reset  # wipe everything first

Safe to skip entirely in production.
"""

import random
import sys
from datetime import date, datetime, timedelta

from app import app
from db import execute, query
from scheduling import job_duration

CREW = [
    # name, phone, max jobs/day, weekday hours, weekend hours, skills
    ("Marco Ruiz", "610-555-0142", 2, (16 * 60, 20 * 60), (8 * 60, 18 * 60), []),
    ("Priya Nair", "484-555-0188", 2, (15 * 60, 19 * 60), (9 * 60, 17 * 60), []),
    ("Jalen Brooks", "610-555-0119", 3, (16 * 60, 20 * 60), (8 * 60, 19 * 60), ["driveway", "fence", "deck", "gutter"]),
    ("Sofia Almeida", "484-555-0163", 1, None, (10 * 60, 16 * 60), ["driveway", "deck", "gutter"]),
    ("Theo Lang", "610-555-0175", 2, (17 * 60, 20 * 60), (8 * 60, 15 * 60), []),
]

# Fake people in real towns, so the ops screens look like a normal week.
# Towns must match BUSINESS["service_area"] in config.py.
CUSTOMERS = [
    ("Dana Reyes", "dana.reyes@example.com", "610-555-0201", "14 Alder Court", "West Chester"),
    ("Marcus Tran", "m.tran@example.com", "610-555-0233", "907 Birch Lane", "Exton"),
    ("Helen Okafor", "helen.ok@example.com", "484-555-0244", "3 Sycamore Way", "Downingtown"),
    ("Greg Sandoval", "gsandoval@example.com", "610-555-0255", "58 Poplar Street", "Malvern"),
    ("Aisha Bello", "aisha.b@example.com", "484-555-0266", "221 Cedar Ridge Rd", "Paoli"),
    ("Tom Whitaker", "twhitaker@example.com", "610-555-0277", "76 Chestnut Ave", "Thorndale"),
    ("Nina Patel", "nina.patel@example.com", "484-555-0288", "1040 Walnut Circle", "West Chester"),
    ("Rob Kinsella", "rkinsella@example.com", "610-555-0299", "12 Juniper Place", "Exton"),
]

DETAILS = [
    "Big oil stain near the garage. Gate code is 4412.",
    "Friendly dog in the back yard, he'll want to help.",
    "The north side gets no sun and it shows.",
    "",
    "Please don't spray the hydrangeas by the porch.",
    "Second time you all have come out, same as last spring.",
]

NOTES = [
    "Left a voicemail.",
    "Texted to confirm we can take it, waiting to hear back on a day.",
    "Wants it done before their in-laws visit.",
]

CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def now():
    return datetime.now().isoformat(timespec="seconds")


def make_code(taken):
    while True:
        code = "CW-" + "".join(random.choice(CODE_CHARS) for _ in range(5))
        if code not in taken:
            taken.add(code)
            return code


def reset():
    for table in ("activity", "appointments", "requests", "crew_time_off",
                  "crew_availability", "crew", "customers"):
        execute(f"DELETE FROM {table}")
    print("Cleared every table.")


def seed():
    random.seed(7)  # same fake data every time, easier to demo

    crew_ids = []
    for name, phone, max_jobs, weekday_hours, weekend_hours, skills in CREW:
        crew_id = execute(
            """INSERT INTO crew (name, phone, email, skills, max_jobs_day, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                name,
                phone,
                name.split()[0].lower() + "@example.com",
                ",".join(skills),
                max_jobs,
                now(),
            ),
        )
        crew_ids.append(crew_id)

        if weekday_hours:
            for weekday in range(5):
                execute(
                    """INSERT INTO crew_availability (crew_id, weekday, start_min, end_min)
                       VALUES (?, ?, ?, ?)""",
                    (crew_id, weekday, *weekday_hours),
                )
        if weekend_hours:
            for weekday in (5, 6):
                execute(
                    """INSERT INTO crew_availability (crew_id, weekday, start_min, end_min)
                       VALUES (?, ?, ?, ?)""",
                    (crew_id, weekday, *weekend_hours),
                )

    # One person is away next weekend, so the matcher has something to skip.
    saturday = date.today() + timedelta(days=(5 - date.today().weekday()) % 7 + 7)
    execute(
        "INSERT INTO crew_time_off (crew_id, day, reason) VALUES (?, ?, ?)",
        (crew_ids[0], saturday.isoformat(), "Family trip"),
    )

    customer_ids = []
    for name, email, phone, address, town in CUSTOMERS:
        customer_ids.append(
            execute(
                """INSERT INTO customers (name, email, phone, address, town, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, email, phone, address, town, now()),
            )
        )

    service_keys = ["driveway", "siding", "deck", "fence", "roof", "gutter"]
    sizes = ["small", "medium", "large"]
    # A realistic mix: a couple untouched, some accepted, most booked or done.
    plan = ["new", "new", "accepted", "accepted", "scheduled", "scheduled",
            "completed", "completed"]
    codes = set()

    for index, customer_id in enumerate(customer_ids):
        status = plan[index]
        picked = random.sample(service_keys, random.choice([1, 1, 2]))
        size = random.choice(sizes)
        duration = job_duration(picked, size)

        if status == "completed":
            day = date.today() - timedelta(days=random.randint(3, 20))
        else:
            day = date.today() + timedelta(days=random.randint(1, 12))

        request_id = execute(
            """INSERT INTO requests
                 (code, customer_id, services, size, property_type, details,
                  preferred_day, preferred_window, status, duration_min,
                  source, created_at)
               VALUES (?, ?, ?, ?, 'House', ?, ?, ?, ?, ?, 'website', ?)""",
            (
                make_code(codes),
                customer_id,
                ",".join(picked),
                size,
                random.choice(DETAILS),
                day.isoformat(),
                random.choice(["any", "morning", "afternoon", "evening"]),
                status,
                duration,
                (datetime.now() - timedelta(days=random.randint(0, 9))).isoformat(timespec="seconds"),
            ),
        )
        execute(
            "INSERT INTO activity (request_id, body, kind, created_at) VALUES (?, ?, 'system', ?)",
            (request_id, "Request came in from the website.", now()),
        )
        if status in ("accepted", "scheduled", "completed"):
            execute(
                "INSERT INTO activity (request_id, body, kind, created_at) VALUES (?, ?, 'note', ?)",
                (request_id, random.choice(NOTES), now()),
            )

        if status in ("scheduled", "completed"):
            crew_id = crew_ids[index % len(crew_ids)]
            start = random.choice([9 * 60, 10 * 60, 13 * 60, 16 * 60])
            execute(
                """INSERT INTO appointments
                     (request_id, crew_id, day, start_min, end_min, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    request_id,
                    crew_id,
                    day.isoformat(),
                    start,
                    start + duration,
                    "completed" if status == "completed" else "scheduled",
                    now(),
                ),
            )

    print(f"Added {len(CREW)} crew, {len(CUSTOMERS)} customers and {len(CUSTOMERS)} requests.")
    print("Log in at /admin with the password from ADMIN_PASSWORD (default: letmein).")


if __name__ == "__main__":
    with app.app_context():
        if "--reset" in sys.argv:
            reset()
        elif query("SELECT 1 FROM crew LIMIT 1", one=True):
            print("There's already data here. Use --reset to start over.")
            sys.exit(0)
        seed()
