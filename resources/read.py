# resources/read.py
import sqlite3
import time
from pathlib import Path
from typing import List, Dict
import csv
from .store import _connect
import io

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

def fetch_range(table: str, start_ts: int, end_ts: int):
    conn = _connect_sensor()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM {table}
            WHERE ts BETWEEN ? AND ?
            ORDER BY ts ASC
            """,
            (start_ts, end_ts)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
def export_dashboard_history(fmt: str = "csv"):
    """
    Build a CSV or XLSX export of the dashboard_readings table.

    Returns: (content_bytes_or_str, content_type, filename)
    """
    fmt = (fmt or "csv").lower()
    conn = _connect()
    cur = conn.cursor()

    try:
        cur.execute(
            """
            SELECT ts, aqi, pm25, pm10, temp, humidity, toxic, flammable, smoke, voc
            FROM dashboard_readings
            ORDER BY ts
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    t = int(time.time())
    filename = f"dashboard_history_{t}.{fmt}"

    headers = [
        "Time",
        "AQI",
        "PM2.5 (µg/m³)",
        "PM10 (µg/m³)",
        "Temperature (°C)",
        "Humidity (%)",
        "Toxic index",
        "Flammable index",
        "Smoke index",
        "VOC index",
    ]

    def fmt_num(v, decimals=3):
        if v is None:
            return ""
        try:
            return f"{float(v):.{decimals}f}"
        except Exception:
            return v

    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(headers)

        for row in rows:
            ts, aqi, pm25, pm10, temp, humidity, toxic, flammable, smoke, voc = row
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or 0))
            writer.writerow([
                time_str,
                fmt_num(aqi, 3),
                fmt_num(pm25, 4),
                fmt_num(pm10, 4),
                fmt_num(temp, 3),
                fmt_num(humidity, 3),
                fmt_num(toxic, 3),
                fmt_num(flammable, 3),
                fmt_num(smoke, 3),
                fmt_num(voc, 3),
            ])

        content = buffer.getvalue()
        content_type = "text/csv"
        return content, content_type, filename

    if fmt == "xlsx":
        try:
            import xlsxwriter
        except ImportError:
            raise ImportError("xlsxwriter not installed. Install with: pip3 install xlsxwriter")

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        ws = workbook.add_worksheet("dashboard")

        for c, h in enumerate(headers):
            ws.write(0, c, h)

        row_idx = 1
        for row in rows:
            ts, aqi, pm25, pm10, temp, humidity, toxic, flammable, smoke, voc = row
            time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or 0))

            ws.write(row_idx, 0, time_str)
            ws.write(row_idx, 1, fmt_num(aqi, 3))
            ws.write(row_idx, 2, fmt_num(pm25, 4))
            ws.write(row_idx, 3, fmt_num(pm10, 4))
            ws.write(row_idx, 4, fmt_num(temp, 3))
            ws.write(row_idx, 5, fmt_num(humidity, 3))
            ws.write(row_idx, 6, fmt_num(toxic, 3))
            ws.write(row_idx, 7, fmt_num(flammable, 3))
            ws.write(row_idx, 8, fmt_num(smoke, 3))
            ws.write(row_idx, 9, fmt_num(voc, 3))

            row_idx += 1

        workbook.close()
        output.seek(0)
        content = output.read()
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return content, content_type, filename

    raise ValueError(f"Unsupported format: {fmt}")
