"""Domain logic shared by the web handlers and the background scheduler."""
import random
from datetime import datetime, timedelta

from emailer import send_email

# Notifications fire once the game is within this many hours. Sending at the
# 48h mark keeps every player inside the requested "36-48 hours before" window.
NOTIFY_WINDOW_HOURS = 48

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def game_datetime(game):
    """Combine a game's date + start_time into a datetime."""
    return datetime.strptime(f"{game['game_date']} {game['start_time']}", "%Y-%m-%d %H:%M")


def game_label(game):
    dt = game_datetime(game)
    return f"{DAY_NAMES[dt.weekday()]}, {dt.strftime('%b %d')} at {dt.strftime('%-I:%M %p')}"


def in_players(conn, game_id):
    return conn.execute(
        """SELECT p.* FROM players p
           JOIN availability a ON a.player_id = p.id
           WHERE a.game_id = ? AND a.status = 'in'
           ORDER BY p.name""",
        (game_id,),
    ).fetchall()


def suggest_teams(conn, game_id):
    """Randomly split the 'in' players into two balanced teams.

    Overwrites any existing (unlocked) suggestion. The organizer can then
    tweak individual assignments before locking.
    """
    players = in_players(conn, game_id)
    ids = [p["id"] for p in players]
    random.shuffle(ids)
    conn.execute("DELETE FROM assignments WHERE game_id = ?", (game_id,))
    for i, pid in enumerate(ids):
        team = "light" if i % 2 == 0 else "dark"
        conn.execute(
            "INSERT INTO assignments (game_id, player_id, team) VALUES (?, ?, ?)",
            (game_id, pid, team),
        )
    conn.commit()


def set_assignment(conn, game_id, player_id, team):
    """team is 'light', 'dark', or 'bench' (bench removes the assignment)."""
    conn.execute(
        "DELETE FROM assignments WHERE game_id = ? AND player_id = ?",
        (game_id, player_id),
    )
    if team in ("light", "dark"):
        conn.execute(
            "INSERT INTO assignments (game_id, player_id, team) VALUES (?, ?, ?)",
            (game_id, player_id, team),
        )
    conn.commit()


def team_roster(conn, game_id, team):
    return conn.execute(
        """SELECT p.* FROM players p
           JOIN assignments a ON a.player_id = p.id
           WHERE a.game_id = ? AND a.team = ?
           ORDER BY p.name""",
        (game_id, team),
    ).fetchall()


def notify_game(conn, game_id):
    """Email every assigned player their team. Returns number of emails sent.

    No-op (returns 0) if teams aren't locked or the game was already notified.
    """
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None or not game["teams_locked"] or game["notified"]:
        return 0

    label = game_label(game)
    light = team_roster(conn, game_id, "light")
    dark = team_roster(conn, game_id, "dark")

    def names(roster):
        return ", ".join(p["name"] for p in roster) or "(none)"

    sent = 0
    for team, roster in (("LIGHT", light), ("DARK", dark)):
        for player in roster:
            subject = f"Hoops {label} — you're on {team}"
            body = (
                f"Hi {player['name']},\n\n"
                f"You're IN for pick-up basketball: {label}.\n\n"
                f"Your team: {team}  (wear a {team.lower()} shirt)\n\n"
                f"LIGHT: {names(light)}\n"
                f"DARK:  {names(dark)}\n\n"
                f"See you on the court!"
            )
            send_email(conn, player["email"], subject, body, game_id=game_id)
            sent += 1

    conn.execute("UPDATE games SET notified = 1 WHERE id = ?", (game_id,))
    conn.commit()
    return sent


def due_for_notification(conn, now=None):
    """Locked, un-notified games whose start is within the notify window."""
    now = now or datetime.now()
    rows = conn.execute(
        "SELECT * FROM games WHERE teams_locked = 1 AND notified = 0"
    ).fetchall()
    due = []
    for g in rows:
        remaining = game_datetime(g) - now
        if timedelta(0) < remaining <= timedelta(hours=NOTIFY_WINDOW_HOURS):
            due.append(g)
    return due
