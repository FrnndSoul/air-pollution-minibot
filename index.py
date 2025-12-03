#!/usr/bin/env python3
from __future__ import annotations
import pathlib
import time

from flask import Flask, jsonify, request
from flask_cors import CORS

from sensors import dht11, mq2, mq135, dsm501a, live_aqi
from resources import store, read as read_db
from resources import settings as settings_store
from ai import aqi, prediction

# ---------- Paths ----------

ROOT = pathlib.Path(__file__).resolve().parent
S_DIR = ROOT / "sensors"
R_DIR = ROOT / "resources"
R_DIR.mkdir(exist_ok=True)

def _p(*parts) -> str:
    return str(pathlib.Path(*parts))


# ---------- Shared CTX ----------

CTX = {
    "paths": {
        "root_dir": _p(ROOT),
        "sensors_dir": _p(S_DIR),
        "resources_dir": _p(R_DIR),
        "sensor_db": _p(R_DIR, "sensor.db"),
    },
}


# ---------- Flask ----------

app = Flask(__name__)
CORS(app)

@app.before_first_request
def init_db():
    store.ensure_tables()


# ---------- API ----------

@app.get("/api/health")
def api_health():
    return jsonify({"ok": True, "time": int(time.time())})


# Raw sensor endpoints (unchanged)
@app.get("/api/dht11")
def api_dht11():
    data = dht11.read()
    store.insert_dht11(
        temperature_c=data.get("temperature_c"),
        humidity_percent=data.get("humidity_percent"),
        ts=data.get("ts"),
    )
    return jsonify(data)


@app.get("/api/mq2")
def api_mq2():
    data = mq2.read()
    store.insert_mq2(
        raw=data.get("raw"),
        voltage=data.get("voltage"),
        ts=data.get("ts"),
    )
    return jsonify(data)


@app.get("/api/mq135")
def api_mq135():
    data = mq135.read()
    store.insert_mq135(
        raw=data.get("raw"),
        voltage=data.get("voltage"),
        ts=data.get("ts"),
    )
    return jsonify(data)


@app.get("/api/dsm501a")
def api_dsm501a():
    data = dsm501a.read()
    store.insert_dsm501a(
        low_pulse_ms=data.get("low_pulse_ms"),
        ratio=data.get("ratio"),
        concentration_ug_m3=data.get("concentration_ug_m3"),
        ts=data.get("ts"),
    )
    return jsonify(data)


# ---------- Single combined dashboard endpoint ----------

@app.get("/api/dashboard")
def api_dashboard():
    metrics = live_aqi.compute_live_metrics()

    raw = metrics.get("raw") or {}
    ts = metrics.get("ts") or int(time.time())

    try:
        dht = raw.get("dht11") or {}
        store.insert_dht11(
            temperature_c=dht.get("temperature_c"),
            humidity_percent=dht.get("humidity_percent"),
            ts=dht.get("ts", ts),
        )

        mq2_r = raw.get("mq2") or {}
        store.insert_mq2(
            raw=mq2_r.get("raw"),
            voltage=mq2_r.get("voltage"),
            ts=mq2_r.get("ts", ts),
        )

        mq135_r = raw.get("mq135") or {}
        store.insert_mq135(
            raw=mq135_r.get("raw"),
            voltage=mq135_r.get("voltage"),
            ts=mq135_r.get("ts", ts),
        )

        dsm = raw.get("dsm501a") or {}
        store.insert_dsm501a(
            low_pulse_ms=dsm.get("low_pulse_ms"),
            ratio=dsm.get("ratio"),
            concentration_ug_m3=dsm.get("concentration_ug_m3"),
            ts=dsm.get("ts", ts),
        )
    except Exception as e:
        print("Error logging dashboard sensor data:", e)

    return jsonify({
        "aqi": metrics["aqi"],
        "flame": metrics["flammable_index"],
        "humidity": metrics["humidity_percent"],
        "pm10": metrics["pm10_ug_m3"],
        "pm25": metrics["pm2_5_ug_m3"],
        "smoke": metrics["smoke_index"],
        "temperature": metrics["temperature_c"],
        "toxic": metrics["toxic_index"],
        "voc": metrics["voc_index"],
        "ts": metrics["ts"],
    })

# ---------- Predictive AQI ----------

@app.get("/api/aqi/forecast")
def api_aqi_forecast():
    result = prediction.compute_aqi_forecast()
    return jsonify(result)

# ---------- Settings ----------

@app.get("/api/settings/latest")
def api_get_settings():
    try:
        s = read_db.get_latest_settings()

        if s is None:
            return jsonify({
                "ok": True,
                "settings": {
                    "email": None,
                    "notifications": False,
                    "forecast_duration": None,
                    "refresh_rate": None,
                    "ts": None,
                }
            })

        return jsonify({"ok": True, "settings": s})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/settings/save")
def api_settings_save():
    try:
        data = request.get_json(force=True) or {}
        settings_store.save_settings(
            email=data.get("email"),
            notifications=bool(data.get("notifications")),
            forecast_duration=data.get("forecast_duration"),
            refresh_rate=data.get("refresh_rate"),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# ---------- Main ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
