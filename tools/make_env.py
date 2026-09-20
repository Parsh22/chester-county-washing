"""
Write a .env with freshly generated secrets.

    python tools/make_env.py                 # local development defaults
    python tools/make_env.py --prod          # print values to paste into a host
    python tools/make_env.py --prod --write  # write .env on the server for you

Run by setup.sh so a fresh clone never sits one forgotten edit away from
running with the shipped placeholder password.
"""

import pathlib
import secrets
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    production = "--prod" in sys.argv
    secret_key = secrets.token_hex(32)
    password = secrets.token_urlsafe(12) if production else secrets.token_urlsafe(9)

    if production and "--write" in sys.argv:
        target = ROOT / ".env"
        if target.exists():
            print(".env already exists — delete it first if you want new secrets.")
            return
        target.write_text(
            f"SECRET_KEY={secret_key}\n"
            f"ADMIN_PASSWORD={password}\n"
            "DATABASE_PATH=data/app.db\n"
            "HTTPS_ONLY=1\n"
        )
        target.chmod(0o600)
        print("Wrote .env (readable only by you).")
        print()
        print(f"    Your /admin password is:  {password}")
        print()
        print("Save that now — it is not stored anywhere you can read it back.")
        return

    if production:
        print("Set these in your host's environment (or its .env file).")
        print("Save the admin password somewhere — it isn't recoverable.\n")
        print(f"SECRET_KEY={secret_key}")
        print(f"ADMIN_PASSWORD={password}")
        print("DATABASE_PATH=data/app.db")
        print("HTTPS_ONLY=1")
        print("\nDo not set FLASK_DEBUG in production.")
        return

    target = ROOT / ".env"
    if target.exists():
        print(".env already exists — leaving it alone.")
        return

    target.write_text(
        "# Local development only. Gitignored — never commit this.\n"
        f"SECRET_KEY={secret_key}\n"
        f"ADMIN_PASSWORD={password}\n"
        "DATABASE_PATH=data/app.db\n"
        "HTTPS_ONLY=0\n"
        "FLASK_DEBUG=1\n"
    )
    print(f"Wrote .env. Your local /admin password is: {password}")


if __name__ == "__main__":
    main()
