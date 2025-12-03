# sensors/mq135.py
import time
from .ads1115 import read_channel

CHANNEL = 0

def read():
    raw, voltage = read_channel(CHANNEL)
    return {
        "raw": raw,
        "voltage": voltage,
        "ts": int(time.time())
    }
