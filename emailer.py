"""Email delivery — STUBBED for the prototype.

Right now this prints each message to the console and records it in the
`emails` table (viewable at /admin/<token>/outbox). To go live, replace the
body of `send_email` with a call to a real provider (Resend / SendGrid /
Postmark / SMTP via smtplib) — nothing else in the app needs to change.
"""


def send_email(conn, recipient, subject, body, game_id=None):
    banner = "=" * 70
    print(f"\n{banner}\n[EMAIL STUB] -> {recipient}\nSubject: {subject}\n{'-' * 70}\n{body}\n{banner}\n", flush=True)
    conn.execute(
        "INSERT INTO emails (game_id, recipient, subject, body) VALUES (?, ?, ?, ?)",
        (game_id, recipient, subject, body),
    )
    conn.commit()
