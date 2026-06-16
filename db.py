"""SQLite storage layer for the pick-up basketball coordinator.

A new connection is opened per request (SQLite file access is cheap and this
keeps things thread-safe across the HTTP server threads).
"""
import os
import sqlite3
import secrets

DB_PATH = os.path.join(os.path.dirname(__file__), "pickup.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL UNIQUE,
    token        TEXT NOT NULL UNIQUE,
    is_organizer INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS games (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date     TEXT NOT NULL,           -- YYYY-MM-DD (usually Friday, sometimes Thursday)
    start_time    TEXT NOT NULL DEFAULT '07:00',
    teams_locked  INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS availability (
    game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    status    TEXT NOT NULL CHECK (status IN ('in', 'out')),
    PRIMARY KEY (game_id, player_id)
);

CREATE TABLE IF NOT EXISTS assignments (
    game_id   INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    team      TEXT NOT NULL CHECK (team IN ('light', 'dark')),
    PRIMARY KEY (game_id, player_id)
);
"""


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def new_token():
    return secrets.token_urlsafe(12)
