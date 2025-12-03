# resources/settings.py
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "settings.db")


def init_db() -> None:
    """Create settings DB/table if they do not exist."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            notifications INTEGER,
            forecast_duration INTEGER,
            refresh_rate INTEGER,
            ts INTEGER DEFAULT (strftime('%s','now'))
        )
        """
    )
    conn.commit()
    conn.close()


def save_settings(email, notifications, forecast_duration, refresh_rate) -> None:
    """
    Insert a new settings row.

    notifications is stored as 0/1, everything else as given (or NULL).
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_settings (email, notifications, forecast_duration, refresh_rate)
        VALUES (?, ?, ?, ?)
        """,
        (
            email,
            1 if notifications else 0,
            int(forecast_duration) if forecast_duration is not None else None,
            int(refresh_rate) if refresh_rate is not None else None,
        ),
    )
    conn.commit()
    conn.close()


def get_latest_settings():
    """
    Return the most recent settings row as a dict or None if no rows exist.

    Example:
        {
            "email": "user@example.com",
            "notifications": True,
            "forecast_duration": 60,
            "refresh_rate": 10,
            "ts": 1735800000
        }
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT email, notifications, forecast_duration, refresh_rate, ts
        FROM user_settings
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    conn.close()

    if row is None:
        return None

    return {
        "email": row["email"],
        "notifications": bool(row["notifications"]),
        "forecast_duration": row["forecast_duration"],
        "refresh_rate": row["refresh_rate"],
        "ts": row["ts"],
    }
