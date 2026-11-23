from backend.database import get_db_connection


def init():
    conn = get_db_connection()
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS user_prefs ("
            " user_id INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,"
            " PRIMARY KEY (user_id, key))"
        )
        conn.commit()
    finally:
        conn.close()


def get_bool(user_id, key, default=False):
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT value FROM user_prefs WHERE user_id = ? AND key = ?", (user_id, key)
        ).fetchone()
        return default if row is None else row["value"] == "1"
    finally:
        conn.close()


def set_bool(user_id, key, value):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO user_prefs (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user_id, key, "1" if value else "0"),
        )
        conn.commit()
    finally:
        conn.close()