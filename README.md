# Chester County Community Washing

A website and a small operations tool for a **volunteer** pressure washing
group.

The public side is a normal site where a neighbor can see what you do and send
a request. The private side (`/admin`) is where the work actually happens:
requests come in, you accept the ones you can take, the app tells you which
crew member is genuinely free on the day they wanted, and you book it.

There is no money anywhere in this project — no prices, no quotes, no
payments. The quantity it tracks instead is **time**: how long a job takes and
who has hours to give. If you ever did want to charge, that's a real feature to
add, not a setting to flip.

Built with Flask and SQLite. No build step, no npm, one file to configure.

---

## Run it locally

```bash
./setup.sh              # makes a virtualenv and installs three packages
source .venv/bin/activate
python seed.py          # optional: fills it with a fake week so it isn't empty
python app.py
```

Open http://127.0.0.1:5000. The ops side is at `/admin` and the default
password is `letmein` (change it — see below).

---

## What's in here

| File | What it does |
|---|---|
| `config.py` | **Start here.** Group name, phone, towns you cover, services, job lengths, booking windows. |
| `app.py` | Wires Flask together. Registers the two blueprints and the template filters. |
| `views/public.py` | Marketing pages, the gallery, the booking form, the status lookup. |
| `views/admin.py` | Login, dashboard, requests, scheduling, crew, customers, CSV export. |
| `scheduling.py` | How long a job takes, and the availability matcher. |
| `db.py` / `schema.sql` | SQLite setup. Tables are created on startup. |
| `seed.py` | Sample crew, customers and jobs for demoing. |
| `smoke_test.py` | Clicks through every page and both flows. Run it after you change something. |
| `templates/` | Jinja templates. `public/` and `admin/` each have their own base layout. |
| `templates/_icons.html` | Inline SVG icons as a Jinja macro — `{{ icon('driveway') }}`. |
| `static/style.css` | All the styling, hand written, no framework. Token scales at the top. |
| `static/photos/` | Real job photos. See its README before adding any. |
| `import_photos.py` | Turns a wide side-by-side phone photo into two web-ready JPEGs. |
| `tools/make_env.py` | Generates a `.env` with real secrets (`--prod` prints values for a host). |
| `DEPLOY.md` | How to get this on the internet. |

---

## Photos

The site is built around before/after pairs, because that's the product.
Every image on it is a real job — there are no placeholders and no stock
photography. Services we haven't photographed show an icon rather than a
stand-in picture.

At the moment that's **one townhouse deck**, shot twice, which is why the home page
says so in as many words instead of pretending to a portfolio.

Photos live in `static/photos/jobs/` and are listed in `WORK` in `config.py`.
`import_photos.py` turns a wide side-by-side phone shot into two optimised
JPEGs:

```bash
python import_photos.py "~/Desktop/Before&After 3.png" driveway-main
```

Full instructions, including how to shoot pairs that line up, are in
`static/photos/README.md`.

There's deliberately **no drag-slider**. The two halves of a phone
before/after aren't taken from an identical position, so wiping between them
looks broken. Side by side with clear labels is honest and reads better on a
phone.

---

## Styling

`static/style.css` starts with a token block and everything else uses it:

- **Spacing** on a 4px scale (`--s1` … `--s9`). Don't invent values between them.
- **Type** on a fixed scale (`--t-xs` … `--t-4xl`), dropping down at 720px.
- **Radius** 4/8/12/16, **shadows** in three tiers. Never ad hoc.
- Numbers — durations, times, counts — get `font-variant-numeric: tabular-nums`
  so columns of figures actually line up.

Templates carry no inline styles. If you need spacing, use `.mt-4` and friends
rather than a one-off `style=""`, otherwise the rhythm drifts.

---

## The request pipeline

`new` → `accepted` → `scheduled` → `completed`, plus `cancelled` from anywhere.

A request arrives as **new**. Somebody reads it and hits *Accept this request*
if it's one you can take, which moves it to **accepted** — meaning yes, but it
still needs a day and a person. Booking a crew member moves it to
**scheduled**. Marking the visit done moves it to **completed**. Cancelling the
only scheduled visit drops it back to **accepted** rather than losing it.

---

## How the matching works

This is the part that isn't just CRUD, so it's worth understanding.

Every crew member sets **weekly hours** (repeating blocks like "Tue 4pm–8pm")
and can mark **one-off days off**. Each service has a typical duration, so a
request for a large driveway plus a fence knows it needs about 4 hours.

When you open a request and pick a day, `find_matches()` in `scheduling.py`:

1. Drops anyone inactive, off that day, or not trained on the services asked for.
2. Drops anyone already at their max jobs for that day.
3. Looks at their hours for that weekday, intersected with the time window the
   customer picked.
4. Walks their existing appointments for that day — each padded by
   `TRAVEL_BUFFER_MIN` on both sides — and finds the earliest gap the job fits in.
5. Sorts whoever is left by who has had the lightest week, so the work spreads out.

If nobody fits, it scans the next three weeks and offers you the days that do
work, so you have something concrete to send back to the customer.

Booking re-checks for a collision at save time, because the suggestion list on
your screen could be a few minutes stale.

---

## Making it yours

Almost everything is in `config.py`:

- `BUSINESS` — name, region, phone, email, and the towns you drive to
  (`service_area` doubles as the request form's town list, so a place that
  isn't on it can't be booked)
- `SERVICES` — what you offer, and how long each takes at each property size
- `SIZES` — what "small / medium / large" means to you
- `WINDOWS` — the time slots customers can pick
- `TRAVEL_BUFFER_MIN` — how much slack between two jobs

How job length is worked out (extra services on one visit count for 70%,
rounded up to the next half hour) lives in `job_duration()` in
`scheduling.py`.

---

## Deploying it

See **[DEPLOY.md](DEPLOY.md)** for the full walkthrough.

Short version: this app needs a host with a **filesystem that survives
restarts**, because the database is a single SQLite file. That rules out
Vercel, Netlify and Render's free tier, all of which would silently wipe your
customers on every deploy.

The recommendation is **PythonAnywhere's free tier** — persistent disk, no
cold starts, no credit card, at `yourname.pythonanywhere.com`. If you want a
custom domain, `render.yaml` here sets up Render's $7/month starter plan with
a disk attached.

## Environment variables

Copy `.env.example` to `.env` for local use; set these in your host's
dashboard in production.

| Variable | Why |
|---|---|
| `SECRET_KEY` | Signs the login cookie. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `ADMIN_PASSWORD` | The password for `/admin`. **Change this before you deploy.** |
| `DATABASE_PATH` | Where the SQLite file goes. Must be on a persistent disk in production. |
| `HTTPS_ONLY` | Set to `1` once you're on https so the session cookie is https-only. |

---

## Testing

```bash
python smoke_test.py
```

It spins up a temporary database, walks every page, checks every image and
stylesheet actually resolves, submits the booking form (good and bad input),
logs into the admin, accepts a request, books a job, tries to double-book the
same slot, and completes it. 53 checks, all green.

---

## Things to know before this is a real business tool

- **One shared password.** Everyone on the team uses the same login and can see
  everything. Fine for five people who know each other; if you grow, add a
  `users` table and per-person logins.
- **No email or texts go out.** The app writes down what was booked, but you
  still send the confirmation yourself. The request page has a pre-written
  message you can copy. Adding real email means a service like Resend or
  SendGrid and about 30 lines in `views/admin.py`.
- **Back up the database.** It's one file. Copy it somewhere weekly:
  `sqlite3 data/app.db ".backup backup.db"`.
- **Crew can't log in.** They see their schedule when you send it. A per-person
  view would be the next feature worth building.
