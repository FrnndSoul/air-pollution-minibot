# sensors/dht11.py
import time
import random

DHT_PIN = 25


def _simulate():
    return (
        round(28 + random.uniform(-1, 1), 1),
        round(60 + random.uniform(-5, 5), 1)
    )


def read():
    try:
        import adafruit_dht
        import board

        sensor = adafruit_dht.DHT11(board.D25, use_pulseio=False)

        for _ in range(5):
            try:
                t = sensor.temperature
                h = sensor.humidity
                if t is not None and h is not None:
                    return {
                        "temperature_c": float(t),
                        "humidity_percent": float(h),
                        "ts": int(time.time())
                    }
            except Exception:
                time.sleep(0.5)

    except Exception:
        pass

    t, h = _simulate()
    return {
        "temperature_c": t,
        "humidity_percent": h,
        "ts": int(time.time())
    }
