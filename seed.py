"""Populate the database with a few players and the upcoming Friday game.

Run once:  python3 seed.py   (safe to re-run; it skips existing emails)
"""
from datetime import date, timedelta

import db

PLAYERS = [
    ("Mike Chen", "michaelchen@navapbc.com", 1),  # organizer
    ("Alex Rivera", "alex@example.com", 0),
    ("Sam Park", "sam@example.com", 0),
    ("Jordan Lee", "jordan@example.com", 0),
    ("Casey Wu", "casey@example.com", 0),
    ("Drew Kim", "drew@example.com", 0),
    ("Pat Nguyen", "pat@example.com", 0),
    ("Robin Diaz", "robin@example.com", 0),
]


def next_friday():
    today = date.today()
    return today + timedelta(days=(4 - today.weekday()) % 7 or 7)


def main():
    db.init_db()
    conn = db.get_conn()
    for name, email, is_org in PLAYERS:
        exists = conn.execute("SELECT 1 FROM players WHERE email = ?", (email,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO players (name, email, token, is_organizer) VALUES (?, ?, ?, ?)",
                (name, email, db.new_token(), is_org),
            )
    if not conn.execute("SELECT 1 FROM games").fetchone():
        conn.execute(
            "INSERT INTO games (game_date, start_time) VALUES (?, ?)",
            (next_friday().isoformat(), "07:00"),
        )
    conn.commit()

    print("\nSeeded. Magic links:")
    for p in conn.execute("SELECT * FROM players ORDER BY is_organizer DESC, name"):
        kind = "ADMIN" if p["is_organizer"] else "player"
        url = f"/admin/{p['token']}" if p["is_organizer"] else f"/p/{p['token']}"
        print(f"  [{kind}] {p['name']:<14} http://localhost:8000{url}")
    conn.close()


if __name__ == "__main__":
    main()
