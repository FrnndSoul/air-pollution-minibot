# ai/aqi.py
from __future__ import annotations
from typing import Dict, Any, List
import time

from sensors import dht11, dsm501a, mq2, mq135

# ai/aqi.py

INDOOR_PM_CALIBRATION = 0.5

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

INDOOR_PM25_BREAKPOINTS = [
    (0.0,   24.0,   0,   50),
    (24.1,  70.8,  51,  100),
    (70.9, 110.8, 101,  150),
    (110.9,300.8, 151, 200),
    (300.9,500.8, 201, 300),
    (500.9,1000.8,301, 500),
]

PM10_BREAKPOINTS = [
    (0.0, 54.0, 0, 50),
    (55.0, 154.0, 51, 100),
    (155.0, 254.0, 101, 150),
    (255.0, 354.0, 151, 200),
    (355.0, 424.0, 201, 300),
    (425.0, 604.0, 301, 500),
]

INDOOR_PM10_BREAKPOINTS = [
    (0.0,   24.0,   0,   50),
    (24.1,  70.8,  51,  100),
    (70.9, 110.8, 101,  150),
    (110.9,300.8, 151, 200),
    (300.9,500.8, 201, 300),
    (500.9,1000.8,301, 500),
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

    pm2_5_raw = dsm.get("concentration_ug_m3")
    if pm2_5_raw is None:
        pm2_5 = None
        pm10 = None
    else:
        pm2_5 = pm2_5_raw * INDOOR_PM_CALIBRATION
        pm10 = pm2_5 * 1.2


    mq2_voltage = mq2_r.get("voltage")
    mq135_voltage = mq135_r.get("voltage")

    voc_index = _scaled_index(mq135_voltage or 0.0, good_level=0.3, bad_level=2.5)
    toxic_index = _scaled_index(mq135_voltage or 0.0, good_level=0.6, bad_level=3.0)
    smoke_index = _scaled_index(mq2_voltage or 0.0, good_level=0.3, bad_level=2.5)
    flame_index = _scaled_index(mq2_voltage or 0.0, good_level=0.5, bad_level=3.0)

    pm25_aqi = _aqi_from_pm(pm2_5 or 0.0, INDOOR_PM25_BREAKPOINTS )
    pm10_aqi = _aqi_from_pm(pm10 or 0.0, INDOOR_PM10_BREAKPOINTS )

    combined_aqi = max(pm25_aqi, pm10_aqi)

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
        "pm2_5_ug_m3_raw": pm2_5_raw,
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

