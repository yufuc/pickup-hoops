"""Vercel Python serverless entry point.

Vercel's Python runtime invokes a class named `handler` (a BaseHTTPRequestHandler
subclass) once per request — there is no long-lived `serve_forever()`. We reuse
the app's existing handler/routing unchanged and just ensure the schema exists.
"""
import os
import sys

# Make the project root importable (app.py, db.py, ... live one level up).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from app import Handler as handler  # noqa: E402  (Vercel looks for `handler`)

db.init_db()
