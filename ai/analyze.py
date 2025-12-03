# ai/analyze.py
from typing import Dict, List, Tuple, Optional
import time
from math import isnan

from resources import read as db_read


def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs) or 1.0
    a = num / den
    b = mean_y - a * mean_x
    return a, b


def _forecast_series(
    rows: List[Dict],
    value_key: str,
    horizon_sec: int,
    min_points: int = 60,
) -> Dict[str, Optional[float]]:
    """
    Generic forecast helper.

    rows: list of rows with ts and value_key
    value_key: which column to forecast
    horizon_sec: how far into the future to predict
    min_points: minimum points required to use regression
    """
    rows = [r for r in rows if r.get(value_key) is not None]
    if not rows:
        return {
            "latest": None,
            "predicted": None,
        }

    xs = [float(r["ts"]) for r in rows]
    ys = [float(r[value_key]) for r in rows]

    latest_value = ys[-1]

    if len(xs) < min_points:
        # Not enough history, just use last value
        return {
            "latest": latest_value,
            "predicted": latest_value,
        }

    a, b = _linear_regression(xs, ys)
    target_ts = int(time.time()) + horizon_sec
    y_pred = a * target_ts + b

    if isnan(y_pred):
        y_pred = latest_value

    return {
        "latest": latest_value,
        "predicted": y_pred,
    }


def _choose_history_window(horizon_sec: int) -> int:
    """
    Decide how far back to look based on requested horizon.

    All values in seconds.
    """
    if horizon_sec <= 15 * 60:
        # forecast within 15 minutes, look back 1 hour
        return 60 * 60
    elif horizon_sec <= 60 * 60:
        # up to 1 hour ahead, look back 3 hours
        return 3 * 60 * 60
    else:
        # up to several hours ahead, look back 6 hours
        return 6 * 60 * 60


def api_prediction(horizon_sec: int = 300) -> Dict[str, Dict]:
    """
    Main AI forecast API.

    horizon_sec:
        300  - 5 min ahead
        3600 - 1 hour ahead
        7200 - 2 hours ahead, etc.
    """
    history_window = _choose_history_window(horizon_sec)

    # Fetch recent history from DB
    dht_rows = db_read.recent_dht11(min_seconds_back=history_window)
    mq2_rows = db_read.recent_mq2(min_seconds_back=history_window)
    mq135_rows = db_read.recent_mq135(min_seconds_back=history_window)
    dsm_rows = db_read.recent_dsm501a(min_seconds_back=history_window)

    result = {
        "meta": {
            "horizon_sec": horizon_sec,
            "history_window_sec": history_window,
            "ts_now": int(time.time()),
        },
        "dht11": {
            "temperature_c": _forecast_series(dht_rows, "temperature_c", horizon_sec),
            "humidity_percent": _forecast_series(dht_rows, "humidity_percent", horizon_sec),
        },
        "mq2": {
            "voltage": _forecast_series(mq2_rows, "voltage", horizon_sec),
            "raw": _forecast_series(mq2_rows, "raw", horizon_sec),
        },
        "mq135": {
            "voltage": _forecast_series(mq135_rows, "voltage", horizon_sec),
            "raw": _forecast_series(mq135_rows, "raw", horizon_sec),
        },
        "dsm501a": {
            "concentration_ug_m3": _forecast_series(dsm_rows, "concentration_ug_m3", horizon_sec),
            "ratio": _forecast_series(dsm_rows, "ratio", horizon_sec),
        },
    }

    return result
