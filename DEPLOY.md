# Putting this on the internet

## What this app needs from a host

Exactly one unusual thing: **a filesystem that survives restarts.** The
database is a single SQLite file. Hosts that give you a fresh container on
every deploy (Vercel, Netlify, Render's free tier) will erase your crew,
customers and bookings without telling you.

Everything else is ordinary: Python 3.12, three packages, one process.

## Recommended: PythonAnywhere (free)

Free forever, no credit card, real persistent disk, and — unlike free tiers
that sleep — it doesn't cold-start. A neighbor clicking your link gets the
page immediately rather than staring at a blank tab for 50 seconds.

The trade-off is the address: `yourname.pythonanywhere.com`. Custom domains
need a paid plan. If you want `chestercountywashing.org`, skip to
[Render](#alternative-render-7month) below.

### 1. Put the code on GitHub — done

The code is pushed to
[`Parsh22/chester-county-washing`](https://github.com/Parsh22/chester-county-washing).
`.env`, `data/` and `.venv/` are gitignored, so no secrets and no customer
data left the laptop.

The repo is **private**, which matters for the next step: PythonAnywhere
can't clone it without credentials. Two ways round that, in step 3.

### 2. Make a PythonAnywhere account

[pythonanywhere.com](https://www.pythonanywhere.com) → **Pricing & signup** →
**Create a Beginner account** (the free one). Your username becomes your web
address, so pick something like `chestercountywashing`.

> This is a **new account, separate from GitHub**. Everywhere below,
> `PA-USERNAME` means this PythonAnywhere username — not `Parsh22`.

### 3. Clone and install

Open **Consoles → Bash**.

Because the repo is private, a plain `git clone` will fail — GitHub stopped
accepting account passwords over git years ago. Pick one of these:

**Option A — make the repo public (simplest).** There is nothing secret in
it: no passwords, no database, no customer details. On GitHub go to the repo
→ **Settings** → scroll to **Danger Zone** → **Change visibility** →
**Make public**. Then the plain clone below just works.

**Option B — keep it private, use a read-only token.** On GitHub:
**Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token**. Set *Repository access* to **Only select
repositories → chester-county-washing**, and under *Repository permissions*
set **Contents: Read-only**. Nothing else. Generate it and copy the token —
it's shown once.

Then, either way:

```bash
git clone https://github.com/Parsh22/chester-county-washing.git
cd chester-county-washing
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

With Option B the clone asks for a username and password: enter `Parsh22`
and paste the **token** as the password. To avoid re-entering it on every
`git pull`, run `git config credential.helper store` inside the repo
afterwards — that writes the token in plain text to `~/.git-credentials` on
your PythonAnywhere account, which is a fair trade for a read-only token
scoped to one repo, but don't do it with a token that can write.

### 4. Create the .env on the server

Still in the Bash console:

```bash
python3.12 tools/make_env.py --prod --write
```

That generates the secrets, writes `.env`, and locks it to your account
(mode 600). It prints your `/admin` password once — **copy it somewhere safe
now**, it isn't stored anywhere you can read back.

### 5. Point the web app at it

Go to the **Web** tab → **Add a new web app** → **Manual configuration** (not
the Flask option) → **Python 3.12**. Then set three things on that page:

| Field | Value |
|---|---|
| **Source code** | `/home/PA-USERNAME/chester-county-washing` |
| **Virtualenv** | `/home/PA-USERNAME/chester-county-washing/.venv` |
| **WSGI configuration file** | click it, then paste the contents of `deploy/pythonanywhere_wsgi.py` over everything in that file, replacing `YOURUSERNAME` |

Under **Static files**, add one mapping so images and CSS don't go through
Python:

| URL | Directory |
|---|---|
| `/static/` | `/home/PA-USERNAME/chester-county-washing/static/` |

Hit the big green **Reload** button.

### 6. Check it

Visit `https://PA-USERNAME.pythonanywhere.com`. If something's wrong, the **Web**
tab has an error log — the traceback is almost always in there.

A blank "Refusing to start" error in the log means step 4 didn't take: the app
found no `.env`, so it stopped rather than run with the default password.

### Keeping it alive

Free accounts ask you to click a **"Run until 3 months from today"** button on
the Web tab every three months. They email you first. Miss it and the site
goes down until you click it — nothing is lost.

### Updating it later

```bash
cd chester-county-washing && git pull && .venv/bin/pip install -r requirements.txt
```

then **Reload** on the Web tab.

---

## Alternative: Render ($7/month)

Worth it when you want your own domain, or automatic deploys on every push.

`render.yaml` in this repo already describes the whole setup. Push to GitHub,
then on [render.com](https://render.com): **New → Blueprint**, pick the repo.
It creates the web service, attaches a 1 GB disk at `/var/data`, generates
`SECRET_KEY`, and prompts you for `ADMIN_PASSWORD`.

The blueprint uses the **starter** plan on purpose. Render's free tier has no
persistent disk, so the database would be wiped on every deploy.

For a custom domain: buy one, then **Settings → Custom Domains** in Render and
follow the DNS instructions. HTTPS is automatic.

---

## Before you tell anyone the address

The site works the moment it's up, but the scheduler can't match anyone until
the crew exists. In `/admin`:

1. **Crew → Add someone** for each volunteer.
2. Open each one and give them **weekly hours**. This is the important bit —
   somebody with no hours can never be matched to a job, and the request page
   will just say nobody is free.
3. Mark any known **days off**.
4. Send yourself a test request from the public form, then accept and book it,
   to confirm the whole loop works on the real server.

**Don't run `seed.py` in production.** It inserts eight fictional customers.
It's for local demos only.

## Looking after it

- **Back up the database.** It's one file and there's no undo:
  ```bash
  sqlite3 data/app.db ".backup backup-$(date +%F).db"
  ```
  Download it from the Files tab now and then.
- **The admin password is shared.** Anyone who has it can see every
  customer's address and phone number. Change it if someone leaves the crew —
  edit `.env` and reload.
- **Real people's addresses are in there now.** That's worth treating
  carefully: don't paste exports into group chats, and keep the repo's
  `data/` directory out of git (it already is).
