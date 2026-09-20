"""
Walks every page and the two flows that matter (book a job, schedule a job).

    python smoke_test.py

Runs against a throwaway database, so it never touches your real data.
"""

import os
import tempfile

os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["ADMIN_PASSWORD"] = "testpw"
os.environ["SECRET_KEY"] = "test"

import app as app_module  # noqa: E402
import seed as seed_module  # noqa: E402
from db import query  # noqa: E402

app = app_module.app
app.config["TESTING"] = True

failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)
    print(("  ok   " if condition else "  FAIL ") + label)


with app.app_context():
    seed_module.seed()

client = app.test_client()

print("\npublic pages")
for path in ["/", "/services", "/faq", "/book", "/track"]:
    check(f"GET {path}", client.get(path).status_code == 200)

import config as _config  # noqa: E402

_home = client.get("/").data
_shots = sum(len(job["shots"]) for job in _config.WORK)
check("home shows every before/after pair", _home.count(b'class="pair"') == _shots)
check("each pair is labelled", _home.count(b'class="shot-tag"') == _shots)
check("no leftover placeholder art", b"photos/services" not in _home and b"photos/jobs/deck-post-before.svg" not in _home)
check("old gallery url still redirects", client.get("/gallery").status_code == 301)

print("\nimages resolve")
import re as _re
_html = client.get("/").data.decode()
_srcs = sorted(set(_re.findall(r'src="(/static/[^"]+)"', _html)))
check(f"home references every work photo ({len(_srcs)})", len(_srcs) == _shots * 2)
for _src in _srcs:
    check(f"GET {_src}", client.get(_src).status_code == 200)
check("stylesheet loads", client.get("/static/style.css").status_code == 200)
check("favicon loads", client.get("/static/favicon.svg").status_code == 200)

print("\ntime preview api")
check(
    "returns a duration",
    client.get("/api/duration?services=driveway&size=large").get_json()["duration_min"] > 0,
)
check(
    "a bigger property takes longer",
    client.get("/api/duration?services=driveway&size=large").get_json()["duration_min"]
    > client.get("/api/duration?services=driveway&size=small").get_json()["duration_min"],
)
check(
    "two services take longer than one",
    client.get("/api/duration?services=driveway&services=deck&size=medium").get_json()["duration_min"]
    > client.get("/api/duration?services=driveway&size=medium").get_json()["duration_min"],
)
check("no services means no time", client.get("/api/duration").get_json()["duration_min"] == 0)

print("\nbooking form")
bad = client.post("/book", data={"name": "", "email": "nope"})
check(
    "rejects a blank form",
    bad.status_code == 200
    and b"Fix the highlighted fields" in bad.data
    and b"look right" in bad.data,  # the email error, with its apostrophe escaped
)

good = client.post(
    "/book",
    data={
        "name": "Test Person",
        "email": "test@example.com",
        "phone": "5550001111",
        "address": "1 Test Road",
        "town": "West Chester",
        "property_type": "House",
        "services": ["driveway", "fence"],
        "size": "medium",
        "preferred_window": "morning",
        "details": "smoke test",
    },
    follow_redirects=True,
)
check("accepts a good form", good.status_code == 200 and b"Got it." in good.data)
check(
    "refuses a town we don't cover",
    b"Pick a town we cover"
    in client.post(
        "/book",
        data={"name": "Test", "email": "t@example.com", "phone": "5550001111",
              "address": "1 Test Road", "town": "Pittsburgh",
              "services": ["driveway"], "size": "medium"},
    ).data,
)

with app.app_context():
    new_request = query(
        "SELECT * FROM requests ORDER BY id DESC LIMIT 1", one=True
    )
check("saved the request", new_request["services"] == "driveway,fence")
check("set a duration", new_request["duration_min"] >= 60)

print("\npublic status lookup")
tracked = client.get(f"/track?code={new_request['code']}")
check("finds a real code", b"Test Person" in tracked.data)
check("handles a bad code", b"Nothing matches" in client.get("/track?code=CW-ZZZZZ").data)

print("\nadmin auth")
check("redirects when logged out", client.get("/admin/").status_code == 302)
check("rejects a wrong password", b"Wrong password" in client.post("/admin/login", data={"password": "nope"}).data)
check(
    "accepts the right password",
    client.post("/admin/login", data={"password": "testpw"}).status_code == 302,
)

print("\nadmin pages")
for path in [
    "/admin/",
    "/admin/requests",
    "/admin/requests?status=new",
    "/admin/requests?status=accepted",
    "/admin/requests?q=Test",
    "/admin/schedule",
    "/admin/crew",
    "/admin/customers",
    "/admin/export/requests.csv",
]:
    check(f"GET {path}", client.get(path).status_code == 200)

with app.app_context():
    crew_id = query("SELECT id FROM crew LIMIT 1", one=True)["id"]
check("GET /admin/crew/<id>", client.get(f"/admin/crew/{crew_id}").status_code == 200)

print("\naccepting a request")
detail = client.get(f"/admin/requests/{new_request['id']}")
check("request detail loads", detail.status_code == 200)
check("new requests offer an accept button", b"Accept this request" in detail.data)
check(
    "accepting works",
    b"now find them a slot"
    in client.post(
        f"/admin/requests/{new_request['id']}/accept", follow_redirects=True
    ).data,
)
check(
    "accepting twice is refused",
    b"already been dealt with"
    in client.post(
        f"/admin/requests/{new_request['id']}/accept", follow_redirects=True
    ).data,
)

print("\nmatching and scheduling")

from datetime import date, timedelta  # noqa: E402

# Find a day the matcher likes, then book the person it suggested.
booked = False
for offset in range(1, 21):
    day = (date.today() + timedelta(days=offset)).isoformat()
    with app.app_context():
        from scheduling import find_matches

        matches = find_matches(day, None, new_request["duration_min"], ["driveway", "fence"])
    if not matches:
        continue
    best = matches[0]
    res = client.post(
        f"/admin/requests/{new_request['id']}/schedule",
        data={"crew_id": best["crew"]["id"], "day": day, "start_min": best["start_min"]},
        follow_redirects=True,
    )
    check("booking succeeded", b"Booked with" in res.data)
    booked = True

    # Same slot a second time has to be refused.
    clash = client.post(
        f"/admin/requests/{new_request['id']}/schedule",
        data={"crew_id": best["crew"]["id"], "day": day, "start_min": best["start_min"]},
        follow_redirects=True,
    )
    check("double booking is blocked", b"overlaps job" in clash.data)
    break

check("found a bookable day within 3 weeks", booked)

with app.app_context():
    after = query("SELECT status FROM requests WHERE id = ?", (new_request["id"],), one=True)
check("status flipped to scheduled", after["status"] == "scheduled")

print("\nnotes and status")
client.post(f"/admin/requests/{new_request['id']}/note", data={"body": "Smoke test note"})
check("note shows on the page", b"Smoke test note" in client.get(f"/admin/requests/{new_request['id']}").data)

with app.app_context():
    appointment = query(
        "SELECT id FROM appointments WHERE request_id = ? ORDER BY id DESC",
        (new_request["id"],),
        one=True,
    )
client.post(f"/admin/appointments/{appointment['id']}/complete", follow_redirects=True)
with app.app_context():
    done = query("SELECT status FROM requests WHERE id = ?", (new_request["id"],), one=True)
check("completing the visit completes the request", done["status"] == "completed")

print("\ncrew editing")
check(
    "adds weekly hours",
    client.post(
        f"/admin/crew/{crew_id}/availability",
        data={"weekday": ["1", "3"], "start": "07:00", "end": "08:30"},
        follow_redirects=True,
    ).status_code
    == 200,
)
check(
    "rejects a backwards time range",
    b"end time after the start"
    in client.post(
        f"/admin/crew/{crew_id}/availability",
        data={"weekday": ["1"], "start": "18:00", "end": "09:00"},
        follow_redirects=True,
    ).data,
)
check(
    "records a day off",
    client.post(
        f"/admin/crew/{crew_id}/timeoff",
        data={"day": (date.today() + timedelta(days=3)).isoformat(), "reason": "Away"},
        follow_redirects=True,
    ).status_code
    == 200,
)

print("\nlogout")
client.get("/admin/logout")
check("session is gone", client.get("/admin/").status_code == 302)

print(f"\n{checks - len(failures)}/{checks} passed")
if failures:
    print("failed: " + ", ".join(failures))
    raise SystemExit(1)
