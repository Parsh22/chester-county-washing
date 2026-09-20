"""Thin wrapper around sqlite3. One connection per request, closed by Flask."""

import os
import sqlite3
from pathlib import Path

from flask import current_app, g

PROJECT_ROOT = Path(__file__).parent
SCHEMA_FILE = PROJECT_ROOT / "schema.sql"


def db_path(app):
    """
    Absolute path to the SQLite file.

    A relative DATABASE_PATH is resolved against the project directory, not
    the working directory. Under a WSGI server the working directory is
    usually somewhere else entirely, and getting this wrong means quietly
    creating an empty database in the wrong place.
    """
    configured = Path(app.config["DATABASE_PATH"]).expanduser()
    if not configured.is_absolute():
        configured = PROJECT_ROOT / configured
    return configured


def get_db():
    """Connection for the current request, created lazily."""
    if "db" not in g:
        path = db_path(current_app)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run a write and return the new row id."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    new_id = cur.lastrowid
    cur.close()
    return new_id


def init_db(app):
    """Create any missing tables. Called on startup so a fresh deploy works."""
    path = db_path(app)
    os.makedirs(path.parent, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_FILE.read_text())
    conn.commit()
    conn.close()
    return path
