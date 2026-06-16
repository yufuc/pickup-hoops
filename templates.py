"""Server-rendered HTML. Plain forms + redirects, plus drag-and-drop on the
team page (vanilla JS persisting via fetch)."""
from html import escape

from services import game_label

CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, system-ui, sans-serif; max-width: 820px;
       margin: 0 auto; padding: 1.25rem; color: #1a1a1a; background: #fafafa; }
h1 { font-size: 1.5rem; } h2 { font-size: 1.15rem; margin-top: 1.5rem; }
a { color: #1565c0; }
.navbar { display: flex; gap: .5rem; flex-wrap: wrap; margin: 0 0 1rem;
          padding-bottom: .9rem; border-bottom: 1px solid #e3e3e3; }
.navbtn { text-decoration: none; padding: .4rem .8rem; border-radius: 8px;
          border: 1px solid #ccc; background: #fff; color: #1a1a1a; font-size: .9rem; }
.navbtn:hover { background: #f0f0f0; }
.card { background: #fff; border: 1px solid #e3e3e3; border-radius: 10px;
        padding: 1rem 1.25rem; margin: 1rem 0; }
.muted { color: #777; font-size: .9rem; }
button { font: inherit; padding: .5rem .9rem; border-radius: 8px; border: 1px solid #ccc;
         background: #fff; cursor: pointer; }
button.primary { background: #1565c0; color: #fff; border-color: #1565c0; }
button.in.active { background: #2e7d32; color: #fff; border-color: #2e7d32; }
button.out.active { background: #c62828; color: #fff; border-color: #c62828; }
.pill { display: inline-block; padding: .15rem .55rem; border-radius: 999px; font-size: .8rem; }
.pill.in { background: #e8f5e9; color: #2e7d32; } .pill.out { background: #ffebee; color: #c62828; }
.pill.locked { background: #ede7f6; color: #5e35b1; } .pill.sent { background: #fff3e0; color: #e65100; }
table { width: 100%; border-collapse: collapse; }
td, th { text-align: left; padding: .5rem; border-bottom: 1px solid #eee; vertical-align: middle; }
form.inline { display: inline; }
input, select { font: inherit; padding: .45rem; border-radius: 8px; border: 1px solid #ccc; }
.row { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; }
.datebanner { background: #e3f2fd; border: 1px solid #90caf9; border-radius: 10px;
              padding: 1.1rem 1.4rem; font-size: 1.25rem; }
.datebanner .gamedate { display: block; font-size: 1.9rem; font-weight: 700;
                        line-height: 1.2; margin-top: .35rem; color: #0d47a1; }
.statcard { display: flex; align-items: baseline; gap: .6rem; }
.statcard .big { font-size: 2.6rem; font-weight: 800; color: #2e7d32; line-height: 1; }
.statcard .sub { color: #777; font-size: .95rem; }
/* drag-and-drop teams */
.teamcol { display: flex; gap: 1rem; flex-wrap: wrap; }
.dropzone { flex: 1; min-width: 200px; border-radius: 10px; padding: .75rem; min-height: 120px;
            border: 2px dashed transparent; transition: border-color .1s, background .1s; }
.dropzone.bench { background: #f1f3f4; border-color: #d0d0d0; }
.dropzone.light { background: #fffde7; border-color: #fff59d; }
.dropzone.dark  { background: #263238; color: #eceff1; border-color: #455a64; }
.dropzone.over  { border-color: #1565c0; background: #e3f2fd; }
.dropzone.dark.over { background: #37474f; }
.zonehead { font-weight: 700; margin-bottom: .5rem; display: flex; justify-content: space-between; }
.chips { display: flex; flex-direction: column; gap: .4rem; min-height: 40px; }
.chip { background: #fff; color: #1a1a1a; border: 1px solid #ccc; border-radius: 8px;
        padding: .45rem .65rem; cursor: grab; user-select: none; box-shadow: 0 1px 2px rgba(0,0,0,.06); }
.chip:active { cursor: grabbing; }
.chip.dragging { opacity: .4; }
.chip.static { cursor: default; box-shadow: none; }
.hint { font-size: .85rem; color: #777; margin: .25rem 0 1rem; }
.copybox { width: 100%; min-height: 180px; padding: .6rem; border-radius: 8px;
           border: 1px solid #ccc; font-family: ui-monospace, Menlo, monospace; font-size: .85rem; }
"""


def navbar(links):
    if not links:
        return ""
    items = "".join(f"<a class='navbtn' href='{href}'>{escape(label)}</a>" for label, href in links)
    return f"<div class='navbar'>{items}</div>"


def page(title, body, nav_links=None):
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{CSS}</style></head>"
        f"<body>{navbar(nav_links)}{body}</body></html>"
    )


def _status_pill(status):
    if status == "in":
        return "<span class='pill in'>IN</span>"
    if status == "out":
        return "<span class='pill out'>OUT</span>"
    return "<span class='muted'>— no response</span>"


# ---- landing: shared availability board ----------------------------------
def landing(game, players_with_status, org_token):
    nav = [("🏀 Home", "/")]
    if org_token:
        nav.append(("Organizer dashboard", f"/admin/{org_token}"))

    if game is None:
        banner = "<div class='datebanner'>No game scheduled yet. Check back soon!</div>"
        headcount = ""
        rows = ""
        for p, _ in players_with_status:
            rows += f"<tr><td>{escape(p['name'])}{' ⭐' if p['is_organizer'] else ''}</td><td class='muted'>—</td><td></td></tr>"
    else:
        banner = (
            f"<div class='datebanner'>🗓️ Mark your availability for"
            f"<span class='gamedate'>{escape(game_label(game))}</span></div>"
        )
        in_count = sum(1 for _, s in players_with_status if s == "in")
        out_count = sum(1 for _, s in players_with_status if s == "out")
        no_resp = len(players_with_status) - in_count - out_count
        headcount = (
            f"<div class='card statcard'>"
            f"<span class='big'>{in_count}</span>"
            f"<span class='sub'>player{'' if in_count == 1 else 's'} in"
            f" &nbsp;·&nbsp; {out_count} out &nbsp;·&nbsp; {no_resp} no response</span>"
            f"</div>"
        )
        rows = ""
        for p, status in players_with_status:
            in_active = " active" if status == "in" else ""
            out_active = " active" if status == "out" else ""
            buttons = (
                f"<form method='post' action='/p/{p['token']}/availability' class='inline'>"
                f"<input type='hidden' name='game_id' value='{game['id']}'>"
                f"<input type='hidden' name='return_to' value='/'>"
                f"<button class='in{in_active}' name='status' value='in'>In</button> "
                f"<button class='out{out_active}' name='status' value='out'>Out</button>"
                f"</form>"
            )
            rows += (
                f"<tr><td>{escape(p['name'])}{' ⭐' if p['is_organizer'] else ''}</td>"
                f"<td>{_status_pill(status)}</td><td>{buttons}</td></tr>"
            )

    body = (
        "<h1>🏀 Pick-up Hoops</h1>"
        f"{banner}"
        f"{headcount}"
        "<div class='card'><h2 style='margin-top:0'>Who's playing?</h2>"
        "<p class='hint'>Tap <strong>In</strong> or <strong>Out</strong> next to your name. "
        "⭐ = organizer.</p>"
        f"<table><tr><th>Player</th><th>Status</th><th>Availability</th></tr>{rows}</table></div>"
    )
    return page("Pick-up Hoops", body, nav)


# ---- player's own page (magic link) --------------------------------------
def player_home(player, game, status, my_team, locked):
    nav = [("🏀 Home", "/")]
    if game is None:
        inner = "<div class='card'>No game scheduled yet. Check back soon!</div>"
    else:
        cur = _status_pill(status)
        in_active = " active" if status == "in" else ""
        out_active = " active" if status == "out" else ""
        toggle = (
            f"<form method='post' action='/p/{player['token']}/availability' class='inline'>"
            f"<input type='hidden' name='game_id' value='{game['id']}'>"
            f"<button class='in{in_active}' name='status' value='in'>I'm IN</button> "
            f"<button class='out{out_active}' name='status' value='out'>I'm OUT</button></form>"
        )
        team_block = ""
        if locked and my_team:
            team_block = (
                f"<div class='card dropzone {my_team}'><strong>Your team: {my_team.upper()}</strong>"
                f"<br>Wear a {my_team} shirt.</div>"
            )
        elif locked and not my_team:
            team_block = "<div class='card muted'>Teams are set but you're not assigned (marked out?).</div>"
        inner = (
            f"<div class='card'><h2 style='margin-top:0'>{escape(game_label(game))}</h2>"
            f"<p>Your status: {cur}</p>{toggle}</div>{team_block}"
        )
    body = f"<h1>🏀 Hi, {escape(player['name'])}</h1>{inner}"
    return page("Your hoops status", body, nav)


# ---- organizer dashboard --------------------------------------------------
def admin_dashboard(org, players, games):
    token = org["token"]
    nav = [("🏀 Home", "/")]
    game_rows = ""
    for g in games:
        flags = "<span class='pill locked'>LOCKED</span>" if g["teams_locked"] else ""
        game_rows += f"""
        <tr>
          <td><a href='/admin/{token}/games/{g['id']}'>open</a> {flags}</td>
          <td>
            <form method='post' action='/admin/{token}/games/{g['id']}/edit' class='row'>
              <input type='date' name='game_date' value='{g['game_date']}' required>
              <input type='time' name='start_time' value='{g['start_time']}' required>
              <button>Save</button>
            </form>
          </td>
          <td>
            <form method='post' action='/admin/{token}/games/{g['id']}/delete' class='inline'
                  onsubmit="return confirm('Delete this game and its availability/teams?')">
              <button class='danger'>Delete</button>
            </form>
          </td>
        </tr>"""
    if not game_rows:
        game_rows = "<tr><td class='muted' colspan='3'>No games yet.</td></tr>"

    player_rows = ""
    for p in players:
        checked = "checked" if p["is_organizer"] else ""
        player_rows += f"""
        <tr>
          <td>
            <form method='post' action='/admin/{token}/players/{p['id']}/edit' class='row'>
              <input name='name' value="{escape(p['name'], quote=True)}" required>
              <input type='email' name='email' value="{escape(p['email'], quote=True)}" required>
              <label class='muted'><input type='checkbox' name='is_organizer' value='1' {checked}> org</label>
              <button>Save</button>
            </form>
          </td>
          <td>
            <form method='post' action='/admin/{token}/players/{p['id']}/delete' class='inline'
                  onsubmit="return confirm('Delete {escape(p['name'], quote=True)}?')">
              <button class='danger'>Delete</button>
            </form>
          </td>
        </tr>"""

    body = f"""
    <h1>🏀 Organizer · {escape(org['name'])}</h1>
    <div class='card'><h2 style='margin-top:0'>Games</h2>
      <table><tr><th></th><th>Date &amp; time</th><th></th></tr>{game_rows}</table>
      <h2>Schedule a game</h2>
      <form method='post' action='/admin/{token}/games' class='row'>
        <label>Date <input type='date' name='game_date' required></label>
        <label>Time <input type='time' name='start_time' value='07:00' required></label>
        <button class='primary'>Add game</button>
      </form>
      <p class='hint'>Usually Friday; pick Thursday's date for the rare Thursday game.</p>
    </div>

    <div class='card'><h2 style='margin-top:0'>Roster</h2>
      <table><tr><th>Player</th><th></th></tr>{player_rows}</table>
      <h2>Add player</h2>
      <form method='post' action='/admin/{token}/players' class='row'>
        <input name='name' placeholder='Name' required>
        <input name='email' type='email' placeholder='email@example.com' required>
        <label class='muted'><input type='checkbox' name='is_organizer' value='1'> organizer</label>
        <button class='primary'>Add player</button>
      </form>
    </div>
    """
    return page("Organizer", body, nav)


# ---- team assignment with drag-and-drop -----------------------------------
def _chip(player, draggable):
    drag = "draggable='true'" if draggable else ""
    cls = "chip" if draggable else "chip static"
    return f"<div class='{cls}' {drag} data-player='{player['id']}'>{escape(player['name'])}</div>"


def _zone(team, title, members, draggable):
    chips = "".join(_chip(p, draggable) for p in members)
    return (
        f"<div class='dropzone {team}' data-team='{team}'>"
        f"<div class='zonehead'><span>{title}</span><span class='count'>{len(members)}</span></div>"
        f"<div class='chips'>{chips}</div></div>"
    )


def admin_game(org, game, unassigned, light, dark, not_playing, summary):
    token = org["token"]
    locked = game["teams_locked"]
    nav = [("🏀 Home", "/"), ("Dashboard", f"/admin/{token}")]

    in_count = len(unassigned) + len(light) + len(dark)
    draggable = not locked

    zones = (
        f"<div class='teamcol'>"
        + (_zone("bench", "Unassigned", unassigned, draggable) if draggable else "")
        + _zone("light", "LIGHT", light, draggable)
        + _zone("dark", "DARK", dark, draggable)
        + "</div>"
    )

    hint = (
        "<p class='hint'>Drag players between <strong>Unassigned</strong>, <strong>Light</strong>, "
        "and <strong>Dark</strong>. Changes save automatically.</p>"
        if draggable else ""
    )

    if locked:
        actions = (
            f"<form method='post' action='/admin/{token}/games/{game['id']}/unlock' class='inline'>"
            f"<button>Unlock to edit</button></form>"
        )
    else:
        actions = (
            f"<form method='post' action='/admin/{token}/games/{game['id']}/suggest' class='inline'>"
            f"<button class='primary'>Suggest teams (random split)</button></form> "
            f"<form method='post' action='/admin/{token}/games/{game['id']}/lock' class='inline'>"
            f"<button>Lock teams</button></form>"
        )

    # Copy-paste block: the organizer pastes this into an email they send manually.
    copy_block = ""
    if light or dark:
        note = ("Teams are locked — players can now see their assignment too."
                if locked else
                "Preview — tip: lock teams to freeze them and reveal assignments to players.")
        copy_block = (
            f"<div class='card'><h2 style='margin-top:0'>📋 Copy for email</h2>"
            f"<p class='hint'>{note}</p>"
            f"<textarea id='copybox' readonly class='copybox'>{escape(summary)}</textarea>"
            f"<div style='margin-top:.5rem'><button id='copybtn' class='primary'>Copy to clipboard</button></div></div>"
        )

    out_block = ""
    if not_playing:
        chips = "".join(_chip(p, False) for p in not_playing)
        out_block = (
            f"<div class='card'><h2 style='margin-top:0'>Not playing "
            f"<span class='muted'>({len(not_playing)})</span></h2>"
            f"<div class='chips' style='flex-direction:row;flex-wrap:wrap'>{chips}</div></div>"
        )

    drag_script = ""
    if draggable:
        assign_url = f"/admin/{token}/games/{game['id']}/assign"
        drag_script = f"""
        <script>
        const ASSIGN_URL = {assign_url!r};
        function refreshCounts() {{
          document.querySelectorAll('.dropzone').forEach(z => {{
            z.querySelector('.count').textContent = z.querySelectorAll('.chip').length;
          }});
        }}
        document.querySelectorAll('.chip[draggable=true]').forEach(c => {{
          c.addEventListener('dragstart', e => {{
            e.dataTransfer.setData('text/plain', c.dataset.player);
            c.classList.add('dragging');
          }});
          c.addEventListener('dragend', () => c.classList.remove('dragging'));
        }});
        document.querySelectorAll('.dropzone').forEach(z => {{
          z.addEventListener('dragover', e => {{ e.preventDefault(); z.classList.add('over'); }});
          z.addEventListener('dragleave', () => z.classList.remove('over'));
          z.addEventListener('drop', e => {{
            e.preventDefault(); z.classList.remove('over');
            const pid = e.dataTransfer.getData('text/plain');
            const chip = document.querySelector('.chip[data-player="' + pid + '"]');
            if (!chip) return;
            z.querySelector('.chips').appendChild(chip);
            refreshCounts();
            const body = 'ajax=1&player_id=' + encodeURIComponent(pid) + '&team=' + encodeURIComponent(z.dataset.team);
            fetch(ASSIGN_URL, {{ method: 'POST',
              headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }}, body }})
              .catch(() => alert('Could not save that move — refresh and try again.'));
          }});
        }});
        </script>
        """

    copy_script = """
    <script>
    (function () {
      const btn = document.getElementById('copybtn');
      const box = document.getElementById('copybox');
      if (!btn || !box) return;
      btn.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(box.value); }
        catch (e) { box.focus(); box.select(); document.execCommand('copy'); }
        const orig = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = orig; }, 1500);
      });
    })();
    </script>
    """ if copy_block else ""

    body = f"""
    <h1>{escape(game_label(game))}</h1>
    <p>{in_count} player(s) IN
       {"· <span class='pill locked'>LOCKED</span>" if locked else ""}</p>

    <div class='card'><h2 style='margin-top:0'>Teams</h2>
      {hint}{zones}
      <div style='margin-top:1rem'>{actions}</div>
    </div>
    {copy_block}
    {out_block}
    {drag_script}{copy_script}
    """
    return page(game_label(game), body, nav)


def simple(title, message, back=None):
    nav = [("🏀 Home", "/")]
    if back:
        nav.append(("Back", back))
    return page(title, f"<h1>{escape(title)}</h1><div class='card'>{escape(message)}</div>", nav)
