# Running it on your own server instead

If you ever move off a managed host onto a VPS, the whole app is:

```bash
gunicorn app:app --bind 127.0.0.1:8000 --workers 2 --threads 4
```

Put nginx (or Caddy, which does HTTPS automatically) in front of that,
proxying to port 8000, and set these in the service environment:

    SECRET_KEY=...
    ADMIN_PASSWORD=...
    DATABASE_PATH=/var/lib/chester-washing/app.db
    HTTPS_ONLY=1

`DATABASE_PATH` must point somewhere that survives redeploys. That's the only
real constraint this app puts on a host.
