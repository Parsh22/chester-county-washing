#!/usr/bin/env bash
# One-time local setup: virtualenv, dependencies and a .env with real secrets.
set -euo pipefail
cd "$(dirname "$0")"

PYTHON=${PYTHON:-python3}
echo "Using $($PYTHON -V)"

if [ ! -d .venv ]; then
  echo "Creating .venv"
  "$PYTHON" -m venv .venv
fi

PIP_ARGS=()

# Corporate laptops often sit behind a TLS-inspecting proxy, which Python
# doesn't trust even though the browser does. If that's this machine, hand pip
# the certificate bundle out of the macOS keychain.
if [ "$(uname)" = "Darwin" ] && ! .venv/bin/python -m pip download --no-deps -d /tmp/_pipcheck pip >/dev/null 2>&1; then
  echo "pip can't verify TLS — exporting the system certificates"
  security find-certificate -a -p /System/Library/Keychains/SystemRootCertificates.keychain > .ca-bundle.pem 2>/dev/null || true
  security find-certificate -a -p /Library/Keychains/System.keychain >> .ca-bundle.pem 2>/dev/null || true
  PIP_ARGS+=(--cert .ca-bundle.pem)
fi
rm -rf /tmp/_pipcheck

.venv/bin/python -m pip install --quiet --upgrade pip "${PIP_ARGS[@]+"${PIP_ARGS[@]}"}"
.venv/bin/python -m pip install --quiet -r requirements.txt "${PIP_ARGS[@]+"${PIP_ARGS[@]}"}"

# Generate real secrets rather than copying the placeholders, so a fresh clone
# is never one forgotten edit away from shipping "letmein".
if [ ! -f .env ]; then
  .venv/bin/python tools/make_env.py
fi

cat <<'MSG'

Done. Next:

  source .venv/bin/activate
  python seed.py      # optional sample data, local only
  python app.py       # http://127.0.0.1:5000

To put it on the internet, read DEPLOY.md.

MSG
