# resources/read.py
import sqlite3
import time
from pathlib import Path
from typing import List, Dict

BASE_DIR = Path(__file__).resolve().parent
SENSOR_DB_PATH = BASE_DIR / "sensor.db"
SETTINGS_DB_PATH = BASE_DIR / "settings.db"


# ---------- Sensor DB (unchanged) ----------

def _connect_sensor() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SENSOR_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_rows(table: str, min_seconds_back: int, max_rows: int) -> List[Dict]:
    now = int(time.time())
    cutoff = now - min_seconds_back

    conn = _connect_sensor()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {table}
            WHERE ts >= ?
            ORDER BY ts ASC
            LIMIT ?
            """,
            (cutoff, max_rows),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def recent_dht11(min_seconds_back: int = 3600, max_rows: int = 2000) -> List[Dict]:
    return _fetch_rows("dht11_readings", min_seconds_back, max_rows)


def recent_mq2(min_seconds_back: int = 3600, max_rows: int = 2000) -> List[Dict]:
    return _fetch_rows("mq2_readings", min_seconds_back, max_rows)


def recent_mq135(min_seconds_back: int = 3600, max_rows: int = 2000) -> List[Dict]:
    return _fetch_rows("mq135_readings", min_seconds_back, max_rows)


def recent_dsm501a(min_seconds_back: int = 3600, max_rows: int = 2000) -> List[Dict]:
    return _fetch_rows("dsm501a_readings", min_seconds_back, max_rows)


# ---------- Settings DB ----------

def get_latest_settings() -> Dict | None:
    """
    Return the latest settings row from settings.db, or None if the
    DB/table is not ready or empty.
    """
    conn = sqlite3.connect(str(SETTINGS_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT email, notifications, forecast_duration, refresh_rate, ts
            FROM settings
            ORDER BY ts DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        # e.g. "no such table: settings"
        return None
    finally:
        conn.close()
