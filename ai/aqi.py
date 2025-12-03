# ai/aqi.py
from __future__ import annotations
from typing import Dict, Any, List
import time

from sensors import dht11, dsm501a, mq2, mq135
from resources import read as read_db
from resources import settings as settings_store


# ---------- Helpers for live metrics ----------

def _scaled_index(value: float, good_level: float, bad_level: float) -> float:
    if value is None:
        return 0.0
    if value <= good_level:
        return 0.0
    if value >= bad_level:
        return 500.0
    return 500.0 * (value - good_level) / (bad_level - good_level)


PM25_BREAKPOINTS = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 500.4, 301, 500),
]

PM10_BREAKPOINTS = [
    (0.0, 54.0, 0, 50),
    (55.0, 154.0, 51, 100),
    (155.0, 254.0, 101, 150),
    (255.0, 354.0, 151, 200),
    (355.0, 424.0, 201, 300),
    (425.0, 604.0, 301, 500),
]


def _aqi_from_pm(value: float, breakpoints) -> float:
    if value is None:
        return 0.0
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= value <= c_high:
            return i_low + (i_high - i_low) * (value - c_low) / (c_high - c_low)
    return 500.0


def compute_current_metrics() -> Dict[str, Any]:
    """
    Live AQI style metrics computed directly from sensors.
    Used by the simple endpoints (/api/pm25, /api/pm10, etc).
    Your dashboard live AQI uses sensors/live_aqi.py instead.
    """
    dht = dht11.read()
    mq2_r = mq2.read()
    mq135_r = mq135.read()
    dsm = dsm501a.read()

    ts_now = int(time.time())

    temp = dht.get("temperature_c")
    humid = dht.get("humidity_percent")

    pm2_5 = dsm.get("concentration_ug_m3")
    pm10 = pm2_5 * 1.2 if pm2_5 is not None else None

    mq2_voltage = mq2_r.get("voltage")
    mq135_voltage = mq135_r.get("voltage")

    voc_index = _scaled_index(mq135_voltage or 0.0, good_level=0.3, bad_level=2.5)
    toxic_index = _scaled_index(mq135_voltage or 0.0, good_level=0.6, bad_level=3.0)
    smoke_index = _scaled_index(mq2_voltage or 0.0, good_level=0.3, bad_level=2.5)
    flame_index = _scaled_index(mq2_voltage or 0.0, good_level=0.5, bad_level=3.0)

    pm25_aqi = _aqi_from_pm(pm2_5 or 0.0, PM25_BREAKPOINTS)
    pm10_aqi = _aqi_from_pm(pm10 or 0.0, PM10_BREAKPOINTS)

    combined_aqi = max(pm25_aqi, pm10_aqi, voc_index, toxic_index, smoke_index)

    if combined_aqi <= 50:
        status = "Good"
    elif combined_aqi <= 100:
        status = "Moderate"
    elif combined_aqi <= 150:
        status = "Unhealthy Sensitive"
    elif combined_aqi <= 200:
        status = "Unhealthy"
    elif combined_aqi <= 300:
        status = "Very Unhealthy"
    else:
        status = "Hazardous"

    return {
        "ts": ts_now,
        "temperature_c": temp,
        "humidity_percent": humid,
        "pm2_5_ug_m3": pm2_5,
        "pm10_ug_m3": pm10,
        "toxic_index": toxic_index,
        "flammable_index": flame_index,
        "smoke_index": smoke_index,
        "voc_index": voc_index,
        "pm25_aqi": pm25_aqi,
        "pm10_aqi": pm10_aqi,
        "aqi": combined_aqi,
        "status": status,
        "raw": {
            "dht11": dht,
            "mq2": mq2_r,
            "mq135": mq135_r,
            "dsm501a": dsm,
        },
    }


# ---------- Forecast helpers ----------

def _history_points(max_minutes: int) -> List[Dict[str, Any]]:
    """
    Build a simple AQI time series from DSM501A history.
    Uses only PM for trend forecasting.
    """
    # We read a bit more than the horizon to get a decent trend.
    lookback_seconds = max(600, max_minutes * 60 * 2)

    rows = read_db.recent_dsm501a(
        min_seconds_back=lookback_seconds,
        max_rows=2000,
    )

    points: List[Dict[str, Any]] = []
    for r in rows:
        ts = int(r.get("ts") or 0)
        pm2_5 = r.get("concentration_ug_m3")
        if pm2_5 is None:
            continue
        pm10 = pm2_5 * 1.2

        pm25_aqi = _aqi_from_pm(pm2_5, PM25_BREAKPOINTS)
        pm10_aqi = _aqi_from_pm(pm10, PM10_BREAKPOINTS)
        aqi_val = max(pm25_aqi, pm10_aqi)

        points.append({"ts": ts, "aqi": float(aqi_val)})

    # Already returned oldest to newest
    return points


def _linear_forecast(history: List[Dict[str, Any]],
                     horizon_minutes: int,
                     step_seconds: int = 60) -> List[Dict[str, Any]]:
    """
    Very simple linear regression forecast on time vs AQI.
    Returns a list of {ts, aqi} for future times only.
    """
    if len(history) < 3:
        return []

    xs = [p["ts"] for p in history]
    ys = [p["aqi"] for p in history]

    # Center time to improve numeric stability
    t0 = xs[0]
    xs0 = [x - t0 for x in xs]
    n = float(len(xs0))

    sum_x = sum(xs0)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs0)
    sum_xy = sum(x * y for x, y in zip(xs0, ys))

    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return []

    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n

    last_ts = xs[-1]
    steps = max(1, int(horizon_minutes * 60 / step_seconds))

    forecast: List[Dict[str, Any]] = []
    for i in range(1, steps + 1):
        ts = last_ts + i * step_seconds
        x = ts - t0
        y = a * x + b
        # Clamp to 0..500
        y = max(0.0, min(500.0, y))
        forecast.append({"ts": ts, "aqi": float(y)})

    return forecast


def compute_aqi_forecast() -> Dict[str, Any]:
    """
    Predictive AQI based on recent PM history.

    Reads forecast_duration from settings.db (latest row).
    If there is not enough history, returns ok=False instead of raising.
    """
    try:
        # 1) Forecast horizon from settings
        settings = settings_store.get_latest_settings()
        if settings and settings.get("forecast_duration"):
            horizon_minutes = int(settings["forecast_duration"])
        else:
            horizon_minutes = 60
    except Exception:
        horizon_minutes = 60

    try:
        history = _history_points(horizon_minutes)
        if len(history) < 3:
            return {
                "ok": False,
                "reason": "not_enough_history",
                "history_count": len(history),
                "forecast": [],
            }

        forecast = _linear_forecast(history, horizon_minutes)

        return {
            "ok": True,
            "horizon_minutes": horizon_minutes,
            "history_count": len(history),
            "forecast_count": len(forecast),
            # front end only uses forecast, history is not sent
            "forecast": forecast,
        }
    except Exception as e:
        # Never throw to Flask, always return JSON
        return {
            "ok": False,
            "error": str(e),
            "forecast": [],
        }
