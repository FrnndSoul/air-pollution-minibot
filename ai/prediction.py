from __future__ import annotations
from typing import Dict, Any, List, Tuple
import math
import warnings

from resources import read as read_db
from resources import settings as settings_store
from ai import aqi as aqi_module

# Use the same calibration as ai/aqi.py if it exists
INDOOR_PM_CALIBRATION = getattr(aqi_module, "INDOOR_PM_CALIBRATION", 1.0)

# If you created special indoor breakpoints, pick them up too
PM25_BPS = getattr(aqi_module, "INDOOR_PM25_BREAKPOINTS", aqi_module.PM25_BREAKPOINTS)
PM10_BPS = getattr(aqi_module, "INDOOR_PM10_BREAKPOINTS", aqi_module.PM10_BREAKPOINTS)


class Predictor:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def load_sensor_history(self, sensor_name: str, limit: int = 200):
        import pandas as pd

        df = pd.read_csv(self.db_path)
        df = df[df["sensor"] == sensor_name].tail(limit)
        return df["value"].astype(float)

    def predict_next_5min(self, sensor_name: str) -> float | None:
        from statsmodels.tsa.arima.model import ARIMA

        warnings.filterwarnings("ignore")

        values = self.load_sensor_history(sensor_name)

        if len(values) < 10:
            return None

        model = ARIMA(values, order=(3, 1, 2))
        model_fit = model.fit()

        forecast = model_fit.forecast(steps=1)
        return float(forecast[0])


# ---------- AQI forecast helpers (moved from ai/aqi.py) ----------

def _history_points(max_minutes: int) -> List[Dict[str, Any]]:
    lookback_seconds = max(600, max_minutes * 60 * 2)

    rows = read_db.recent_dsm501a(
        min_seconds_back=lookback_seconds,
        max_rows=2000,
    )

    points: List[Dict[str, Any]] = []
    for r in rows:
        ts = int(r.get("ts") or 0)
        pm2_5_raw = r.get("concentration_ug_m3")
        if pm2_5_raw is None:
            continue

        # Apply the same indoor calibration as live AQI
        pm2_5 = pm2_5_raw * INDOOR_PM_CALIBRATION
        pm10 = pm2_5 * 1.2

        # Use the same breakpoint sets used by ai/aqi.py
        pm25_aqi = aqi_module._aqi_from_pm(pm2_5, PM25_BPS)
        pm10_aqi = aqi_module._aqi_from_pm(pm10, PM10_BPS)

        # For forecast we only care about PM driven AQI
        aqi_val = max(pm25_aqi, pm10_aqi)

        points.append({"ts": ts, "aqi": float(aqi_val)})

    return points



def _linear_forecast(
    history: List[Dict[str, Any]],
    horizon_minutes: int,
    step_seconds: int = 60,
) -> Tuple[List[Dict[str, Any]], float, float, float]:
    """
    Linear regression forecast on time vs AQI.

    Margin of error per forecast point is derived from the
    Root Mean Squared Error (RMSE) of the regression, scaled
    by the number of historical readings (N):

        margin = RMSE / sqrt(N)

    This makes the margin shrink as we get more data, and
    grow when we have fewer samples.

    Returns:
        forecast: list of {ts, aqi, error} for future times only
        mae: mean absolute error on the history
        rmse: root mean squared error on the history
        margin: per point symmetric +/- AQI margin
    """
    n_history = len(history)
    if n_history < 3:
        return [], 0.0, 0.0, 0.0

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
        return [], 0.0, 0.0, 0.0

    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n

    # Compute residuals on history to estimate typical error
    residuals = []
    for ts, y in zip(xs, ys):
        x0 = ts - t0
        y_hat = a * x0 + b
        residuals.append(y - y_hat)

    if residuals:
        mae = sum(abs(r) for r in residuals) / len(residuals)
        rmse = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    else:
        mae = rmse = 0.0

    # Margin of error shrinks as we get more history
    if n_history > 0:
        margin = rmse / math.sqrt(float(n_history))
    else:
        margin = rmse

    last_ts = xs[-1]
    steps = max(1, int(horizon_minutes * 60 / step_seconds))

    forecast: List[Dict[str, Any]] = []
    for i in range(1, steps + 1):
        ts = last_ts + i * step_seconds
        x = ts - t0
        y = a * x + b
        # Clamp to 0..500
        y = max(0.0, min(500.0, y))
        forecast.append(
            {
                "ts": ts,
                "aqi": float(y),
                # Frontend reads error as +/- AQI uncertainty
                "error": float(margin),
            }
        )

    return forecast, float(mae), float(rmse), float(margin)


def compute_aqi_forecast() -> Dict[str, Any]:
    """
    Predictive AQI based on recent PM history.

    Reads forecast_duration from settings.db (latest row).
    If there is not enough history, returns ok=False instead of raising.

    Also computes MAE and RMSE of the regression on the history and
    exposes them in the response. Each forecast point includes an
    "error" field representing a symmetric +/- AQI margin for that
    timestamp. The margin depends both on the regression error and
    on the number of available historical readings.
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
        history_count = len(history)
        if history_count < 3:
            return {
                "ok": False,
                "reason": "not_enough_history",
                "history_count": history_count,
                "forecast": [],
            }

        forecast, mae, rmse, margin = _linear_forecast(history, horizon_minutes)

        return {
            "ok": True,
            "horizon_minutes": horizon_minutes,
            "history_count": history_count,
            "forecast_count": len(forecast),
            "mae": mae,
            "rmse": rmse,
            "margin_error": margin,
            "margin_method": "rmse_over_sqrt_n",
            # Frontend uses 'aqi' and 'error' per point
            "forecast": forecast,
        }
    except Exception as e:
        # Never throw to Flask, always return JSON
        return {
            "ok": False,
            "error": str(e),
            "forecast": [],
        }
