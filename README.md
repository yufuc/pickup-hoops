# 🏀 Pick-up Hoops — weekly game coordinator (prototype)

Coordinates a weekly pick-up basketball game: players mark themselves **in/out**,
the organizer splits the "in" players into **light vs. dark** teams, and the app
**auto-emails each team ~48h before tip-off**.

This is a **local prototype** built with the Python standard library only —
no installs, no build step. Email sending is **stubbed** (printed to the console
and saved to an in-app outbox); swap in a real provider when ready.

## Run

```bash
cd pickup-hoops
python3 seed.py     # create sample players + the upcoming Friday game (prints magic links)
python3 app.py      # start the server at http://localhost:8000
```

Open <http://localhost:8000> for a dev index of everyone's magic links.

## How it works

- **Players** open their personal magic link (`/p/<token>`) and tap **I'm IN / I'm OUT**
  for the upcoming game. Once teams are locked they can see their team.
- **The organizer** opens `/admin/<token>` to:
  - schedule a game (pick any date — usually Friday, occasionally Thursday),
  - add players to the roster,
  - **Suggest teams** (random balanced split of the "in" players), then tweak any
    player's team via the dropdowns,
  - **Lock teams**, then either let emails auto-send or **Send team emails now**.
- **The scheduler** (`scheduler.py`) runs in a background thread, checking every 30s.
  When a *locked, not-yet-notified* game is within **48 hours** of tip-off, it emails
  each player their team assignment. Sending at the 48h mark keeps everyone inside the
  requested 36–48h window even if the server was briefly down.

## Going to production (next steps)

- **Email:** replace the body of `send_email` in `emailer.py` with a Resend/SendGrid/
  Postmark/SMTP call. Nothing else changes.
- **Hosting:** the scheduler is an in-process thread, fine for a single always-on
  machine. For serverless hosting, move `due_for_notification` → `notify_game` behind a
  real cron (e.g. a daily/hourly job).
- **Auth:** magic-link tokens are unguessable but never expire and live in the URL —
  fine for a casual group; add expiry/rotation if you need more.

## Files

| File | Purpose |
|------|---------|
| `app.py` | HTTP server + routing |
| `db.py` | SQLite schema + connection helper |
| `services.py` | Team suggestion, notification, scheduling-window logic |
| `emailer.py` | Email delivery (stubbed) |
| `scheduler.py` | Background notify thread |
| `templates.py` | Server-rendered HTML |
| `seed.py` | Sample data |
