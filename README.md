# 🏀 Pick-up Hoops — weekly game coordinator (prototype)

Coordinates a weekly pick-up basketball game: players mark themselves **in/out**,
the organizer splits the "in" players into **light vs. dark** teams, then copies a
ready-made **text block** to paste into an email they send to the players themselves.

This is a **local prototype** built with the Python standard library only —
no installs, no build step.

## Run

```bash
cd pickup-hoops
python3 seed.py     # create sample players + the upcoming Friday game (prints magic links)
python3 app.py      # start the server at http://localhost:8000
```

Open <http://localhost:8000> for a dev index of everyone's magic links.

## How it works

- **Players** mark **In / Out** for the upcoming game — either from the shared landing
  board (a button next to their name) or their personal page (`/p/<token>`). Once teams
  are locked they can see their own team.
- **The organizer** opens `/admin/<token>` to:
  - schedule a game (pick any date — usually Friday, occasionally Thursday),
  - add players to the roster,
  - **Suggest teams** (random balanced split of the "in" players), then **drag** players
    between Unassigned / Light / Dark to tweak,
  - **Lock teams**, then **Copy for email** — a formatted text block (each team's names
    and email addresses) to paste into an email the organizer sends manually.

## Going to production (next steps)

- **Hosting:** runs as a single always-on process with a local SQLite file. A
  process-friendly host (Render/Railway/Fly) runs it nearly unchanged; serverless
  (Vercel) would need a hosted DB + a WSGI refactor.
- **Auth:** magic-link tokens are unguessable but never expire and live in the URL —
  fine for a casual group; add expiry/rotation if you need more.

## Files

| File | Purpose |
|------|---------|
| `app.py` | HTTP server + routing |
| `db.py` | SQLite schema + connection helper |
| `services.py` | Team suggestion + the copy-paste email summary |
| `templates.py` | Server-rendered HTML (incl. drag-and-drop + copy button) |
| `seed.py` | Sample data |
