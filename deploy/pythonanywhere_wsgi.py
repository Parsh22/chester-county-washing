"""
PythonAnywhere WSGI entry point.

Copy the contents of this file into the WSGI configuration file that
PythonAnywhere creates for you — the Web tab links to it, and it lives at:

    /var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py

Replace YOURUSERNAME below with your PythonAnywhere username, delete
everything else that's already in that file, and hit Reload.
"""

import os
import sys

PROJECT = "/home/YOURUSERNAME/chester-county-washing"

# Put the project on the import path so `import app` finds our app.py.
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# app.py calls load_dotenv() itself, but only looks in the working directory,
# which isn't the project when running under WSGI. Point it at the real file.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(PROJECT, ".env"))

from app import app as application  # noqa: E402,F401
