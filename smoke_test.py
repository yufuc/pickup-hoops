"""End-to-end smoke test driving the running server over HTTP."""
import urllib.parse, urllib.request
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
org = c.execute("SELECT token FROM players WHERE is_organizer=1").fetchone()["token"]
players = c.execute("SELECT id, name, token FROM players WHERE is_organizer=0 ORDER BY name").fetchall()
gid = c.execute("SELECT id FROM games ORDER BY id LIMIT 1").fetchone()["id"]

# 1. six IN, one OUT
for p in players[:6]:
    post(f"/p/{p['token']}/availability", game_id=gid, status="in")
robin = players[6]
post(f"/p/{robin['token']}/availability", game_id=gid, status="out")
ins = services.in_players(db.get_conn(), gid)
print(f"1. availability: {len(ins)} IN ->", [p["name"] for p in ins])

# 2. suggest teams
post(f"/admin/{org}/games/{gid}/suggest")
c2 = db.get_conn()
light = [p["name"] for p in services.team_roster(c2, gid, "light")]
dark = [p["name"] for p in services.team_roster(c2, gid, "dark")]
print(f"2. suggested  LIGHT={light}  DARK={dark}  (balanced={abs(len(light)-len(dark))<=1})")

# 3. reassign first light player to dark, verify it moved
mover = services.team_roster(db.get_conn(), gid, "light")[0]
post(f"/admin/{org}/games/{gid}/assign", player_id=mover["id"], team="dark")
c3 = db.get_conn()
print(f"3. moved {mover['name']} -> dark; now LIGHT={len(services.team_roster(c3,gid,'light'))} DARK={len(services.team_roster(c3,gid,'dark'))}")

# 4. player view before lock should NOT reveal team
status, html = get(f"/p/{players[0]['token']}")
print("4. player sees team before lock:", ("Your team" in html))

# 5. lock + notify
post(f"/admin/{org}/games/{gid}/lock")
print("5. notify ->", post(f"/admin/{org}/games/{gid}/notify"))

# 6. emails recorded (should equal number of assigned players = 6)
emails = db.get_conn().execute("SELECT recipient, subject FROM emails ORDER BY id").fetchall()
print(f"6. emails sent: {len(emails)}")
for e in emails:
    print("   ", e["recipient"], "|", e["subject"])

# 7. double-notify must be a no-op (already notified)
post(f"/admin/{org}/games/{gid}/notify")
again = db.get_conn().execute("SELECT COUNT(*) n FROM emails").fetchone()["n"]
print(f"7. re-notify no-op: total emails still {again}")

# 8. player view after notify reveals team
status, html = get(f"/p/{players[0]['token']}")
print("8. player sees team after notify:", ("Your team" in html))

# 9. authorization: player token cannot hit admin
import urllib.error
try:
    get(f"/admin/{players[0]['token']}")
    print("9. player->admin: NOT blocked (BUG)")
except urllib.error.HTTPError as e:
    print(f"9. player->admin blocked with {e.code}")
