"""End-to-end smoke test driving the running server over HTTP."""
import urllib.parse, urllib.request, urllib.error
import db, services

BASE = "http://localhost:8000"


def post(path, **fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return r.status


def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return r.status, r.read().decode()


c = db.get_conn()
# Clean slate so prior interactive clicking doesn't skew the assertions.
c.execute("DELETE FROM availability"); c.execute("DELETE FROM assignments")
c.execute("UPDATE games SET teams_locked = 0"); c.commit()

org = c.execute("SELECT token FROM players WHERE is_organizer=1").fetchone()["token"]
players = c.execute("SELECT id, name, token FROM players WHERE is_organizer=0 ORDER BY name").fetchall()
# Target the same game the app considers "upcoming" (earliest future game).
gid = c.execute(
    "SELECT id FROM games WHERE game_date >= date('now') ORDER BY game_date, start_time LIMIT 1"
).fetchone()["id"]

# 1. six IN, one OUT
for p in players[:6]:
    post(f"/p/{p['token']}/availability", game_id=gid, status="in")
post(f"/p/{players[6]['token']}/availability", game_id=gid, status="out")
ins = services.in_players(db.get_conn(), gid)
print(f"1. availability: {len(ins)} IN ->", [p["name"] for p in ins])

# 2. suggest teams
post(f"/admin/{org}/games/{gid}/suggest")
c2 = db.get_conn()
light = [p["name"] for p in services.team_roster(c2, gid, "light")]
dark = [p["name"] for p in services.team_roster(c2, gid, "dark")]
print(f"2. suggested  LIGHT={light}  DARK={dark}  (balanced={abs(len(light)-len(dark))<=1})")

# 3. reassign first light player to dark
mover = services.team_roster(db.get_conn(), gid, "light")[0]
post(f"/admin/{org}/games/{gid}/assign", player_id=mover["id"], team="dark")
c3 = db.get_conn()
print(f"3. moved {mover['name']} -> dark; now LIGHT={len(services.team_roster(c3,gid,'light'))} DARK={len(services.team_roster(c3,gid,'dark'))}")

# 4. player does NOT see team before lock
_, html = get(f"/p/{players[0]['token']}")
print("4. player sees team before lock:", ("Your team" in html))

# 5. copy-paste block present on admin page, with names + emails
_, gp = get(f"/admin/{org}/games/{gid}")
game = db.get_conn().execute("SELECT * FROM games WHERE id=?", (gid,)).fetchone()
summary = services.team_summary_text(db.get_conn(), game)
print("5a. copy box on admin page :", ("id='copybox'" in gp and "Copy to clipboard" in gp))
print("5b. summary has both teams :", ("LIGHT" in summary and "DARK" in summary))
print("5c. summary includes emails:", ("@example.com" in summary))

# 6. lock -> player now sees team
post(f"/admin/{org}/games/{gid}/lock")
_, html = get(f"/p/{players[0]['token']}")
print("6. player sees team after lock:", ("Your team" in html))

# 7. no email machinery remains
_, dash = get(f"/admin/{org}")
print("7. no 'Outbox'/'emails sent' in UI:", ("Outbox" not in dash and "EMAILS SENT" not in dash))

# 8. unlock works
post(f"/admin/{org}/games/{gid}/unlock")
relocked = db.get_conn().execute("SELECT teams_locked FROM games WHERE id=?", (gid,)).fetchone()["teams_locked"]
print("8. unlock works:", relocked == 0)

# 9. authorization: player token cannot hit admin
try:
    get(f"/admin/{players[0]['token']}")
    print("9. player->admin: NOT blocked (BUG)")
except urllib.error.HTTPError as e:
    print(f"9. player->admin blocked with {e.code}")
