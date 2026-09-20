"""Entry point. `python app.py` for local dev, `gunicorn app:app` in prod."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

# Load the .env sitting next to this file, not one relative to the working
# directory. Under a WSGI server the working directory is somewhere else, and
# a missed .env means the app quietly falls back to its insecure defaults.
load_dotenv(Path(__file__).parent / ".env")

import config  # noqa: E402  (must come after load_dotenv so env vars are seen)
import db  # noqa: E402
import scheduling  # noqa: E402
from views.admin import admin_bp  # noqa: E402
from views.public import public_bp  # noqa: E402

# Values that are fine on a laptop and unacceptable on the public internet.
PLACEHOLDER_SECRETS = {
    "SECRET_KEY": "dev-only-change-me",
    "ADMIN_PASSWORD": "letmein",
}


def _truthy(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def check_secrets():
    """
    Refuse to boot in production with the shipped defaults.

    Without this the site comes up looking perfectly fine while anyone who has
    read the source can log into /admin. Failing at startup is noisy, but it's
    noisy at deploy time rather than after someone finds it.
    """
    if _truthy("FLASK_DEBUG"):
        return

    unset = [name for name, default in PLACEHOLDER_SECRETS.items()
             if getattr(config, name) == default]
    if unset:
        raise RuntimeError(
            "Refusing to start: " + " and ".join(unset) + " still "
            + ("has" if len(unset) == 1 else "have") + " the default value.\n"
            "Set them in .env (or your host's environment) before going live.\n"
            "Generate a key with:  python -c \"import secrets; "
            "print(secrets.token_hex(32))\"\n"
            "For local development set FLASK_DEBUG=1 instead."
        )


def create_app():
    check_secrets()

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_PATH=config.DATABASE_PATH,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if _truthy("HTTPS_ONLY"):
        app.config["SESSION_COOKIE_SECURE"] = True

    db.init_db(app)
    app.teardown_appcontext(db.close_db)

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # Available in every template without passing it through each render call.
    app.jinja_env.globals.update(
        BUSINESS=config.BUSINESS,
        SERVICES=config.SERVICES,
        SIZES=config.SIZES,
        WINDOWS=config.WINDOWS,
        WEEKDAYS=config.WEEKDAYS,
        STATUS_LABELS=config.STATUS_LABELS,
        REQUEST_STATUSES=config.REQUEST_STATUSES,
        TRAVEL_BUFFER_MIN=config.TRAVEL_BUFFER_MIN,
        PROPERTY_TYPES=config.PROPERTY_TYPES,
        WORK=config.WORK,
    )
    app.jinja_env.filters.update(
        time=scheduling.fmt_time,
        timerange=lambda pair: scheduling.fmt_range(*pair),
        day=scheduling.fmt_day,
        hours=lambda minutes: f"{round(minutes / 30) / 2:g} hrs" if minutes else "-",
    )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=_truthy("FLASK_DEBUG"),
    )
