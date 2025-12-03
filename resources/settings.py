import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "settings.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            notifications INTEGER,
            forecast_duration INTEGER,
            refresh_rate INTEGER,
            ts INTEGER DEFAULT (strftime('%s','now'))
        )
    """)
    conn.commit()
    conn.close()

def save_settings(email, notifications, forecast_duration, refresh_rate):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_settings (email, notifications, forecast_duration, refresh_rate)
        VALUES (?, ?, ?, ?)
    """, (email, 1 if notifications else 0, forecast_duration, refresh_rate))
    conn.commit()
    conn.close()
