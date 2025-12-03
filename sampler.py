# sensor_loop.py
import time

from sensors import dht11, mq2, mq135, dsm501a
from resources import store

SAMPLE_INTERVAL = 5  # seconds


def main():
    print("Starting continuous sensor loop (every 5 sec)...")
    store.ensure_tables()

    while True:
        ts = int(time.time())

        # -------------------------
        # Read actual sensors
        # -------------------------
        dht = dht11.read()
        mq2_r = mq2.read()
        mq135_r = mq135.read()
        dsm = dsm501a.read()

        # -------------------------
        # Store each reading individually
        # -------------------------

        # DHT11
        store.insert_dht11(
            temperature_c=dht.get("temperature_c"),
            humidity_percent=dht.get("humidity_percent"),
            ts=dht.get("ts"),
        )

        # MQ2
        store.insert_mq2(
            raw=mq2_r.get("raw"),
            voltage=mq2_r.get("voltage"),
            ts=mq2_r.get("ts"),
        )

        # MQ135
        store.insert_mq135(
            raw=mq135_r.get("raw"),
            voltage=mq135_r.get("voltage"),
            ts=mq135_r.get("ts"),
        )

        # DSM501A
        store.insert_dsm501a(
            low_pulse_ms=dsm.get("low_pulse_ms"),
            ratio=dsm.get("ratio"),
            concentration_ug_m3=dsm.get("concentration_ug_m3"),
            ts=dsm.get("ts"),
        )

        print(f"[{ts}] Stored new sensor readings.")

        time.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    main()
