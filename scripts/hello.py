"""Hello from MicroPython on XIAO ESP32-S3."""

import sys
import time

print("Hello from XIAO ESP32-S3!")
print("MicroPython:", sys.version)
print("Platform:", sys.platform)

for i in range(5):
    print(f"tick {i}")
    time.sleep(0.5)

print("done")
