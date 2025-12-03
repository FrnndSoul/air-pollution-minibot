# sensors/dsm501a.py
import time
import RPi.GPIO as GPIO

DSM_PIN = 24
DEFAULT_SAMPLE_SEC = 5

_initialized = False

def _ensure_setup():
    global _initialized
    if not _initialized:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(DSM_PIN, GPIO.IN)
        _initialized = True


def read(sample_sec: int = None):
    _ensure_setup()

    # use custom sample time or fall back to default
    SAMPLE_SEC = sample_sec if sample_sec is not None else DEFAULT_SAMPLE_SEC

    start = time.time()
    low_time = 0
    last_state = GPIO.input(DSM_PIN)
    last_change = start

    end = start + SAMPLE_SEC

    while time.time() < end:
        s = GPIO.input(DSM_PIN)
        now = time.time()
        if s != last_state:
            if last_state == GPIO.LOW:
                low_time += now - last_change
            last_state = s
            last_change = now

    if last_state == GPIO.LOW:
        low_time += time.time() - last_change

    lpo_ms = low_time * 1000
    ratio = lpo_ms / (SAMPLE_SEC * 1000 * 10)

    conc = (
        1.1 * ratio**3
        - 3.8 * ratio**2
        + 520 * ratio
        + 0.62
    )

    return {
        "low_pulse_ms": round(lpo_ms, 3),
        "ratio": ratio,
        "concentration_ug_m3": conc,
        "ts": int(time.time())
    }
