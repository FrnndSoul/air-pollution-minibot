# resources/store.py
import sqlite3
import time
from pathlib import Path
from typing import Optional
import io

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

def ensure_dashboard_table() -> None:
    """
    Create the combined dashboard_readings table if it does not exist.
    """
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS dashboard_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            aqi REAL,
            pm25 REAL,
            pm10 REAL,
            temp REAL,
            humidity REAL,
            toxic REAL,
            flammable REAL,
            smoke REAL,
            voc REAL
        )
        """
    )

    conn.commit()
    conn.close()

def insert_dashboard_reading(metrics: dict, ts: Optional[int] = None) -> None:
    """
    Insert one combined dashboard row using computed metrics.

    metrics is the dict returned by live_aqi.compute_live_metrics()
    or equivalent. If ts is not given, current unix time is used.
    """
    if ts is None:
        ts = int(time.time())

    try:
        conn = _connect()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO dashboard_readings (
                ts,
                aqi,
                pm25,
                pm10,
                temp,
                humidity,
                toxic,
                flammable,
                smoke,
                voc
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                metrics.get("aqi"),
                metrics.get("pm2_5_ug_m3"),
                metrics.get("pm10_ug_m3"),
                metrics.get("temperature_c"),
                metrics.get("humidity_percent"),
                metrics.get("toxic_index"),
                metrics.get("flammable_index"),
                metrics.get("smoke_index"),
                metrics.get("voc_index"),
            ),
        )
        conn.commit()
    except Exception as e:
        print("Error inserting into dashboard_readings:", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
