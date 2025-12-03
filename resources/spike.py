# resources/spike.py

from __future__ import annotations

import datetime as dt
import os
import sqlite3
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Sequence

from .email import send_spike_alert_if_enabled
from .settings import get_latest_settings


# Path to settings.db (same file that stores the email and forecast_duration)
SETTINGS_DB_PATH = os.path.join(os.path.dirname(__file__), "settings.db")

# Sensors your system tracks. Adjust if your schema is different.
SENSOR_KEYS = [
    "aqi",
    "pm25",
    "pm10",
    "temp",
    "humidity",
    "toxic",
    "flammable",
    "smoke",
    "voc",
]

# Simple absolute thresholds. If a sensor reading is greater than or equal
# to this value, it counts as a spike.
DEFAULT_ABSOLUTE_THRESHOLDS: Dict[str, float] = {
    "aqi": 150.0,        # Unhealthy
    "pm25": 35.0,        # µg/m³
    "pm10": 50.0,        # µg/m³
    "temp": 32.0,        # Celsius
    "humidity": 75.0,    # Percent
    "toxic": 1.0,        # Normalized index
    "flammable": 1.0,    # Normalized index
    "smoke": 1.0,        # Normalized index
    "voc": 300.0,        # Example ppb threshold
}

# Minimal change required relative to baseline to flag a spike
MIN_RELATIVE_INCREASE: Dict[str, float] = {
    "aqi": 25.0,
    "pm25": 10.0,
    "pm10": 15.0,
    "temp": 2.0,
    "humidity": 5.0,
    "toxic": 0.2,
    "flammable": 0.2,
    "smoke": 0.2,
    "voc": 50.0,
}


@dataclass
class Reading:
    """
    Represents one set of sensor readings at a specific time.

    Example:
        Reading(
            timestamp=datetime.utcnow(),
            values={
                "aqi": 165.0,
                "pm25": 55.2,
                "voc": 310.0,
                ...
            }
        )
    """
    timestamp: dt.datetime
    values: Dict[str, float]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _coerce_float(value: object) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compute_baseline(history: Sequence[Reading]) -> Optional[Dict[str, float]]:
    """
    Compute a simple baseline from older readings.

    Uses the average of each sensor over all readings except the last one.
    If there is not enough history, returns None so that only absolute
    thresholds are used.
    """
    if len(history) < 2:
        return None

    sensor_sums: Dict[str, List[float]] = {key: [] for key in SENSOR_KEYS}

    for reading in history[:-1]:
        for key in SENSOR_KEYS:
            v = _coerce_float(reading.values.get(key))
            if v is not None:
                sensor_sums[key].append(v)

    baseline: Dict[str, float] = {}
    have_any = False

    for key, values in sensor_sums.items():
        if values:
            baseline[key] = float(mean(values))
            have_any = True

    return baseline if have_any else None


def detect_spiking_sensors(
    current_values: Dict[str, float],
    baseline_values: Optional[Dict[str, float]] = None,
    absolute_thresholds: Optional[Dict[str, float]] = None,
    relative_factor: float = 1.4,
) -> List[str]:
    """
    Determine which sensors are currently spiking.

    A sensor is considered to be spiking if:
      * Its value is at or above the absolute threshold
        (from absolute_thresholds or DEFAULT_ABSOLUTE_THRESHOLDS)
    or
      * There is a baseline value available and the current value is
        at least `relative_factor` times the baseline, and it also
        exceeds a minimum absolute increase (MIN_RELATIVE_INCREASE).

    Returns a list of sensor keys, for example: ["aqi", "pm25", "voc"]
    """
    thresholds = dict(DEFAULT_ABSOLUTE_THRESHOLDS)
    if absolute_thresholds:
        thresholds.update(absolute_thresholds)

    spiking: List[str] = []

    for key in SENSOR_KEYS:
        current = _coerce_float(current_values.get(key))
        if current is None:
            continue

        # Absolute rule
        abs_threshold = thresholds.get(key)
        if abs_threshold is not None and current >= abs_threshold:
            spiking.append(key)
            continue

        # Relative rule
        if baseline_values is not None:
            baseline = _coerce_float(baseline_values.get(key))
            if baseline is not None and baseline > 0:
                min_delta = MIN_RELATIVE_INCREASE.get(key, 0.0)
                if current >= baseline * relative_factor and (current - baseline) >= min_delta:
                    spiking.append(key)

    return spiking


def compute_aqi_trend(
    history: Sequence[Reading],
    default_window_minutes: int = 30,
) -> Optional[Dict[str, float]]:
    """
    Compute a simple AQI trend based on the first and last readings.

    Returns a dict of the form:
      {
        "slope": slope_per_minute,
        "current_aqi": last_value,
        "predicted_peak": predicted_value,
      }

    or None if there is not enough data.
    """
    if len(history) < 2:
        return None

    # Use first and last non None AQI values
    first_aqi = None
    first_time = None
    last_aqi = None
    last_time = None

    for reading in history:
        aqi_value = _coerce_float(reading.values.get("aqi"))
        if aqi_value is None:
            continue
        if first_aqi is None:
            first_aqi = aqi_value
            first_time = reading.timestamp
        last_aqi = aqi_value
        last_time = reading.timestamp

    if first_aqi is None or last_aqi is None or first_time is None or last_time is None:
        return None

    delta_minutes = (last_time - first_time).total_seconds() / 60.0
    if delta_minutes <= 0:
        return None

    slope = (last_aqi - first_aqi) / delta_minutes
    predicted_peak = last_aqi + slope * float(default_window_minutes)

    return {
        "slope": slope,
        "current_aqi": last_aqi,
        "predicted_peak": predicted_peak,
    }


# ---------------------------------------------------------------------------
# Cooldown handling using settings.db
# ---------------------------------------------------------------------------

def _ensure_alert_state_table() -> None:
    """
    Creates a small table in settings.db to track the last time an email
    alert was sent, if it does not already exist.
    """
    with sqlite3.connect(SETTINGS_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_alert_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_sent_at TEXT
            )
            """
        )
        conn.commit()


def _get_last_alert_time() -> Optional[dt.datetime]:
    _ensure_alert_state_table()
    with sqlite3.connect(SETTINGS_DB_PATH) as conn:
        cur = conn.execute(
            "SELECT last_sent_at FROM email_alert_state WHERE id = 1"
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        try:
            return dt.datetime.fromisoformat(row[0])
        except ValueError:
            return None


def _set_last_alert_time(ts: dt.datetime) -> None:
    _ensure_alert_state_table()
    iso = ts.isoformat()
    with sqlite3.connect(SETTINGS_DB_PATH) as conn:
        cur = conn.execute(
            "SELECT 1 FROM email_alert_state WHERE id = 1"
        )
        if cur.fetchone():
            conn.execute(
                "UPDATE email_alert_state SET last_sent_at = ? WHERE id = 1",
                (iso,),
            )
        else:
            conn.execute(
                "INSERT INTO email_alert_state (id, last_sent_at) VALUES (1, ?)",
                (iso,),
            )
        conn.commit()


def _get_cooldown_minutes_from_settings(default_minutes: int = 30) -> int:
    """
    Reads forecast_duration from settings.db and uses it as the cooldown.

    If missing or invalid, returns default_minutes.
    """
    try:
        settings = get_latest_settings() or {}
    except Exception:
        settings = {}

    value = settings.get("forecast_duration")

    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = default_minutes

    # At least 1 minute to avoid zero or negative
    return max(minutes, 1)


# ---------------------------------------------------------------------------
# High level function for /api/dashboard
# ---------------------------------------------------------------------------

def handle_new_reading_for_dashboard(
    history: Sequence[Reading],
    absolute_thresholds: Optional[Dict[str, float]] = None,
    relative_factor: float = 1.4,
) -> bool:
    """
    Entry point to call from /api/dashboard.

    Behavior:
      * Reads forecast_duration from settings.db
      * Uses forecast_duration as:
          - cooldown (minimum minutes between emails)
          - forecast window for AQI trend in the email content
      * Detects spikes based on current reading and baseline
      * Sends email through send_spike_alert_if_enabled if:
          - at least one sensor is spiking
          - cooldown has elapsed
          - notifications are enabled and email is configured

    Returns True if an email was sent, False otherwise.
    """
    if not history:
        return False

    cooldown_minutes = _get_cooldown_minutes_from_settings(default_minutes=30)
    now = dt.datetime.utcnow()
    last_sent = _get_last_alert_time()

    if last_sent is not None:
        elapsed_minutes = (now - last_sent).total_seconds() / 60.0
        if elapsed_minutes < cooldown_minutes:
            # Still within cooldown, do not send another email
            return False

    current = history[-1].values
    baseline = _compute_baseline(history)

    spiking = detect_spiking_sensors(
        current_values=current,
        baseline_values=baseline,
        absolute_thresholds=absolute_thresholds,
        relative_factor=relative_factor,
    )

    if not spiking:
        return False

    aqi_trend = compute_aqi_trend(
        history,
        default_window_minutes=cooldown_minutes,
    )

    sent = send_spike_alert_if_enabled(
        spiking_sensors=spiking,
        metrics=current,
        aqi_trend=aqi_trend,
        forecast_window_minutes=cooldown_minutes,
    )

    if sent:
        _set_last_alert_time(now)

    return sent
