"""Storage layer.

Uses **Postgres** when a connection string is present in the environment
(`DATABASE_URL` or `POSTGRES_URL`) — this is the path used on Vercel, where the
local filesystem is read-only/ephemeral and SQLite cannot persist.

Falls back to a local **SQLite** file otherwise, so local development still runs
with zero installs. App code is written against one small interface (`get_conn`
returning a `Conn` that takes `?` placeholders); the wrapper adapts to whichever
backend is active.
"""
import os
import secrets

DSN = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
USE_PG = bool(DSN)

if USE_PG:
    import psycopg
    from psycopg.rows import dict_row
else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), "pickup.db")


class Conn:
    """One interface over both backends, with a single `?` placeholder style.

    Returns the underlying cursor from `execute`, so callers can chain
    `.fetchone()` / `.fetchall()` and iterate exactly as with sqlite3.
    """

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        if USE_PG:
            sql = sql.replace("?", "%s")  # our SQL never contains a literal '?'
        return self._raw.execute(sql, params)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def get_conn():
    if USE_PG:
        return Conn(psycopg.connect(DSN, row_factory=dict_row, autocommit=False))
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    return Conn(raw)


def _schema_statements():
    pk = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ts = ("TIMESTAMPTZ NOT NULL DEFAULT now()" if USE_PG
          else "TEXT NOT NULL DEFAULT (datetime('now'))")
    return [
        f"""CREATE TABLE IF NOT EXISTS players (
            id           {pk},
            name         TEXT NOT NULL,
            email        TEXT NOT NULL UNIQUE,
            token        TEXT NOT NULL UNIQUE,
            is_organizer INTEGER NOT NULL DEFAULT 0,
            created_at   {ts}
        )""",
        f"""CREATE TABLE IF NOT EXISTS games (
            id           {pk},
            game_date    TEXT NOT NULL,
            start_time   TEXT NOT NULL DEFAULT '07:00',
            teams_locked INTEGER NOT NULL DEFAULT 0,
            created_at   {ts}
        )""",
        """CREATE TABLE IF NOT EXISTS availability (
            game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            status    TEXT NOT NULL CHECK (status IN ('in', 'out')),
            PRIMARY KEY (game_id, player_id)
        )""",
        """CREATE TABLE IF NOT EXISTS assignments (
            game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
            player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            team      TEXT NOT NULL CHECK (team IN ('light', 'dark')),
            PRIMARY KEY (game_id, player_id)
        )""",
    ]


def init_db():
    conn = get_conn()
    for stmt in _schema_statements():
        conn.execute(stmt)
    conn.commit()
    _maybe_bootstrap_admin(conn)
    conn.close()


def _maybe_bootstrap_admin(conn):
    """On a fresh deploy, create the first organizer from ADMIN_EMAIL/ADMIN_NAME.

    No-op if the env var is unset, the email already exists, or an organizer is
    already present. The resulting admin link is retrieved via /setup.
    """
    email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    if not email:
        return
    if conn.execute("SELECT 1 FROM players WHERE is_organizer = 1 LIMIT 1").fetchone():
        return
    if conn.execute("SELECT 1 FROM players WHERE email = ?", (email,)).fetchone():
        return
    name = (os.environ.get("ADMIN_NAME") or email.split("@")[0]).strip()
    conn.execute(
        "INSERT INTO players (name, email, token, is_organizer) VALUES (?, ?, ?, 1)",
        (name, email, new_token()),
    )
    conn.commit()


def new_token():
    return secrets.token_urlsafe(12)
