-- Every table the app uses. Safe to re-run: nothing here drops data.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT NOT NULL,
    address     TEXT NOT NULL,
    town        TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);

CREATE TABLE IF NOT EXISTS crew (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    phone          TEXT NOT NULL DEFAULT '',
    email          TEXT NOT NULL DEFAULT '',
    -- Comma separated service keys this person is trained on. Empty = all.
    skills         TEXT NOT NULL DEFAULT '',
    max_jobs_day   INTEGER NOT NULL DEFAULT 2,
    active         INTEGER NOT NULL DEFAULT 1,
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL
);

-- One row per recurring block of time a crew member can work.
CREATE TABLE IF NOT EXISTS crew_availability (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    crew_id   INTEGER NOT NULL REFERENCES crew(id) ON DELETE CASCADE,
    weekday   INTEGER NOT NULL,   -- 0 = Monday ... 6 = Sunday
    start_min INTEGER NOT NULL,   -- minutes past midnight
    end_min   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_avail_crew ON crew_availability(crew_id, weekday);

-- One-off days someone cannot work (vacation, exams, whatever).
CREATE TABLE IF NOT EXISTS crew_time_off (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    crew_id INTEGER NOT NULL REFERENCES crew(id) ON DELETE CASCADE,
    day     TEXT NOT NULL,        -- YYYY-MM-DD
    reason  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_timeoff_crew ON crew_time_off(crew_id, day);

CREATE TABLE IF NOT EXISTS requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,   -- short code the customer can look up
    customer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    services        TEXT NOT NULL,          -- comma separated service keys
    size            TEXT NOT NULL,          -- small | medium | large
    property_type   TEXT NOT NULL DEFAULT '',
    details         TEXT NOT NULL DEFAULT '',
    preferred_day   TEXT NOT NULL DEFAULT '',  -- YYYY-MM-DD, may be blank
    preferred_window TEXT NOT NULL DEFAULT 'any',
    status          TEXT NOT NULL DEFAULT 'new',
    -- How long we expect to be on site. This is a volunteer service, so time
    -- is the only quantity the app tracks about a job.
    duration_min    INTEGER NOT NULL DEFAULT 120,
    source          TEXT NOT NULL DEFAULT 'website',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status);

CREATE TABLE IF NOT EXISTS appointments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    crew_id    INTEGER NOT NULL REFERENCES crew(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,       -- YYYY-MM-DD
    start_min  INTEGER NOT NULL,
    end_min    INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled | completed | cancelled
    notes      TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_appt_day ON appointments(day);
CREATE INDEX IF NOT EXISTS idx_appt_crew_day ON appointments(crew_id, day);
CREATE INDEX IF NOT EXISTS idx_appt_request ON appointments(request_id);

-- Running log shown on the request page, so anyone picking up the job can
-- see what already happened.
CREATE TABLE IF NOT EXISTS activity (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'note',  -- note | system
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_request ON activity(request_id);
