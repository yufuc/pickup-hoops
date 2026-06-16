"""Background thread that auto-sends team emails inside the notify window."""
import threading
import time
import traceback

from db import get_conn
from services import due_for_notification, notify_game, game_label

CHECK_INTERVAL_SECONDS = 30


def _loop():
    while True:
        try:
            conn = get_conn()
            for game in due_for_notification(conn):
                count = notify_game(conn, game["id"])
                if count:
                    print(f"[scheduler] sent {count} emails for game {game['id']} ({game_label(game)})", flush=True)
            conn.close()
        except Exception:
            traceback.print_exc()
        time.sleep(CHECK_INTERVAL_SECONDS)


def start():
    t = threading.Thread(target=_loop, name="notify-scheduler", daemon=True)
    t.start()
    print(f"[scheduler] running (checks every {CHECK_INTERVAL_SECONDS}s)", flush=True)
    return t
