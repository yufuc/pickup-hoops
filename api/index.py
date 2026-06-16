"""Vercel Python serverless entry point.

Vercel's Python runtime looks for a top-level class named `handler` (a
BaseHTTPRequestHandler subclass) and invokes it once per request — there is no
long-lived `serve_forever()`. We subclass the app's existing handler so all the
routing is reused. The schema is created lazily on the first request (see
app.Handler._dispatch), so nothing touches the database at build/import time.
"""
import os
import sys

# Make the project root importable (app.py, db.py, ... live one level up).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import Handler  # noqa: E402


class handler(Handler):  # Vercel detects this top-level `handler` class
    pass
