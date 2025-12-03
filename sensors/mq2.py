# sensors/mq2.py
import time
from .ads1115 import read_channel

CHANNEL = 1

def read():
    raw, voltage = read_channel(CHANNEL)
    return {
        "raw": raw,
        "voltage": voltage,
        "ts": int(time.time())
    }
