# ES32 MicroPython Toolkit

**Software Rev 2.0**  
**Copyright © 2026 Qian Yang. All rights reserved.**

Desktop GUI for **ESP32** boards (default: Seeed ESP32-S3):

1. Select board type, then download and flash official MicroPython firmware  
2. Upload / run Python scripts you edit in Cursor (or any editor)

---

## Features

### Flash Firmware
- Choose board type (ESP32-S3 Seeed, generic ESP32 / S2 / S3 / C3 / C6 / C2 / H2)
- Match `esptool` chip, flash address, and firmware `.bin` to the selected board
- Detect serial ports
- Download latest stable firmware from [micropython.org](https://micropython.org/download/)
- Erase flash and write firmware (Seeed ESP32-S3 uses `esp32s3` at `0x0`)

### Upload Code
- Select a local `.py` file (e.g. under `scripts/`)
- Upload to the board (`main.py`, `boot.py`, or custom name)
- **Upload as main.py** — runs automatically after reset
- **Run once** — execute without saving to flash
- List board files, soft reset, pull a file from the board

---

## Requirements

- macOS / Linux / Windows
- Python **3.11+** with **Tcl/Tk** (tkinter)
  - Recommended: [python.org](https://www.python.org/downloads/) installer  
  - On Homebrew Python 3.14: `brew install python-tk@3.14`
- USB-C cable and an ESP32-S3 board

---

## Setup

```bash
cd "/path/to/ES32firmware"
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Dependencies: `esptool`, `pyserial`, `certifi`, `mpremote`.

---

## Run

### macOS App (double-click)

Open:

`ES32 MicroPython Toolkit.app`

Keep this `.app` **inside the project folder** (next to `es32fw.py` and `.venv`).  
You can drag it to the Dock for quick launch.

### Terminal

```bash
source .venv/bin/activate
python es32fw.py
```

Or:

```bash
./run.sh
```

In Cursor / VS Code, select the interpreter: **`.venv/bin/python`**.

---

## Typical workflow

### 1. Flash MicroPython (first time)

1. Connect the board with USB-C  
2. Open **Flash Firmware**, select the board type  
3. Click **Refresh**, select the serial port  
4. Click **Download latest**  
5. Click **Flash MicroPython**  

If the tool cannot connect:

1. Hold **BOOT (B)**  
2. Press **RESET (R)**  
3. Release **BOOT**  
4. Refresh the port and flash again  

### 2. Write code in Cursor → upload to board

1. Edit files under `scripts/` (examples included)  
2. Open **Upload Code**  
3. Select your `.py` file  
4. Choose on-device name (default `main.py`)  
5. Click **Upload as main.py** or **Run once**  

> Close Thonny / other serial tools before uploading so the port is free.

---

## Project layout

```
ES32firmware/
├── es32fw.py           # Main GUI application
├── run.sh              # Launcher (uses .venv)
├── requirements.txt
├── scripts/
│   ├── main.py         # Example: blink onboard LED (GPIO21)
│   └── hello.py        # Example: print hello
├── firmware/           # Downloaded .bin files (created at runtime)
└── README.md
```

---

## Serial tips (macOS)

- Prefer ports like `/dev/cu.usbmodem*`  
- After flashing MicroPython, the same USB port is used by **mpremote** for file transfer  

---

## License / copyright

Copyright © 2026 Qian Yang. All rights reserved.

MicroPython firmware is provided by the MicroPython project and subject to its own license.
