"""Blink onboard LED on Seeed XIAO ESP32-S3.

Edit this file in Cursor, then use the GUI:
  Upload Code → select this file → Upload as main.py
"""

from machine import Pin
import time

# XIAO ESP32-S3 user LED
led = Pin(21, Pin.OUT)

print("XIAO ESP32-S3 blink started")
while True:
    led.value(1)
    time.sleep(0.5)
    led.value(0)
    time.sleep(0.5)
