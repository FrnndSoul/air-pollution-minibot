# sensors/ads1115.py
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
ads.gain = 1

CHANNEL_MAP = {
    0: ADS.P0,
    1: ADS.P1,
    2: ADS.P2,
    3: ADS.P3,
}


def read_channel(ch):
    pin = CHANNEL_MAP[ch]
    chan = AnalogIn(ads, pin)
    return int(chan.value), float(chan.voltage)
