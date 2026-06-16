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

## Deploying to Vercel

The app runs locally as an always-on process backed by SQLite, **and** as Vercel
serverless functions backed by Postgres — `db.py` picks the backend automatically
based on whether a database URL is present in the environment.

1. **Provision Postgres** (Vercel Postgres, [Neon](https://neon.tech), or Supabase).
   Use the **pooled** connection string (serverless opens many short-lived
   connections).
2. **Import the repo** into Vercel (New Project → import `pickup-hoops`).
3. **Set environment variables** in the Vercel project:

   | Variable | Required | Purpose |
   |----------|----------|---------|
   | `DATABASE_URL` | ✅ | Postgres connection string (or `POSTGRES_URL`) |
   | `ADMIN_EMAIL` | ✅ (first deploy) | Bootstraps the first organizer account |
   | `ADMIN_NAME` | optional | Display name for that organizer |
   | `SETUP_KEY` | ✅ (first deploy) | Unlocks `/setup` to retrieve the admin link |

4. **Deploy.** Then visit `https://<your-app>/setup?key=<SETUP_KEY>` once to get
   your private organizer admin link, and bookmark it.

How it maps to Vercel: `api/index.py` exposes the request handler as `handler`
(invoked per request — no `serve_forever`). `vercel.json` explicitly builds it with
the `@vercel/python` runtime (bundling the root `*.py` modules) and routes every
path to it. `requirements.txt` installs the Postgres driver.

> Prefer the original always-on design? A process host (Render/Railway/Fly) runs
> the local SQLite version nearly unchanged — set the `PORT` env var and a start
> command of `python3 app.py`.

## Notes / next steps

- **Auth:** magic-link tokens are unguessable but never expire and live in the URL —
  fine for a casual group; add expiry/rotation if you need more. The shared landing
  board lets anyone toggle any player's status (by design); the organizer admin link
  is kept off the public page in production.

## Files

| File | Purpose |
|------|---------|
| `app.py` | Request handler + routing (works as a local server and on Vercel) |
| `db.py` | Backend-agnostic storage (Postgres in prod, SQLite locally) |
| `services.py` | Team suggestion + the copy-paste email summary |
| `templates.py` | Server-rendered HTML (incl. drag-and-drop + copy button) |
| `seed.py` | Sample data (local dev) |
| `api/index.py` | Vercel serverless entry point |
| `vercel.json` | Routes all paths to the function |
| `requirements.txt` | Postgres driver (used only when a DB URL is set) |
