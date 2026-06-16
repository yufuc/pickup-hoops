"""Pick-up basketball coordinator — local prototype.

Run:  python3 app.py        then open http://localhost:8000
"""
import os
import re
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import db
import templates as T
import services as S

PORT = int(os.environ.get("PORT", 8000))


# ---- small routing helper -------------------------------------------------
ROUTES = []  # (method, compiled_regex, handler_name)
_DB_READY = False  # schema is created lazily on the first request (see _dispatch)


def route(method, pattern):
    def deco(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn))
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    # --- response helpers ---
    def _html(self, html, status=200):
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _no_content(self):
        self.send_response(204)
        self.end_headers()

    def _form(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _query(self):
        qs = urllib.parse.urlparse(self.path).query
        return {k: v[0] for k, v in urllib.parse.parse_qs(qs).items()}

    def _dispatch(self, method):
        global _DB_READY
        if not _DB_READY:
            db.init_db()  # idempotent; runs once per (cold) process
            _DB_READY = True
        path = urllib.parse.urlparse(self.path).path
        # On Vercel all paths are rewritten to this function; if the rewrite
        # target leaks through as the path, recover the original route.
        if path.startswith("/api/index"):
            path = path[len("/api/index"):] or "/"
        for m, rx, fn in ROUTES:
            if m != method:
                continue
            match = rx.match(path)
            if match:
                conn = db.get_conn()
                try:
                    fn(self, conn, *match.groups())
                finally:
                    conn.close()
                return
        self._html(T.simple("Not found", "No such page."), status=404)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def log_message(self, fmt, *args):  # quieter console
        return


# ---- lookups --------------------------------------------------------------
def _player_by_token(conn, token):
    return conn.execute("SELECT * FROM players WHERE token = ?", (token,)).fetchone()


def _organizer_by_token(conn, token):
    p = _player_by_token(conn, token)
    return p if (p and p["is_organizer"]) else None


def _upcoming_game(conn):
    """The next game that hasn't happened yet, else the most recent one."""
    today = date.today().isoformat()  # pass as a param — portable across backends
    return conn.execute(
        "SELECT * FROM games WHERE game_date >= ? ORDER BY game_date, start_time LIMIT 1",
        (today,),
    ).fetchone() or conn.execute(
        "SELECT * FROM games ORDER BY game_date DESC, start_time DESC LIMIT 1"
    ).fetchone()


# ---- routes: public / dev -------------------------------------------------
@route("GET", "/")
def index(h, conn):
    game = _upcoming_game(conn)
    # The organizer dashboard is openly linked from the landing board for
    # everyone (a casual, fully-open model — anyone can manage games/roster).
    org = conn.execute(
        "SELECT token FROM players WHERE is_organizer = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    org_token = org["token"] if org else None
    if game:
        rows = conn.execute(
            """SELECT p.*, a.status AS av
               FROM players p
               LEFT JOIN availability a ON a.player_id = p.id AND a.game_id = ?
               ORDER BY p.is_organizer DESC, p.name""",
            (game["id"],),
        ).fetchall()
        players_with_status = [(r, r["av"]) for r in rows]
    else:
        rows = conn.execute(
            "SELECT * FROM players ORDER BY is_organizer DESC, name"
        ).fetchall()
        players_with_status = [(r, None) for r in rows]
    h._html(T.landing(game, players_with_status, org_token))


def _setup_allowed(conn, given_key):
    """Setup is open when the DB has no organizer yet (first-run bootstrap), or
    when SETUP_KEY is configured and matches. Returns (allowed, key_for_forms)."""
    env_key = os.environ.get("SETUP_KEY")
    if env_key and given_key == env_key:
        return True, env_key
    no_org = conn.execute(
        "SELECT 1 FROM players WHERE is_organizer = 1 LIMIT 1"
    ).fetchone() is None
    return no_org, (env_key or "")


def _organizers(conn):
    return conn.execute(
        "SELECT name, email, token FROM players WHERE is_organizer = 1 ORDER BY id"
    ).fetchall()


@route("GET", r"/setup")
def setup(h, conn):
    """Create / retrieve organizer access (see _setup_allowed for the gate)."""
    allowed, key = _setup_allowed(conn, h._query().get("key", ""))
    if not allowed:
        return h._html(T.simple("Setup", "Setup is not available."), status=404)
    h._html(T.setup_page(_organizers(conn), key))


@route("POST", r"/setup/create")
def setup_create(h, conn):
    form = h._form()
    allowed, key = _setup_allowed(conn, form.get("key", ""))
    if not allowed:
        return h._html(T.simple("Setup", "Setup is not available."), status=404)
    name = form.get("name", "").strip()
    email = form.get("email", "").strip().lower()
    if name and email and not conn.execute(
        "SELECT 1 FROM players WHERE email = ?", (email,)
    ).fetchone():
        conn.execute(
            "INSERT INTO players (name, email, token, is_organizer) VALUES (?, ?, ?, 1)",
            (name, email, db.new_token()),
        )
        conn.commit()
    # Render directly (not redirect) so the new admin link is shown even when
    # creating the very first organizer in open (no-key) mode.
    h._html(T.setup_page(_organizers(conn), key))


# ---- routes: player -------------------------------------------------------
@route("GET", r"/p/([\w-]+)")
def player_home(h, conn, token):
    player = _player_by_token(conn, token)
    if not player:
        return h._html(T.simple("Unknown link", "This link isn't valid."), status=404)
    game = _upcoming_game(conn)
    status = my_team = None
    locked = False
    if game:
        a = conn.execute(
            "SELECT status FROM availability WHERE game_id = ? AND player_id = ?",
            (game["id"], player["id"]),
        ).fetchone()
        status = a["status"] if a else None
        t = conn.execute(
            "SELECT team FROM assignments WHERE game_id = ? AND player_id = ?",
            (game["id"], player["id"]),
        ).fetchone()
        my_team = t["team"] if t else None
        locked = bool(game["teams_locked"])
    h._html(T.player_home(player, game, status, my_team, locked))


@route("POST", r"/p/([\w-]+)/availability")
def set_availability(h, conn, token):
    player = _player_by_token(conn, token)
    if not player:
        return h._html(T.simple("Unknown link", "This link isn't valid."), status=404)
    form = h._form()
    game_id, status = form.get("game_id"), form.get("status")
    if status in ("in", "out") and game_id:
        conn.execute(
            """INSERT INTO availability (game_id, player_id, status) VALUES (?, ?, ?)
               ON CONFLICT(game_id, player_id) DO UPDATE SET status = excluded.status""",
            (game_id, player["id"], status),
        )
        conn.commit()
    # Return to wherever the request came from (landing board or personal page).
    dest = form.get("return_to", "")
    if not (dest.startswith("/") and not dest.startswith("//")):
        dest = f"/p/{token}"
    h._redirect(dest)


# ---- routes: organizer ----------------------------------------------------
def _require_org(h, conn, token):
    org = _organizer_by_token(conn, token)
    if not org:
        h._html(T.simple("Not authorized", "Organizer link required."), status=403)
        return None
    return org


@route("GET", r"/admin/([\w-]+)")
def admin_dashboard(h, conn, token):
    org = _require_org(h, conn, token)
    if not org:
        return
    players = conn.execute("SELECT * FROM players ORDER BY is_organizer DESC, name").fetchall()
    games = conn.execute("SELECT * FROM games ORDER BY game_date DESC, start_time DESC").fetchall()
    h._html(T.admin_dashboard(org, players, games))


@route("POST", r"/admin/([\w-]+)/players")
def add_player(h, conn, token):
    org = _require_org(h, conn, token)
    if not org:
        return
    form = h._form()
    name, email = form.get("name", "").strip(), form.get("email", "").strip().lower()
    is_org = 1 if form.get("is_organizer") else 0
    if name and email:
        try:
            conn.execute(
                "INSERT INTO players (name, email, token, is_organizer) VALUES (?, ?, ?, ?)",
                (name, email, db.new_token(), is_org),
            )
            conn.commit()
        except Exception:
            pass  # duplicate email — ignore for the prototype
    h._redirect(f"/admin/{token}")


@route("POST", r"/admin/([\w-]+)/players/(\d+)/edit")
def edit_player(h, conn, token, player_id):
    if not _require_org(h, conn, token):
        return
    form = h._form()
    name, email = form.get("name", "").strip(), form.get("email", "").strip().lower()
    is_org = 1 if form.get("is_organizer") else 0
    if name and email:
        try:
            conn.execute(
                "UPDATE players SET name = ?, email = ?, is_organizer = ? WHERE id = ?",
                (name, email, is_org, player_id),
            )
            conn.commit()
        except Exception:
            pass  # email collides with another player — ignore for the prototype
    h._redirect(f"/admin/{token}")


@route("POST", r"/admin/([\w-]+)/players/(\d+)/delete")
def delete_player(h, conn, token, player_id):
    org = _require_org(h, conn, token)
    if not org:
        return
    # Don't let the acting organizer delete themselves out of their own session.
    if str(org["id"]) != player_id:
        conn.execute("DELETE FROM players WHERE id = ?", (player_id,))  # cascades availability + assignments
        conn.commit()
    h._redirect(f"/admin/{token}")


@route("POST", r"/admin/([\w-]+)/games")
def add_game(h, conn, token):
    org = _require_org(h, conn, token)
    if not org:
        return
    form = h._form()
    date, time = form.get("game_date"), form.get("start_time", "07:00")
    if date:
        conn.execute(
            "INSERT INTO games (game_date, start_time) VALUES (?, ?)", (date, time)
        )
        conn.commit()
    h._redirect(f"/admin/{token}")


@route("POST", r"/admin/([\w-]+)/games/(\d+)/edit")
def edit_game(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    form = h._form()
    date, time = form.get("game_date"), form.get("start_time", "07:00")
    if date:
        conn.execute(
            "UPDATE games SET game_date = ?, start_time = ? WHERE id = ?",
            (date, time, game_id),
        )
        conn.commit()
    h._redirect(f"/admin/{token}")


@route("POST", r"/admin/([\w-]+)/games/(\d+)/delete")
def delete_game(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    conn.execute("DELETE FROM games WHERE id = ?", (game_id,))  # cascades availability + assignments
    conn.commit()
    h._redirect(f"/admin/{token}")


@route("GET", r"/admin/([\w-]+)/games/(\d+)")
def admin_game(h, conn, token, game_id):
    org = _require_org(h, conn, token)
    if not org:
        return
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not game:
        return h._html(T.simple("Not found", "No such game.", back=f"/admin/{token}"), status=404)
    rows = conn.execute(
        """SELECT p.*, a.status AS av_status, asg.team AS team
           FROM players p
           LEFT JOIN availability a ON a.player_id = p.id AND a.game_id = ?
           LEFT JOIN assignments asg ON asg.player_id = p.id AND asg.game_id = ?
           ORDER BY p.name""",
        (game_id, game_id),
    ).fetchall()
    light = [r for r in rows if r["team"] == "light"]
    dark = [r for r in rows if r["team"] == "dark"]
    unassigned = [r for r in rows if r["av_status"] == "in" and r["team"] is None]
    not_playing = [r for r in rows if r["av_status"] == "out"]
    summary = S.team_summary_text(conn, game)
    h._html(T.admin_game(org, game, unassigned, light, dark, not_playing, summary))


def _locked_guard(h, conn, token, game_id):
    """Return the game row, or None if missing (404 already sent)."""
    game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    if not game:
        h._html(T.simple("Not found", "No such game.", back=f"/admin/{token}"), status=404)
        return None
    return game


@route("POST", r"/admin/([\w-]+)/games/(\d+)/suggest")
def suggest(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    game = _locked_guard(h, conn, token, game_id)
    if game and not game["teams_locked"]:
        S.suggest_teams(conn, game_id)
    h._redirect(f"/admin/{token}/games/{game_id}")


@route("POST", r"/admin/([\w-]+)/games/(\d+)/assign")
def assign(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    game = _locked_guard(h, conn, token, game_id)
    if game is None:
        return  # 404 already sent
    form = h._form()
    if not game["teams_locked"] and form.get("player_id"):
        S.set_assignment(conn, game_id, form["player_id"], form.get("team", "bench"))
    if form.get("ajax"):
        return h._no_content()
    h._redirect(f"/admin/{token}/games/{game_id}")


@route("POST", r"/admin/([\w-]+)/games/(\d+)/lock")
def lock(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    conn.execute("UPDATE games SET teams_locked = 1 WHERE id = ?", (game_id,))
    conn.commit()
    h._redirect(f"/admin/{token}/games/{game_id}")


@route("POST", r"/admin/([\w-]+)/games/(\d+)/unlock")
def unlock(h, conn, token, game_id):
    if not _require_org(h, conn, token):
        return
    conn.execute("UPDATE games SET teams_locked = 0 WHERE id = ?", (game_id,))
    conn.commit()
    h._redirect(f"/admin/{token}/games/{game_id}")


def main():
    db.init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"\n🏀 Pick-up Hoops running at http://localhost:{PORT}\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
