"""The pages customers see: marketing, the booking form, and status lookup."""

import re
import secrets
from datetime import date, datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

import config
from db import execute, query
from scheduling import job_duration

public_bp = Blueprint("public", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# No I/O/0/1 so nobody misreads a code over the phone.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_code():
    while True:
        code = "CW-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        if not query("SELECT 1 FROM requests WHERE code = ?", (code,), one=True):
            return code


def _now():
    return datetime.now().isoformat(timespec="seconds")


@public_bp.route("/")
def home():
    return render_template("public/home.html")


@public_bp.route("/services")
def services():
    return render_template("public/services.html")


@public_bp.route("/gallery")
def gallery():
    """
    There used to be a separate gallery page. With one job photographed it
    lives on the home page instead — this keeps any shared links working.
    """
    return redirect(url_for("public.home") + "#work", code=301)


@public_bp.route("/faq")
def faq():
    return render_template("public/faq.html")


# ------------------------------------------------------------------ booking --


@public_bp.route("/book", methods=["GET", "POST"])
def book():
    form = {
        "name": "",
        "email": "",
        "phone": "",
        "address": "",
        "town": "",
        "property_type": "",
        "size": "medium",
        "preferred_day": "",
        "preferred_window": "any",
        "details": "",
    }
    picked_services = []
    errors = {}

    if request.method == "POST":
        for field in form:
            form[field] = request.form.get(field, "").strip()
        picked_services = [s for s in request.form.getlist("services") if s in config.SERVICES]

        if not form["name"]:
            errors["name"] = "We need a name to put on the job."
        if not EMAIL_RE.match(form["email"]):
            errors["email"] = "That email doesn't look right."
        if len(re.sub(r"\D", "", form["phone"])) < 10:
            errors["phone"] = "Enter a 10 digit phone number."
        if not form["address"]:
            errors["address"] = "Street address, so we know where to park."
        if form["town"] not in config.BUSINESS["service_area"]:
            errors["town"] = "Pick a town we cover."
        if not picked_services:
            errors["services"] = "Pick at least one thing to clean."
        if form["size"] not in config.SIZES:
            errors["size"] = "Pick a size."

        if form["preferred_day"]:
            try:
                wanted = datetime.strptime(form["preferred_day"], "%Y-%m-%d").date()
                if wanted < date.today():
                    errors["preferred_day"] = "That day already happened."
            except ValueError:
                errors["preferred_day"] = "Use the date picker."

        if not errors:
            code = _save_request(form, picked_services)
            return redirect(url_for("public.thanks", code=code))

    return render_template(
        "public/book.html",
        form=form,
        picked_services=picked_services,
        errors=errors,
        today=date.today().isoformat(),
    )


def _save_request(form, picked_services):
    """Create (or refresh) the customer, then log the request. Returns the code."""
    existing = query(
        "SELECT * FROM customers WHERE lower(email) = lower(?)", (form["email"],), one=True
    )
    if existing:
        customer_id = existing["id"]
        execute(
            """UPDATE customers SET name = ?, phone = ?, address = ?, town = ?
               WHERE id = ?""",
            (form["name"], form["phone"], form["address"], form["town"], customer_id),
        )
    else:
        customer_id = execute(
            """INSERT INTO customers (name, email, phone, address, town, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (form["name"], form["email"], form["phone"], form["address"], form["town"], _now()),
        )

    duration = job_duration(picked_services, form["size"])
    code = _new_code()

    request_id = execute(
        """INSERT INTO requests
             (code, customer_id, services, size, property_type, details,
              preferred_day, preferred_window, status, duration_min, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, 'website', ?)""",
        (
            code,
            customer_id,
            ",".join(picked_services),
            form["size"],
            form["property_type"],
            form["details"],
            form["preferred_day"],
            form["preferred_window"] or "any",
            duration,
            _now(),
        ),
    )
    execute(
        "INSERT INTO activity (request_id, body, kind, created_at) VALUES (?, ?, 'system', ?)",
        (request_id, "Request came in from the website.", _now()),
    )
    return code


@public_bp.route("/thanks/<code>")
def thanks(code):
    row = query("SELECT * FROM requests WHERE code = ?", (code,), one=True)
    if not row:
        return redirect(url_for("public.home"))
    return render_template("public/thanks.html", req=row)


# ------------------------------------------------------------------- status --


@public_bp.route("/track")
def track():
    code = (request.args.get("code") or "").strip().upper()
    row = None
    not_found = False

    if code:
        row = query(
            """SELECT r.*, c.name AS customer_name
               FROM requests r JOIN customers c ON c.id = r.customer_id
               WHERE r.code = ?""",
            (code,),
            one=True,
        )
        not_found = row is None

    appointment = None
    if row:
        appointment = query(
            """SELECT a.*, cr.name AS crew_name, cr.phone AS crew_phone
               FROM appointments a JOIN crew cr ON cr.id = a.crew_id
               WHERE a.request_id = ? AND a.status != 'cancelled'
               ORDER BY a.day LIMIT 1""",
            (row["id"],),
            one=True,
        )

    return render_template(
        "public/track.html", code=code, req=row, appointment=appointment, not_found=not_found
    )


# -------------------------------------------- live time preview on the form --


@public_bp.route("/api/duration")
def api_duration():
    """
    Called by the request form as boxes get checked, so people can see roughly
    how long someone will be at their place. Same maths the scheduler uses.
    """
    picked = [s for s in request.args.getlist("services") if s in config.SERVICES]
    size = request.args.get("size", "medium")
    return jsonify({"duration_min": job_duration(picked, size) if picked else 0})
