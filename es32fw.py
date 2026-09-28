#!/usr/bin/env python3
"""GUI: flash MicroPython to ESP32-S3 and upload Python scripts from Cursor.

Software Rev 1.0
Copyright (c) 2026 Qian Yang. All rights reserved.
"""

from __future__ import annotations

import os
import re
import shlex
import ssl
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path


def _reexec_project_venv() -> None:
    """Always run with project .venv (Homebrew Python often has no _tkinter)."""
    app_dir = Path(__file__).resolve().parent
    venv_dir = app_dir / ".venv"
    venv_python = venv_dir / "bin" / "python3"
    if not venv_python.is_file():
        venv_python = venv_dir / "bin" / "python"
    if not venv_python.is_file():
        return
    try:
        if Path(sys.prefix).resolve() == venv_dir.resolve():
            return
    except OSError:
        pass
    os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]])


_reexec_project_venv()

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:
    if exc.name not in {"tkinter", "_tkinter"}:
        raise
    sys.stderr.write(
        "tkinter/_tkinter is missing.\n"
        "Create/use the project venv (Python.org 3.11+ with Tcl/Tk):\n"
        "  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m venv .venv\n"
        "  source .venv/bin/activate\n"
        "  pip install -r requirements.txt\n"
        "  python es32fw.py\n"
    )
    raise SystemExit(1) from exc

try:
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    list_ports = None

try:
    import certifi
except ImportError:  # pragma: no cover
    certifi = None

APP_NAME = "ES32 MicroPython Toolkit"
APP_REV = "1.0"
APP_COPYRIGHT = "Copyright © 2026 Qian Yang. All rights reserved."
APP_TITLE = f"{APP_NAME}  ·  Rev {APP_REV}"
BOARD_PAGE = "https://micropython.org/download/SEEED_XIAO_ESP32S3/"
FIRMWARE_BASE = "https://micropython.org"
CHIP = "esp32s3"
FLASH_ADDR = "0x0"
DEFAULT_BAUD = "460800"
APP_DIR = Path(__file__).resolve().parent
FIRMWARE_DIR = APP_DIR / "firmware"
SCRIPTS_DIR = APP_DIR / "scripts"


def ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def urlopen(url: str, timeout: float = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "es32fw/1.0"})
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


def list_serial_ports() -> list[str]:
    if list_ports is None:
        return []
    ports: list[str] = []
    for port in list_ports.comports():
        device = port.device or ""
        if sys.platform == "darwin":
            if device.startswith("/dev/tty."):
                continue
            if "Bluetooth" in device or "debug-console" in device:
                continue
        desc = (port.description or "").strip()
        label = f"{device}  ({desc})" if desc and desc != "n/a" else device
        ports.append(label)
    return ports


def port_device(label: str) -> str:
    return label.split("  (", 1)[0].strip()


def find_latest_stable_bin(html: str) -> tuple[str, str]:
    pattern = re.compile(
        r'href="(/resources/firmware/(SEEED_XIAO_ESP32S3-[^"]+\.bin))"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(html):
        path, name = match.group(1), match.group(2)
        if "preview" in name.lower():
            continue
        return f"{FIRMWARE_BASE}{path}", name
    raise RuntimeError("No stable MicroPython .bin found on the download page.")


class FlasherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.minsize(780, 640)
        self.geometry("900x720")
        self.configure(bg="#f4f6f8")

        self.port_var = tk.StringVar()
        self.baud_var = tk.StringVar(value=DEFAULT_BAUD)
        self.firmware_var = tk.StringVar()
        self.erase_first_var = tk.BooleanVar(value=True)
        self.script_var = tk.StringVar()
        self.remote_name_var = tk.StringVar(value="main.py")
        self.status_var = tk.StringVar(value="Ready")
        self._busy = False
        self._proc: subprocess.Popen[str] | None = None
        self._action_buttons: list[ttk.Button] = []

        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        default_script = SCRIPTS_DIR / "main.py"
        if default_script.is_file():
            self.script_var.set(str(default_script))

        self._build_style()
        self._build_ui()
        self.refresh_ports()
        self.refresh_local_scripts()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("TLabel", background="#f4f6f8", foreground="#1f2933")
        style.configure("Card.TLabel", background="#ffffff", foreground="#1f2933")
        style.configure("Title.TLabel", font=("Helvetica", 18, "bold"), background="#f4f6f8")
        style.configure("Hint.TLabel", foreground="#52606d", background="#ffffff")
        style.configure("Status.TLabel", foreground="#334e68", background="#f4f6f8")
        style.configure("Meta.TLabel", foreground="#627d98", background="#f4f6f8", font=("Helvetica", 10))
        style.configure("Accent.TButton", padding=(12, 8))
        style.configure("TButton", padding=(10, 6))
        style.configure("TCheckbutton", background="#ffffff")
        style.configure("TLabelframe", background="#ffffff")
        style.configure("TLabelframe.Label", background="#ffffff", font=("Helvetica", 11, "bold"))
        style.configure("TNotebook", background="#f4f6f8")
        style.configure("TNotebook.Tab", padding=(14, 8))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(root)
        header.pack(fill=tk.X)
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side=tk.LEFT, anchor=tk.W)
        ttk.Button(header, text="About", command=self.show_about).pack(side=tk.RIGHT)

        ttk.Label(
            root,
            text=f"Software Rev {APP_REV}  ·  {APP_COPYRIGHT}",
            style="Meta.TLabel",
        ).pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(
            root,
            text="Flash firmware, then upload Python files you edit in Cursor.",
            style="Status.TLabel",
        ).pack(anchor=tk.W, pady=(4, 10))

        # Shared serial port bar
        port_card = ttk.Frame(root, style="Card.TFrame", padding=12)
        port_card.pack(fill=tk.X, pady=(0, 10))
        port_row = ttk.Frame(port_card, style="Card.TFrame")
        port_row.pack(fill=tk.X)
        ttk.Label(port_row, text="Serial port", style="Card.TLabel", width=12).pack(side=tk.LEFT)
        self.port_combo = ttk.Combobox(
            port_row, textvariable=self.port_var, state="readonly", width=52
        )
        self.port_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(port_row, text="Refresh", command=self.refresh_ports).pack(side=tk.LEFT)

        notebook = ttk.Notebook(root)
        notebook.pack(fill=tk.BOTH, expand=True)

        flash_tab = ttk.Frame(notebook, padding=12)
        code_tab = ttk.Frame(notebook, padding=12)
        notebook.add(flash_tab, text="  Flash Firmware  ")
        notebook.add(code_tab, text="  Upload Code  ")

        self._build_flash_tab(flash_tab)
        self._build_code_tab(code_tab)

        status_row = ttk.Frame(root)
        status_row.pack(fill=tk.X, pady=(10, 4))
        ttk.Label(status_row, textvariable=self.status_var, style="Status.TLabel").pack(
            side=tk.LEFT, anchor=tk.W
        )
        self.cancel_btn = ttk.Button(
            status_row, text="Cancel", command=self.cancel_job, state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        log_frame = ttk.LabelFrame(root, text="Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(
            log_frame,
            height=14,
            wrap=tk.WORD,
            bg="#0b1220",
            fg="#e2e8f0",
            insertbackground="#e2e8f0",
            font=("Menlo", 11),
            relief=tk.FLAT,
            padx=8,
            pady=8,
        )
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.configure(yscrollcommand=scroll.set, state=tk.DISABLED)

        ttk.Label(
            root,
            text=f"Rev {APP_REV}  |  {APP_COPYRIGHT}",
            style="Meta.TLabel",
        ).pack(anchor=tk.E, pady=(8, 0))

    def _build_flash_tab(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X)

        baud_row = ttk.Frame(card, style="Card.TFrame")
        baud_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(baud_row, text="Baud rate", style="Card.TLabel", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            baud_row,
            textvariable=self.baud_var,
            values=("115200", "230400", "460800", "921600"),
            state="readonly",
            width=16,
        ).pack(side=tk.LEFT)

        fw_row = ttk.Frame(card, style="Card.TFrame")
        fw_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(fw_row, text="Firmware .bin", style="Card.TLabel", width=14).pack(side=tk.LEFT)
        ttk.Entry(fw_row, textvariable=self.firmware_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8)
        )
        ttk.Button(fw_row, text="Browse…", command=self.browse_firmware).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(fw_row, text="Download latest", command=self.download_firmware).pack(side=tk.LEFT)

        ttk.Label(
            card,
            text="Official MicroPython firmware for ESP32-S3.",
            style="Hint.TLabel",
        ).pack(anchor=tk.W)

        ttk.Checkbutton(
            card,
            text="Erase flash before writing (recommended for first install)",
            variable=self.erase_first_var,
        ).pack(anchor=tk.W, pady=(12, 0))

        tip = ttk.LabelFrame(parent, text="Bootloader tip", padding=12)
        tip.pack(fill=tk.X, pady=12)
        ttk.Label(
            tip,
            text=(
                "1. Connect the ESP32-S3 board with USB-C.\n"
                "2. If flashing fails: hold BOOT (B), press RESET (R), release BOOT.\n"
                "3. Refresh port → Flash MicroPython."
            ),
            style="Card.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X)
        erase_btn = ttk.Button(actions, text="Erase flash", command=self.erase_flash)
        erase_btn.pack(side=tk.LEFT)
        flash_btn = ttk.Button(
            actions, text="Flash MicroPython", style="Accent.TButton", command=self.flash_firmware
        )
        flash_btn.pack(side=tk.LEFT, padx=8)
        self._action_buttons.extend([erase_btn, flash_btn])

    def _build_code_tab(self, parent: ttk.Frame) -> None:
        tip = ttk.LabelFrame(parent, text="Workflow (Cursor → ESP32-S3)", padding=12)
        tip.pack(fill=tk.X)
        ttk.Label(
            tip,
            text=(
                "1. Edit Python under scripts/ in Cursor (e.g. scripts/main.py).\n"
                "2. Select the file below.\n"
                "3. Upload as main.py (runs on boot) or Run once (no save)."
            ),
            style="Card.TLabel",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        card = ttk.Frame(parent, style="Card.TFrame", padding=14)
        card.pack(fill=tk.X, pady=(12, 0))

        local_row = ttk.Frame(card, style="Card.TFrame")
        local_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(local_row, text="Local .py", style="Card.TLabel", width=14).pack(side=tk.LEFT)
        self.script_combo = ttk.Combobox(local_row, textvariable=self.script_var, width=48)
        self.script_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(local_row, text="Browse…", command=self.browse_script).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(local_row, text="Refresh list", command=self.refresh_local_scripts).pack(
            side=tk.LEFT
        )

        remote_row = ttk.Frame(card, style="Card.TFrame")
        remote_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(remote_row, text="On device as", style="Card.TLabel", width=14).pack(side=tk.LEFT)
        ttk.Combobox(
            remote_row,
            textvariable=self.remote_name_var,
            values=("main.py", "boot.py", "hello.py", "app.py"),
            width=20,
        ).pack(side=tk.LEFT)
        ttk.Label(
            remote_row,
            text="  main.py = auto-run after reset",
            style="Hint.TLabel",
        ).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(
            card,
            text=f"Project scripts folder: {SCRIPTS_DIR}",
            style="Hint.TLabel",
        ).pack(anchor=tk.W, pady=(4, 0))

        actions = ttk.Frame(parent)
        actions.pack(fill=tk.X, pady=(12, 0))

        upload_btn = ttk.Button(
            actions, text="Upload to board", style="Accent.TButton", command=self.upload_script
        )
        upload_btn.pack(side=tk.LEFT)
        upload_main_btn = ttk.Button(
            actions, text="Upload as main.py", command=self.upload_as_main
        )
        upload_main_btn.pack(side=tk.LEFT, padx=6)
        run_btn = ttk.Button(actions, text="Run once", command=self.run_script)
        run_btn.pack(side=tk.LEFT, padx=6)

        actions2 = ttk.Frame(parent)
        actions2.pack(fill=tk.X, pady=(8, 0))
        ls_btn = ttk.Button(actions2, text="List board files", command=self.list_board_files)
        ls_btn.pack(side=tk.LEFT)
        reset_btn = ttk.Button(actions2, text="Soft reset", command=self.soft_reset)
        reset_btn.pack(side=tk.LEFT, padx=6)
        open_btn = ttk.Button(actions2, text="Open scripts folder", command=self.open_scripts_folder)
        open_btn.pack(side=tk.LEFT, padx=6)
        pull_btn = ttk.Button(actions2, text="Pull from board…", command=self.pull_from_board)
        pull_btn.pack(side=tk.LEFT, padx=6)

        self._action_buttons.extend(
            [upload_btn, upload_main_btn, run_btn, ls_btn, reset_btn, open_btn, pull_btn]
        )

    # ----- logging / status -----

    def append_log(self, text: str) -> None:
        def _append() -> None:
            self.log.configure(state=tk.NORMAL)
            self.log.insert(tk.END, text)
            self.log.see(tk.END)
            self.log.configure(state=tk.DISABLED)

        self.after(0, _append)

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_var.set(text))

    def show_about(self) -> None:
        messagebox.showinfo(
            "About",
            f"{APP_NAME}\n"
            f"Software Rev {APP_REV}\n\n"
            f"{APP_COPYRIGHT}\n\n"
            "Flash MicroPython to ESP32-S3\n"
            "and upload Python scripts from Cursor.",
        )

    # ----- shared helpers -----

    def refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo["values"] = ports
        if ports:
            current = self.port_var.get()
            if current not in ports:
                preferred = next(
                    (p for p in ports if "usbmodem" in p.lower() or "usb" in p.lower()),
                    ports[0],
                )
                self.port_var.set(preferred)
            self.append_log(f"Found {len(ports)} serial port(s).\n")
        else:
            self.port_var.set("")
            self.append_log("No serial ports found. Plug in the board and click Refresh.\n")

    def refresh_local_scripts(self) -> None:
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(str(p) for p in SCRIPTS_DIR.glob("*.py"))
        self.script_combo["values"] = files
        current = self.script_var.get().strip()
        if current and current not in files and Path(current).is_file():
            files = [current, *files]
            self.script_combo["values"] = files
        elif not current and files:
            self.script_var.set(files[0])

    def browse_firmware(self) -> None:
        path = filedialog.askopenfilename(
            title="Select MicroPython firmware",
            filetypes=[("Firmware binary", "*.bin"), ("All files", "*.*")],
        )
        if path:
            self.firmware_var.set(path)

    def browse_script(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Python script",
            initialdir=str(SCRIPTS_DIR),
            filetypes=[("Python", "*.py"), ("All files", "*.*")],
        )
        if path:
            self.script_var.set(path)
            self.refresh_local_scripts()

    def open_scripts_folder(self) -> None:
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(SCRIPTS_DIR)])
        elif sys.platform.startswith("win"):
            os.startfile(str(SCRIPTS_DIR))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(SCRIPTS_DIR)])

    def _require_port(self) -> bool:
        if not self.port_var.get().strip():
            messagebox.showwarning("Port required", "Select a serial port first.")
            return False
        return True

    def _require_script(self) -> Path | None:
        path = Path(self.script_var.get().strip())
        if not str(path):
            messagebox.showwarning("Script required", "Select a local .py file first.")
            return None
        if not path.is_file():
            messagebox.showerror("Missing file", f"Script not found:\n{path}")
            return None
        return path

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for btn in self._action_buttons:
            btn.configure(state=state)
        self.cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)

    def _run_job(self, status: str, fn) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.set_status(status)

        def runner() -> None:
            try:
                fn()
                self.set_status("Done")
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                self.append_log(f"\nERROR: {err}\n")
                self.set_status("Failed")
                self.after(0, lambda e=err: messagebox.showerror("Operation failed", e))
            finally:
                self._proc = None
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=runner, daemon=True).start()

    def cancel_job(self) -> None:
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()
            self.append_log("\nCancel requested…\n")
            self.set_status("Cancelling…")

    def _run_cmd(self, cmd: list[str]) -> None:
        self.append_log("\n$ " + " ".join(shlex.quote(a) for a in cmd) + "\n")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self.append_log(line)
        code = self._proc.wait()
        if code != 0:
            raise RuntimeError(f"Command exited with code {code}")
        self.append_log("OK\n")

    def _mpremote(self, *args: str) -> None:
        port = port_device(self.port_var.get())
        cmd = [
            sys.executable,
            "-m",
            "mpremote",
            "connect",
            f"port:{port}",
            *args,
        ]
        self._run_cmd(cmd)

    # ----- flash tab actions -----

    def download_firmware(self) -> None:
        if self._busy:
            return
        self._run_job("Downloading firmware…", self._download_worker)

    def erase_flash(self) -> None:
        if not self._require_port():
            return
        if not messagebox.askyesno(
            "Erase flash",
            "This will erase the entire flash on the board.\nContinue?",
        ):
            return
        self._run_job("Erasing flash…", lambda: self._run_esptool(["erase-flash"]))

    def flash_firmware(self) -> None:
        if not self._require_port():
            return
        firmware = self.firmware_var.get().strip()
        if not firmware:
            messagebox.showwarning("Firmware required", "Select or download a .bin firmware first.")
            return
        if not Path(firmware).is_file():
            messagebox.showerror("Missing file", f"Firmware not found:\n{firmware}")
            return

        def worker() -> None:
            if self.erase_first_var.get():
                self.set_status("Erasing flash…")
                self._run_esptool(["erase-flash"])
            self.set_status("Writing firmware…")
            self._run_esptool(
                [
                    "--baud",
                    self.baud_var.get(),
                    "write-flash",
                    "-z",
                    FLASH_ADDR,
                    firmware,
                ]
            )

        self._run_job("Flashing MicroPython…", worker)

    def _download_worker(self) -> None:
        FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
        self.append_log(f"Fetching firmware list from {BOARD_PAGE}\n")
        with urlopen(BOARD_PAGE, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        url, name = find_latest_stable_bin(html)
        dest = FIRMWARE_DIR / name
        self.append_log(f"Downloading {name}\n{url}\n")

        with urlopen(url, timeout=120) as resp, open(dest, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            read = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if total:
                    pct = read * 100 // total
                    self.set_status(f"Downloading… {pct}%")

        self.after(0, lambda: self.firmware_var.set(str(dest)))
        size_mb = dest.stat().st_size / (1024 * 1024)
        self.append_log(f"Saved {dest} ({size_mb:.2f} MB)\n")

    def _run_esptool(self, args: list[str]) -> None:
        port = port_device(self.port_var.get())
        cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            CHIP,
            "--port",
            port,
            *args,
        ]
        self._run_cmd(cmd)

    # ----- upload code tab actions -----

    def upload_script(self) -> None:
        if not self._require_port():
            return
        path = self._require_script()
        if path is None:
            return
        remote = self.remote_name_var.get().strip() or path.name
        if not remote.endswith(".py"):
            remote += ".py"

        def worker() -> None:
            self._mpremote("fs", "cp", str(path), f":{remote}")
            self.append_log(f"Uploaded → :{remote}\n")

        self._run_job(f"Uploading {path.name} → {remote}…", worker)

    def upload_as_main(self) -> None:
        self.remote_name_var.set("main.py")
        self.upload_script()

    def run_script(self) -> None:
        if not self._require_port():
            return
        path = self._require_script()
        if path is None:
            return

        def worker() -> None:
            self._mpremote("run", str(path))

        self._run_job(f"Running {path.name}…", worker)

    def list_board_files(self) -> None:
        if not self._require_port():
            return
        self._run_job("Listing board files…", lambda: self._mpremote("fs", "ls", ":"))

    def soft_reset(self) -> None:
        if not self._require_port():
            return
        self._run_job("Soft reset…", lambda: self._mpremote("soft-reset"))

    def pull_from_board(self) -> None:
        if not self._require_port():
            return
        remote = self.remote_name_var.get().strip() or "main.py"
        if not remote.endswith(".py"):
            remote += ".py"
        dest = filedialog.asksaveasfilename(
            title="Save board file as",
            initialdir=str(SCRIPTS_DIR),
            initialfile=remote,
            defaultextension=".py",
            filetypes=[("Python", "*.py"), ("All files", "*.*")],
        )
        if not dest:
            return

        def worker() -> None:
            self._mpremote("fs", "cp", f":{remote}", dest)
            self.append_log(f"Pulled :{remote} → {dest}\n")
            self.after(0, self.refresh_local_scripts)

        self._run_job(f"Pulling :{remote}…", worker)

    def _on_close(self) -> None:
        if self._busy:
            if not messagebox.askyesno("Busy", "An operation is running. Quit anyway?"):
                return
            self.cancel_job()
        self.destroy()


def main() -> None:
    if list_ports is None:
        print("pyserial is required. Install with: pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)
    app = FlasherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
