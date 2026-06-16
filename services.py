"""Domain logic shared by the web handlers."""
import random
from datetime import datetime

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


def team_summary_text(conn, game):
    """Plain-text block the organizer can copy/paste into an email.

    Each player is listed on its own line; all email addresses are combined into
    a single comma-separated line so the organizer can paste them straight into
    the To/Bcc field.
    """
    light = team_roster(conn, game["id"], "light")
    dark = team_roster(conn, game["id"], "dark")

    def block(team, roster):
        header = f"{team} ({len(roster)}):"
        if not roster:
            return f"{header}\n(none yet)"
        names = "\n".join(p["name"] for p in roster)
        return f"{header}\n{names}"

    all_emails = ", ".join(p["email"] for p in (light + dark))

    return (
        f"Pick-up basketball — {game_label(game)}\n\n"
        f"{block('LIGHT', light)}\n\n"
        f"{block('DARK', dark)}\n\n"
        f"Light team: wear a light shirt. Dark team: wear a dark shirt. "
        f"See you on the court!\n\n"
        f"All emails: {all_emails}"
    )
