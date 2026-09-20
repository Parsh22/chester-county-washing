"""
The part only the organisers log into: incoming requests, scheduling, crew
and the people we've helped.

Auth is a single shared password in ADMIN_PASSWORD. That's enough for a small
volunteer group; if the team ever needs separate logins this is the file to
change.
"""

import csv
import io
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import config
from db import execute, query
from scheduling import find_matches, next_open_days, parse_day, week_bounds

admin_bp = Blueprint("admin", __name__)


def _now():
    return datetime.now().isoformat(timespec="seconds")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _log(request_id, body, kind="system"):
    execute(
        "INSERT INTO activity (request_id, body, kind, created_at) VALUES (?, ?, ?, ?)",
        (request_id, body, kind, _now()),
    )


# --------------------------------------------------------------------- auth --


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == config.ADMIN_PASSWORD:
            session["admin"] = True
            session.permanent = False
            target = request.args.get("next")
            # Only follow same-site paths, never a full URL someone pasted in.
            if target and target.startswith("/") and not target.startswith("//"):
                return redirect(target)
            return redirect(url_for("admin.dashboard"))
        error = "Wrong password."
    return render_template("admin/login.html", error=error)


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.home"))


# ---------------------------------------------------------------- dashboard --


@admin_bp.route("/")
@login_required
def dashboard():
    today = date.today()
    monday, sunday = week_bounds(today)

    counts = {
        status: query(
            "SELECT COUNT(*) AS n FROM requests WHERE status = ?", (status,), one=True
        )["n"]
        for status in config.REQUEST_STATUSES
    }

    todays_jobs = query(
        """SELECT a.*, r.code, r.services,
                  c.name AS customer_name, c.address, c.town, c.phone,
                  cr.name AS crew_name
           FROM appointments a
           JOIN requests r ON r.id = a.request_id
           JOIN customers c ON c.id = r.customer_id
           JOIN crew cr ON cr.id = a.crew_id
           WHERE a.day = ? AND a.status != 'cancelled'
           ORDER BY a.start_min""",
        (today.isoformat(),),
    )

    new_leads = query(
        """SELECT r.*, c.name AS customer_name, c.town
           FROM requests r JOIN customers c ON c.id = r.customer_id
           WHERE r.status = 'new' ORDER BY r.created_at DESC LIMIT 8"""
    )

    # Volunteer hours the team has committed to this week — the closest thing
    # we have to a "how busy are we" number now that nothing is priced.
    hours_this_week = query(
        """SELECT COALESCE(SUM(a.end_min - a.start_min), 0) AS total
           FROM appointments a
           WHERE a.day BETWEEN ? AND ? AND a.status != 'cancelled'""",
        (monday.isoformat(), sunday.isoformat()),
        one=True,
    )["total"]

    crew_load = query(
        """SELECT cr.id, cr.name,
                  (SELECT COUNT(*) FROM appointments a
                    WHERE a.crew_id = cr.id AND a.status != 'cancelled'
                      AND a.day BETWEEN ? AND ?) AS jobs
           FROM crew cr WHERE cr.active = 1 ORDER BY jobs DESC, cr.name""",
        (monday.isoformat(), sunday.isoformat()),
    )

    unscheduled = query(
        """SELECT r.*, c.name AS customer_name
           FROM requests r JOIN customers c ON c.id = r.customer_id
           WHERE r.status IN ('new', 'accepted')
             AND r.preferred_day != '' AND r.preferred_day < ?
           ORDER BY r.preferred_day""",
        (today.isoformat(),),
    )

    return render_template(
        "admin/dashboard.html",
        counts=counts,
        todays_jobs=todays_jobs,
        new_leads=new_leads,
        hours_this_week=int(hours_this_week),
        crew_load=crew_load,
        stale=unscheduled,
        today=today,
    )


# ----------------------------------------------------------------- requests --


@admin_bp.route("/requests")
@login_required
def requests_list():
    status = request.args.get("status", "open")
    search = (request.args.get("q") or "").strip()

    sql = """SELECT r.*, c.name AS customer_name, c.town, c.phone, c.email
             FROM requests r JOIN customers c ON c.id = r.customer_id
             WHERE 1 = 1"""
    args = []

    if status in config.REQUEST_STATUSES:
        sql += " AND r.status = ?"
        args.append(status)
    elif status == "open":
        sql += " AND r.status IN ('new', 'accepted', 'scheduled')"

    if search:
        sql += " AND (c.name LIKE ? OR c.email LIKE ? OR c.phone LIKE ? OR r.code LIKE ?)"
        like = f"%{search}%"
        args += [like, like, like, like.upper()]

    sql += " ORDER BY r.created_at DESC"

    return render_template(
        "admin/requests.html",
        rows=query(sql, args),
        status=status,
        search=search,
    )


@admin_bp.route("/requests/<int:request_id>")
@login_required
def request_detail(request_id):
    req = query(
        """SELECT r.*, c.name AS customer_name, c.email, c.phone, c.address, c.town,
                  c.id AS customer_id, c.notes AS customer_notes
           FROM requests r JOIN customers c ON c.id = r.customer_id
           WHERE r.id = ?""",
        (request_id,),
        one=True,
    )
    if not req:
        flash("That request is gone.", "error")
        return redirect(url_for("admin.requests_list"))

    service_keys = [s for s in req["services"].split(",") if s]

    # The admin can play with a different date/window than the customer asked
    # for without saving anything.
    day = request.args.get("day") or req["preferred_day"] or ""
    window = request.args.get("window") or req["preferred_window"] or "any"
    window_key = window if window in config.WINDOWS else None

    matches = find_matches(day, window_key, req["duration_min"], service_keys) if day else []
    alternatives = []
    if not matches:
        alternatives = next_open_days(window_key, req["duration_min"], service_keys)

    appointments = query(
        """SELECT a.*, cr.name AS crew_name, cr.phone AS crew_phone
           FROM appointments a JOIN crew cr ON cr.id = a.crew_id
           WHERE a.request_id = ? ORDER BY a.day, a.start_min""",
        (request_id,),
    )

    history = query(
        """SELECT r.id, r.code, r.created_at, r.status, r.services
           FROM requests r WHERE r.customer_id = ? AND r.id != ?
           ORDER BY r.created_at DESC""",
        (req["customer_id"], request_id),
    )

    return render_template(
        "admin/request_detail.html",
        req=req,
        service_keys=service_keys,
        matches=matches,
        alternatives=alternatives,
        appointments=appointments,
        activity=query(
            "SELECT * FROM activity WHERE request_id = ? ORDER BY id DESC", (request_id,)
        ),
        history=history,
        day=day,
        window=window,
        today=date.today().isoformat(),
    )


@admin_bp.route("/requests/<int:request_id>/accept", methods=["POST"])
@login_required
def accept_request(request_id):
    """Say yes to a new request. It still needs a day and a person after this."""
    row = query("SELECT status FROM requests WHERE id = ?", (request_id,), one=True)
    if not row:
        flash("That request is gone.", "error")
        return redirect(url_for("admin.requests_list"))

    if row["status"] != "new":
        flash("That one has already been dealt with.", "error")
    else:
        execute("UPDATE requests SET status = 'accepted' WHERE id = ?", (request_id,))
        _log(request_id, "Accepted. Needs a day and a person.")
        flash("Accepted — now find them a slot.", "ok")

    return redirect(url_for("admin.request_detail", request_id=request_id))


@admin_bp.route("/requests/<int:request_id>/status", methods=["POST"])
@login_required
def set_status(request_id):
    status = request.form.get("status")
    if status not in config.REQUEST_STATUSES:
        flash("Unknown status.", "error")
        return redirect(url_for("admin.request_detail", request_id=request_id))

    execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
    if status == "cancelled":
        execute(
            "UPDATE appointments SET status = 'cancelled' WHERE request_id = ?", (request_id,)
        )
    if status == "completed":
        execute(
            """UPDATE appointments SET status = 'completed'
               WHERE request_id = ? AND status = 'scheduled'""",
            (request_id,),
        )

    _log(request_id, f"Status changed to {config.STATUS_LABELS[status]}.")
    flash("Status updated.", "ok")
    return redirect(url_for("admin.request_detail", request_id=request_id))


@admin_bp.route("/requests/<int:request_id>/note", methods=["POST"])
@login_required
def add_note(request_id):
    body = (request.form.get("body") or "").strip()
    if body:
        _log(request_id, body, kind="note")
    return redirect(url_for("admin.request_detail", request_id=request_id))


@admin_bp.route("/requests/<int:request_id>/schedule", methods=["POST"])
@login_required
def schedule(request_id):
    req = query("SELECT * FROM requests WHERE id = ?", (request_id,), one=True)
    if not req:
        flash("That request is gone.", "error")
        return redirect(url_for("admin.requests_list"))

    crew_id = request.form.get("crew_id", type=int)
    day = request.form.get("day", "")
    start_min = request.form.get("start_min", type=int)

    if not crew_id or not parse_day(day) or start_min is None:
        flash("Pick a person, a day and a start time.", "error")
        return redirect(url_for("admin.request_detail", request_id=request_id))

    end_min = start_min + req["duration_min"]

    # Re-check the slot at save time: the suggestion list could be minutes old
    # and someone else may have taken it.
    clash = query(
        """SELECT r.code FROM appointments a JOIN requests r ON r.id = a.request_id
           WHERE a.crew_id = ? AND a.day = ? AND a.status != 'cancelled'
             AND a.start_min < ? AND a.end_min > ?""",
        (crew_id, day, end_min, start_min),
        one=True,
    )
    if clash:
        flash(f"That overlaps job {clash['code']}. Pick another slot.", "error")
        return redirect(url_for("admin.request_detail", request_id=request_id, day=day))

    member = query("SELECT name FROM crew WHERE id = ?", (crew_id,), one=True)
    execute(
        """INSERT INTO appointments (request_id, crew_id, day, start_min, end_min, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (request_id, crew_id, day, start_min, end_min, _now()),
    )
    execute("UPDATE requests SET status = 'scheduled' WHERE id = ?", (request_id,))
    _log(request_id, f"Assigned to {member['name']} on {day}.")
    flash(f"Booked with {member['name']}.", "ok")
    return redirect(url_for("admin.request_detail", request_id=request_id))


@admin_bp.route("/appointments/<int:appointment_id>/<action>", methods=["POST"])
@login_required
def appointment_action(appointment_id, action):
    appointment = query(
        """SELECT a.*, cr.name AS crew_name FROM appointments a
           JOIN crew cr ON cr.id = a.crew_id WHERE a.id = ?""",
        (appointment_id,),
        one=True,
    )
    if not appointment:
        flash("That appointment is gone.", "error")
        return redirect(url_for("admin.dashboard"))

    request_id = appointment["request_id"]

    if action == "complete":
        execute("UPDATE appointments SET status = 'completed' WHERE id = ?", (appointment_id,))
        execute("UPDATE requests SET status = 'completed' WHERE id = ?", (request_id,))
        _log(request_id, f"{appointment['crew_name']} marked the job done.")
    elif action == "cancel":
        execute("UPDATE appointments SET status = 'cancelled' WHERE id = ?", (appointment_id,))
        still_on = query(
            """SELECT 1 FROM appointments
               WHERE request_id = ? AND status = 'scheduled'""",
            (request_id,),
            one=True,
        )
        if not still_on:
            execute("UPDATE requests SET status = 'accepted' WHERE id = ?", (request_id,))
        _log(request_id, f"Cancelled the visit with {appointment['crew_name']}.")
    else:
        flash("Unknown action.", "error")

    return redirect(
        request.form.get("back") or url_for("admin.request_detail", request_id=request_id)
    )


# ----------------------------------------------------------------- schedule --


@admin_bp.route("/schedule")
@login_required
def schedule_view():
    anchor = parse_day(request.args.get("day", "")) or date.today()
    monday, _ = week_bounds(anchor)
    days = [monday + timedelta(days=i) for i in range(7)]

    rows = query(
        """SELECT a.*, r.code, r.services,
                  c.name AS customer_name, c.address, c.town, c.phone,
                  cr.name AS crew_name
           FROM appointments a
           JOIN requests r ON r.id = a.request_id
           JOIN customers c ON c.id = r.customer_id
           JOIN crew cr ON cr.id = a.crew_id
           WHERE a.day BETWEEN ? AND ? AND a.status != 'cancelled'
           ORDER BY a.day, a.start_min""",
        (days[0].isoformat(), days[-1].isoformat()),
    )

    by_day = {d.isoformat(): [] for d in days}
    for row in rows:
        by_day[row["day"]].append(row)

    return render_template(
        "admin/schedule.html",
        days=days,
        by_day=by_day,
        monday=monday,
        prev_week=(monday - timedelta(days=7)).isoformat(),
        next_week=(monday + timedelta(days=7)).isoformat(),
        today=date.today(),
    )


# --------------------------------------------------------------------- crew --


@admin_bp.route("/crew", methods=["GET", "POST"])
@login_required
def crew_list():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Everyone needs a name.", "error")
        else:
            execute(
                """INSERT INTO crew (name, phone, email, max_jobs_day, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    name,
                    (request.form.get("phone") or "").strip(),
                    (request.form.get("email") or "").strip(),
                    request.form.get("max_jobs_day", type=int) or 2,
                    _now(),
                ),
            )
            flash(f"Added {name}. Set their hours next.", "ok")
        return redirect(url_for("admin.crew_list"))

    monday, sunday = week_bounds(date.today())
    members = query(
        """SELECT cr.*,
                  (SELECT COUNT(*) FROM appointments a
                    WHERE a.crew_id = cr.id AND a.status != 'cancelled'
                      AND a.day BETWEEN ? AND ?) AS jobs_week,
                  (SELECT COUNT(*) FROM crew_availability av WHERE av.crew_id = cr.id) AS blocks
           FROM crew cr ORDER BY cr.active DESC, cr.name""",
        (monday.isoformat(), sunday.isoformat()),
    )
    return render_template("admin/crew.html", members=members)


@admin_bp.route("/crew/<int:crew_id>", methods=["GET", "POST"])
@login_required
def crew_detail(crew_id):
    member = query("SELECT * FROM crew WHERE id = ?", (crew_id,), one=True)
    if not member:
        flash("No such crew member.", "error")
        return redirect(url_for("admin.crew_list"))

    if request.method == "POST":
        execute(
            """UPDATE crew SET name = ?, phone = ?, email = ?, skills = ?,
                   max_jobs_day = ?, active = ?, notes = ? WHERE id = ?""",
            (
                (request.form.get("name") or member["name"]).strip(),
                (request.form.get("phone") or "").strip(),
                (request.form.get("email") or "").strip(),
                ",".join(s for s in request.form.getlist("skills") if s in config.SERVICES),
                request.form.get("max_jobs_day", type=int) or 2,
                1 if request.form.get("active") else 0,
                (request.form.get("notes") or "").strip(),
                crew_id,
            ),
        )
        flash("Saved.", "ok")
        return redirect(url_for("admin.crew_detail", crew_id=crew_id))

    availability = query(
        "SELECT * FROM crew_availability WHERE crew_id = ? ORDER BY weekday, start_min",
        (crew_id,),
    )
    by_weekday = {i: [] for i in range(7)}
    for block in availability:
        by_weekday[block["weekday"]].append(block)

    upcoming = query(
        """SELECT a.*, r.code, c.name AS customer_name, c.address, c.town
           FROM appointments a
           JOIN requests r ON r.id = a.request_id
           JOIN customers c ON c.id = r.customer_id
           WHERE a.crew_id = ? AND a.day >= ? AND a.status != 'cancelled'
           ORDER BY a.day, a.start_min LIMIT 20""",
        (crew_id, date.today().isoformat()),
    )

    return render_template(
        "admin/crew_detail.html",
        member=member,
        by_weekday=by_weekday,
        time_off=query(
            "SELECT * FROM crew_time_off WHERE crew_id = ? ORDER BY day", (crew_id,)
        ),
        upcoming=upcoming,
        skills=[s for s in member["skills"].split(",") if s],
        today=date.today().isoformat(),
    )


@admin_bp.route("/crew/<int:crew_id>/availability", methods=["POST"])
@login_required
def add_availability(crew_id):
    weekdays = [int(w) for w in request.form.getlist("weekday") if w.isdigit()]
    start = _hhmm_to_min(request.form.get("start"))
    end = _hhmm_to_min(request.form.get("end"))

    if not weekdays or start is None or end is None or end <= start:
        flash("Pick at least one day and an end time after the start.", "error")
        return redirect(url_for("admin.crew_detail", crew_id=crew_id))

    for weekday in weekdays:
        if 0 <= weekday <= 6:
            execute(
                """INSERT INTO crew_availability (crew_id, weekday, start_min, end_min)
                   VALUES (?, ?, ?, ?)""",
                (crew_id, weekday, start, end),
            )
    flash("Hours added.", "ok")
    return redirect(url_for("admin.crew_detail", crew_id=crew_id))


@admin_bp.route("/crew/<int:crew_id>/availability/<int:block_id>/delete", methods=["POST"])
@login_required
def delete_availability(crew_id, block_id):
    execute("DELETE FROM crew_availability WHERE id = ? AND crew_id = ?", (block_id, crew_id))
    return redirect(url_for("admin.crew_detail", crew_id=crew_id))


@admin_bp.route("/crew/<int:crew_id>/timeoff", methods=["POST"])
@login_required
def add_time_off(crew_id):
    day = request.form.get("day", "")
    if not parse_day(day):
        flash("Pick a real date.", "error")
    else:
        execute(
            "INSERT INTO crew_time_off (crew_id, day, reason) VALUES (?, ?, ?)",
            (crew_id, day, (request.form.get("reason") or "").strip()),
        )
        flash("Marked as unavailable.", "ok")
    return redirect(url_for("admin.crew_detail", crew_id=crew_id))


@admin_bp.route("/crew/<int:crew_id>/timeoff/<int:off_id>/delete", methods=["POST"])
@login_required
def delete_time_off(crew_id, off_id):
    execute("DELETE FROM crew_time_off WHERE id = ? AND crew_id = ?", (off_id, crew_id))
    return redirect(url_for("admin.crew_detail", crew_id=crew_id))


def _hhmm_to_min(value):
    """'14:30' -> 870."""
    try:
        hours, minutes = value.split(":")
        total = int(hours) * 60 + int(minutes)
    except (AttributeError, ValueError):
        return None
    return total if 0 <= total <= 24 * 60 else None


# ---------------------------------------------------------------- customers --


@admin_bp.route("/customers")
@login_required
def customers_list():
    search = (request.args.get("q") or "").strip()
    sql = """SELECT c.*,
                    (SELECT COUNT(*) FROM requests r WHERE r.customer_id = c.id) AS jobs,
                    (SELECT MAX(r.created_at) FROM requests r WHERE r.customer_id = c.id) AS last_seen
             FROM customers c"""
    args = []
    if search:
        sql += " WHERE c.name LIKE ? OR c.email LIKE ? OR c.phone LIKE ? OR c.town LIKE ?"
        like = f"%{search}%"
        args = [like, like, like, like]
    sql += " ORDER BY last_seen DESC"
    return render_template("admin/customers.html", rows=query(sql, args), search=search)


@admin_bp.route("/customers/<int:customer_id>", methods=["GET", "POST"])
@login_required
def customer_detail(customer_id):
    customer = query("SELECT * FROM customers WHERE id = ?", (customer_id,), one=True)
    if not customer:
        flash("No such customer.", "error")
        return redirect(url_for("admin.customers_list"))

    if request.method == "POST":
        execute(
            "UPDATE customers SET notes = ? WHERE id = ?",
            ((request.form.get("notes") or "").strip(), customer_id),
        )
        flash("Notes saved.", "ok")
        return redirect(url_for("admin.customer_detail", customer_id=customer_id))

    return render_template(
        "admin/customer_detail.html",
        customer=customer,
        rows=query(
            "SELECT * FROM requests WHERE customer_id = ? ORDER BY created_at DESC",
            (customer_id,),
        ),
    )


# ------------------------------------------------------------------- export --


@admin_bp.route("/export/requests.csv")
@login_required
def export_requests():
    rows = query(
        """SELECT r.code, r.created_at, r.status, r.services, r.size,
                  r.duration_min,
                  c.name, c.email, c.phone, c.address, c.town,
                  a.day, a.start_min, cr.name AS crew
           FROM requests r
           JOIN customers c ON c.id = r.customer_id
           LEFT JOIN appointments a ON a.request_id = r.id AND a.status != 'cancelled'
           LEFT JOIN crew cr ON cr.id = a.crew_id
           ORDER BY r.created_at DESC"""
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "code", "received", "status", "services", "size",
            "expected_minutes",
            "customer", "email", "phone", "address", "town",
            "job_date", "job_start_min", "assigned_to",
        ]
    )
    for row in rows:
        writer.writerow([row[key] for key in row.keys()])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=requests-{date.today()}.csv"
        },
    )
