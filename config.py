"""
Everything about the group lives here.

If you're handing this project to someone else, this is the only file they
need to touch to make it say the right name, the right towns and the right
contact details.

This is a volunteer operation, so there are no prices anywhere in this
codebase on purpose. What the app tracks instead of money is *time*: how long
a job takes, and who has the hours free to do it.
"""

import os

# ---------------------------------------------------------------- the group --

BUSINESS = {
    "name": "Chester County Community Washing",
    # Shown in page titles and the footer, so search engines and neighbors
    # both know where this is.
    "region": "Chester County, PA",
    "tagline": "A volunteer crew from around here.",
    "blurb": (
        "We're a group of local students who pressure wash driveways, siding, "
        "decks and fences for our neighbors. You tell us what needs cleaning, "
        "we match you with whoever on the team is free, and someone comes out. "
        "There's nothing to pay — we volunteer our time."
    ),
    # One line on why the group exists. Shown on the home page.
    "mission": (
        "We started this because half the people on our street couldn't get up "
        "a ladder or haul a machine around. We already had the gear and the "
        "weekends, so it seemed silly not to."
    ),
    "phone": "(484) 340-2332",
    # Same number, digits only — what a tel: link needs to dial correctly.
    "phone_link": "+14843402332",
    "email": "chestercountypowerwashing@gmail.com",
    "founded": 2023,
    # Towns / neighborhoods you actually drive to. Shown on the site and used
    # to validate the request form.
    # Guessed at a cluster around West Chester — edit this to the places you
    # actually drive to. The request form only accepts towns on this list.
    "service_area": [
        "West Chester",
        "Exton",
        "Downingtown",
        "Malvern",
        "Paoli",
        "Thorndale",
    ],
    # Shown on the contact page so people know when a human will reply.
    "hours": "Weekdays after 3:30pm, weekends 8am-6pm",
}

# ---------------------------------------------------------------- services --
#
# minutes : how long the job usually takes, by size. This is the number the
#           scheduler uses to block off time on someone's calendar, so it's
#           worth keeping honest as you learn what jobs really take.

SERVICES = {
    "driveway": {
        "icon": "driveway",
        "name": "Driveway & Sidewalk",
        "summary": "Surface cleaner pass on concrete, plus edging and rinse.",
        "minutes": {"small": 75, "medium": 120, "large": 180},
    },
    "siding": {
        "icon": "house",
        "name": "House Siding (Soft Wash)",
        "summary": "Low pressure detergent wash for vinyl, stucco and brick.",
        "minutes": {"small": 120, "medium": 180, "large": 270},
    },
    "deck": {
        "icon": "deck",
        "name": "Deck & Patio",
        "summary": "Wood-safe pressure and a brightener rinse.",
        "minutes": {"small": 90, "medium": 135, "large": 195},
    },
    "fence": {
        "icon": "fence",
        "name": "Fence",
        "summary": "Both sides, gates included, green stuff gone.",
        "minutes": {"small": 75, "medium": 120, "large": 180},
    },
    "roof": {
        "icon": "roof",
        "name": "Roof Soft Wash",
        "summary": "Black streak removal. Single story only, no walking the roof.",
        "minutes": {"small": 150, "medium": 210, "large": 300},
    },
    "gutter": {
        "icon": "gutter",
        "name": "Gutter Brightening",
        "summary": "Scrub off the tiger stripes on the outside of the gutters.",
        "minutes": {"small": 60, "medium": 90, "large": 130},
    },
}

# ------------------------------------------------------------------- work --
#
# Jobs we've photographed. One entry per job, with as many before/after
# "shots" as you managed to take of it.
#
# Right now that's a single deck, which is why the site talks about one job
# rather than pretending to a portfolio. Add another entry here and the home
# page picks it up automatically — see static/photos/README.md for how to
# prepare the images.

WORK = [
    {
        "title": "A townhouse deck in Chester County",
        "service": "deck",
        "town": "",  # fill in once you remember which one this was
        "summary": (
            "Composite boards and a white vinyl rail, four years without a wash. "
            "The green had got into every corner of the post bases. Two of us, "
            "one Saturday morning."
        ),
        "shots": [
            {
                "label": "The post base",
                "note": "Algae builds up where the post meets the deck and stays wet.",
                "before": "photos/jobs/deck-post-before.jpg",
                "after": "photos/jobs/deck-post-after.jpg",
            },
            {
                "label": "The top rail",
                "note": "Streaking along the top of the rail, right where you put your hands.",
                "before": "photos/jobs/deck-rail-before.jpg",
                "after": "photos/jobs/deck-rail-after.jpg",
            },
        ],
    },
]

SIZES = {
    "small": {"name": "Small", "hint": "Townhouse, 1-2 car driveway, small deck"},
    "medium": {"name": "Medium", "hint": "Average single family home"},
    "large": {"name": "Large", "hint": "Big lot, long driveway, two stories"},
}

PROPERTY_TYPES = ["House", "Townhouse", "Apartment / Condo", "Community space", "Other"]

# ------------------------------------------------------------- scheduling --
#
# Windows people can ask for, in minutes past midnight.

WINDOWS = {
    "morning": {"name": "Morning", "label": "8:00am - 12:00pm", "start": 8 * 60, "end": 12 * 60},
    "afternoon": {"name": "Afternoon", "label": "12:00pm - 4:00pm", "start": 12 * 60, "end": 16 * 60},
    "evening": {"name": "Evening", "label": "4:00pm - 7:00pm", "start": 16 * 60, "end": 19 * 60},
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Gap left between two jobs for the same person, so they can pack up and drive.
TRAVEL_BUFFER_MIN = 45

# ---------------------------------------------------------------- pipeline --
#
# new       - just arrived, nobody has looked at it yet
# accepted  - we've said yes; it still needs a day and a person
# scheduled - somebody is booked to go
# completed - done
# cancelled - not happening, for whatever reason

REQUEST_STATUSES = ["new", "accepted", "scheduled", "completed", "cancelled"]

STATUS_LABELS = {
    "new": "New request",
    "accepted": "Accepted",
    "scheduled": "Scheduled",
    "completed": "Completed",
    "cancelled": "Cancelled",
}

# ------------------------------------------------------------------- app ----

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "letmein")
DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/app.db")
