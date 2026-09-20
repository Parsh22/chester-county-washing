"""
PythonAnywhere WSGI entry point.

On the Web tab, click the "WSGI configuration file" link, delete everything
in the editor that opens, and paste this file in its place. Then Save and
hit the green Reload button.

There is nothing to edit here — the project path is worked out from your
home directory, so it's the same for every account.
"""

import os
import sys

# PythonAnywhere runs this as your user, so ~ is /home/<your-username>.
PROJECT = os.path.expanduser("~/chester-county-washing")

if not os.path.isdir(PROJECT):
    raise RuntimeError(
        f"No project at {PROJECT}. Either the git clone didn't run, or it "
        "landed somewhere else. In a Bash console run:  ls ~"
    )

# Put the project on the import path so `import app` finds our app.py.
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# app.py loads the .env next to itself, so this is belt and braces — but it
# also gives a clearer error than "Refusing to start" if the file is missing.
if not os.path.isfile(os.path.join(PROJECT, ".env")):
    raise RuntimeError(
        "No .env in the project. In a Bash console run:\n"
        "  cd ~/chester-county-washing && python3.12 tools/make_env.py --prod --write"
    )

from app import app as application  # noqa: E402,F401
