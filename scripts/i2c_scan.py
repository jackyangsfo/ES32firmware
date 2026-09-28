"""I2C bus scan for Seeed XIAO ESP32-S3 (MicroPython).

Default hardware I2C pins on XIAO ESP32-S3:
  SDA = D4 = GPIO5
  SCL = D5 = GPIO6

Upload: Upload Code → this file → Run once
Or save as main.py temporarily to see results after reset.
"""

from machine import Pin, SoftI2C
import time

SDA_PIN = 5  # D4
SCL_PIN = 6  # D5
FREQ = 100_000

print("I2C scan on SDA=GPIO%d SCL=GPIO%d @ %d Hz" % (SDA_PIN, SCL_PIN, FREQ))
time.sleep(0.2)

i2c = SoftI2C(sda=Pin(SDA_PIN), scl=Pin(SCL_PIN), freq=FREQ)
addrs = i2c.scan()

if not addrs:
    print("No I2C devices found.")
    print("Check: wiring, 3V3/GND, pull-ups (often 4.7k), correct SDA/SCL.")
else:
    print("Found %d device(s):" % len(addrs))
    for a in addrs:
        print("  0x%02X (%d)" % (a, a))

print("done")
