# sensors/live_aqi.py
"""
Live AQI computation using current readings from the sensors.

This module is for instant AQI based on:
  - DSM501A particulate (PM2.5, PM10)
  - DHT11 temperature and humidity
  - MQ2 and MQ135 gas sensors (toxic, smoke, VOC, flammable)

Predictive or forecasted AQI will live in ai/aqi.py later.
"""

from typing import Dict, Any
import time

from . import dht11, dsm501a, mq2, mq135
from resources import settings as settings_store

# sensors/live_aqi.py

INDOOR_PM_CALIBRATION = 0.5  # try 0.5 first, then tune

# -------- Helpers --------

def _scaled_index(value: float, good_level: float, bad_level: float) -> float:
    """
    Map a sensor value in [good_level, bad_level] to an index in [0, 500].

    Below good_level -> 0
    Above bad_level  -> 500
    """
    if value is None:
        return 0.0
    if value <= good_level:
        return 0.0
    if value >= bad_level:
        return 500.0
    return 500.0 * (value - good_level) / (bad_level - good_level)


# US style AQI breakpoints for particles
PM25_BREAKPOINTS = [
    (0.0,  12.0,   0,   50),
    (12.1, 35.4,  51,  100),
    (35.5, 55.4, 101,  150),
    (55.5, 150.4,151,  200),
    (150.5,250.4,201,  300),
    (250.5,500.4,301,  500),
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
    (0.0,   54.0,   0,   50),
    (55.0, 154.0,  51,  100),
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
    """Convert μg/m3 to AQI using the given breakpoint table."""
    if value is None:
        return 0.0
    for c_low, c_high, i_low, i_high in breakpoints:
        if c_low <= value <= c_high:
            return i_low + (i_high - i_low) * (value - c_low) / (c_high - c_low)
    # Above highest breakpoint, clamp to 500
    return 500.0


# -------- Main live computation --------

def compute_live_metrics() -> Dict[str, Any]:
    """
    Read all physical sensors and compute live AQI.

    Returns:
        {
          "ts": int,   # seconds
          "temperature_c": float or None,
          "humidity_percent": float or None,
          "pm2_5_ug_m3": float or None,
          "pm10_ug_m3": float or None,
          "toxic_index": float,
          "flammable_index": float,
          "smoke_index": float,
          "voc_index": float,
          "pm25_aqi": float,
          "pm10_aqi": float,
          "aqi": float,
          "status": str,
          "raw": { ... }
        }
    """
    # Raw sensor reads
    dht = dht11.read()
    mq2_r = mq2.read()
    mq135_r = mq135.read()
    settings = settings_store.get_latest_settings()
    refresh_rate = 1  # fallback
    if settings and settings.get("refresh_rate"):
        refresh_rate = max(1, int(settings["refresh_rate"]))

    dsm = dsm501a.read(sample_sec=refresh_rate)

    ts_now = int(time.time())

    # Temperature and humidity
    temp = dht.get("temperature_c")
    humid = dht.get("humidity_percent")

        # DSM501A concentration_ug_m3 is used as PM2.5 approximation.
    pm2_5_raw = dsm.get("concentration_ug_m3")

    if pm2_5_raw is None:
        pm2_5 = None
        pm10 = None
    else:
        # Apply simple indoor calibration
        pm2_5 = pm2_5_raw * INDOOR_PM_CALIBRATION

        # Very simple approximation: PM10 a bit higher than PM2.5.
        pm10 = pm2_5 * 1.2


    # MQ2 and MQ135 voltages
    mq2_voltage = mq2_r.get("voltage")
    mq135_voltage = mq135_r.get("voltage")

    # Gas indices (for separate display, not for main AQI)
    # Thresholds are rough and should be tuned with real world data.
    voc_index = _scaled_index(mq135_voltage or 0.0, good_level=0.3, bad_level=2.5)
    toxic_index = _scaled_index(mq135_voltage or 0.0, good_level=0.6, bad_level=3.0)
    smoke_index = _scaled_index(mq2_voltage or 0.0, good_level=0.3, bad_level=2.5)
    flammable_index = _scaled_index(mq2_voltage or 0.0, good_level=0.5, bad_level=3.0)

    # Particle AQIs
    pm25_aqi = _aqi_from_pm(pm2_5, INDOOR_PM25_BREAKPOINTS)
    pm10_aqi = _aqi_from_pm(pm10 or 0.0, INDOOR_PM10_BREAKPOINTS)

    # Combined AQI for live display - PM only
    combined_aqi = max(pm25_aqi, pm10_aqi)
    
    # Human readable status
    if combined_aqi <= 50:
        status = "Good"
    elif combined_aqi <= 100:
        status = "Moderate"
    elif combined_aqi <= 150:
        status = "Unhealthy for sensitive groups"
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

        # Calibrated values used for AQI
        "pm2_5_ug_m3": pm2_5,
        "pm10_ug_m3": pm10,

        # Raw values from the sensor for debugging
        "pm2_5_ug_m3_raw": pm2_5_raw,
        # you can also add pm10_raw if you want

        # Gas indices (for separate cards)
        "toxic_index": toxic_index,
        "flammable_index": flammable_index,
        "smoke_index": smoke_index,
        "voc_index": voc_index,

        # Particle AQIs
        "pm25_aqi": pm25_aqi,
        "pm10_aqi": pm10_aqi,

        # Combined AQI and status (PM only)
        "aqi": combined_aqi,
        "status": status,

        # Raw readings for debugging
        "raw": {
            "dht11": dht,
            "mq2": mq2_r,
            "mq135": mq135_r,
            "dsm501a": dsm,
        },
    }


def read() -> Dict[str, Any]:
    """Convenience wrapper to match the pattern of other sensor modules."""
    return compute_live_metrics()
