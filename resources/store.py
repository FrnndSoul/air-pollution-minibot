# resources/store.py
import sqlite3
import time
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
SENSOR_DB_PATH = BASE_DIR / "sensor.db"


def _connect() -> sqlite3.Connection:
    SENSOR_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SENSOR_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables() -> None:
    """
    Create tables for each sensor if they do not exist.

    We do not touch any old tables that might already be in the database.
    """
    conn = _connect()
    cur = conn.cursor()

    # DHT11: temperature and humidity
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dht11_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            temperature_c REAL,
            humidity_percent REAL
        )
        """
    )

    # MQ2: gas sensor on ADS1115 A1
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mq2_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            raw INTEGER,
            voltage REAL
        )
        """
    )

    # MQ135: air quality sensor on ADS1115 A0
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mq135_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            raw INTEGER,
            voltage REAL
        )
        """
    )

    # DSM501A: dust sensor on GPIO24
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dsm501a_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            low_pulse_ms REAL,
            ratio REAL,
            concentration_ug_m3 REAL
        )
        """
    )

    conn.commit()
    conn.close()


def insert_dht11(
    temperature_c: Optional[float],
    humidity_percent: Optional[float],
    ts: Optional[int] = None,
) -> None:
    ensure_tables()
    if ts is None:
        ts = int(time.time())

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dht11_readings (ts, temperature_c, humidity_percent)
            VALUES (?, ?, ?)
            """,
            (ts, temperature_c, humidity_percent),
        )
        conn.commit()
    finally:
        conn.close()


def insert_mq2(
    raw: Optional[int],
    voltage: Optional[float],
    ts: Optional[int] = None,
) -> None:
    ensure_tables()
    if ts is None:
        ts = int(time.time())

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mq2_readings (ts, raw, voltage)
            VALUES (?, ?, ?)
            """,
            (ts, raw, voltage),
        )
        conn.commit()
    finally:
        conn.close()


def insert_mq135(
    raw: Optional[int],
    voltage: Optional[float],
    ts: Optional[int] = None,
) -> None:
    ensure_tables()
    if ts is None:
        ts = int(time.time())

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO mq135_readings (ts, raw, voltage)
            VALUES (?, ?, ?)
            """,
            (ts, raw, voltage),
        )
        conn.commit()
    finally:
        conn.close()


def insert_dsm501a(
    low_pulse_ms: Optional[float],
    ratio: Optional[float],
    concentration_ug_m3: Optional[float],
    ts: Optional[int] = None,
) -> None:
    ensure_tables()
    if ts is None:
        ts = int(time.time())

    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dsm501a_readings (ts, low_pulse_ms, ratio, concentration_ug_m3)
            VALUES (?, ?, ?, ?)
            """,
            (ts, low_pulse_ms, ratio, concentration_ug_m3),
        )
        conn.commit()
    finally:
        conn.close()
