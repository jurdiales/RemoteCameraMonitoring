"""
RemoteCamera — GUI Launcher
===========================
A tkinter interface to configure and launch the monitoring server.
Run with: python gui.py
"""

import os
import queue
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext, font, ttk
from pygrabber.dshow_graph import FilterGraph

import server as srv

# ── Colour palette (mirrors the web UI) ──────────────────────────────────────────────────────────────────────────────
BG       = "#0a0c0e"
PANEL    = "#111417"
BORDER   = "#1e2329"
GREEN    = "#00e676"
RED      = "#ff3d3d"
AMBER    = "#ffa726"
TEXT     = "#c8cdd4"
DIM      = "#4a5060"
FONT     = "Helvetica"
FONT_SZ  = 11
TERM     = "Cascadia Code SemiBold"
MONO     = (FONT, FONT_SZ)
LABELS   = (FONT, 12, "bold")
MONO_SM  = (FONT, FONT_SZ)

_HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(_HERE, "server.py")

MAX_CONSOLE_LINES = 5

# ── Helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _sep(parent, row, colspan=4):
    """Horizontal separator line."""
    tk.Frame(parent, bg=BORDER, height=1).grid(
        row=row, column=0, columnspan=colspan, sticky="ew", pady=(2, 6))


def _section_label(parent, text, row, colspan=4):
    tk.Label(parent, text=text, bg=BG, fg=DIM, font=LABELS, anchor="w").grid(
        row=row, column=0, columnspan=colspan, sticky="w", pady=(15, 0))
    _sep(parent, row + 1, colspan)


def _label(parent, text, row, col):
    tk.Label(parent, text=text, bg=BG, fg=DIM, font=MONO, anchor="w").grid(
        row=row, column=col, sticky="w", padx=(0, 8), pady=3)


def _entry(parent, default, row, col, width=8, show='', validate='none', validate_cmd=''):
    var = tk.StringVar(value=str(default))
    e = tk.Entry(
        parent, textvariable=var, width=width, show=show, justify=tk.RIGHT,
        bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=MONO,
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=GREEN,
        validate=validate, validatecommand=validate_cmd,
    )
    e.grid(row=row, column=col, sticky="w", pady=3, padx=20)
    return var


def _check(parent, text, default, row, col, colspan=2):
    var = tk.BooleanVar(value=default)
    tk.Checkbutton(
        parent, text=text, variable=var,
        bg=BG, fg=TEXT, selectcolor=PANEL,
        activebackground=BG, activeforeground=GREEN,
        font=MONO, bd=0,
    ).grid(row=row, column=col, columnspan=colspan, sticky="w", pady=2)
    return var

def _style_dropdown(event):
    widget = event.widget
    try:
        # Get the internal popup window path from Tcl
        popup = widget.tk.eval(f'ttk::combobox::PopdownWindow {widget._w}')
        widget.tk.call(popup, 'configure', '-background', BORDER)
        widget.tk.call(popup, 'configure', '-highlightBackground', BORDER)
        widget.tk.call(popup, 'configure', '-highlightColor', BORDER)
        widget.tk.call(popup, 'configure', '-highlightThickness', 1)
    except Exception:
        pass

def _combobox(parent, values, row, col, colspan=3):
    cbb = ttk.Combobox(parent, state="readonly", justify=tk.LEFT, values=values, style='CBB.TCombobox')
    cbb.bind('<Map>', _style_dropdown)
    cbb.option_add('*TCombobox*Listbox*Font', MONO)
    cbb.option_add('*TCombobox*Listbox.background', BG)
    cbb.option_add('*TCombobox*Listbox.foreground', TEXT)
    cbb.option_add('*TCombobox*Listbox.selectBackground', PANEL)
    cbb.option_add('*TCombobox*Listbox.selectForeground', TEXT)
    cbb.option_add('*TCombobox*Listbox.highlightBackground', BORDER)  # ← the white ring
    cbb.option_add('*TCombobox*Listbox.highlightColor', BORDER)       # ← when focused
    cbb.option_add('*TCombobox*Listbox.highlightThickness', 1)
    cbb.option_add('*TCombobox*Listbox.borderWidth', 0)
    cbb.option_add("*TCombobox*Listbox.relief", "flat")
    cbb.configure(font=MONO)
    cbb.grid(row=row, column=col, columnspan=colspan, sticky="we", pady=3, padx=20)
    if len(values) > 0:
        cbb.current(0)
    return cbb

def _validate_int(value):
    """Return True if *value* can be parsed as a non-negative integer."""
    try:
        return int(value) >= 0
    except (ValueError, TypeError):
        return False

def list_fonts():
    print('\n'.join(sorted(list(font.families()))))


def generate_combobox_style(root):
    combostyle = ttk.Style(root)
    combostyle.theme_use('clam')
    combostyle.configure('CBB.TCombobox',
        foreground=TEXT,
        fieldbackground=PANEL,
        background=PANEL,
        selectforeground=TEXT,
        selectbackground=PANEL,
        arrowcolor=TEXT,
        bordercolor=BORDER,
        lightcolor=PANEL,   # ← kills the inner white border of the clam theme
        darkcolor=PANEL,    # ← kills the inner dark bevel of the clam theme
    )
    combostyle.map('CBB.TCombobox',
        foreground=[('readonly', TEXT), ('focus', TEXT), ('disabled', 'gray')],
        fieldbackground=[('readonly', PANEL), ('focus', PANEL)],  # ← prevents white-on-focus
        background=[('active', PANEL), ('pressed', PANEL)],
        selectbackground=[('focus', PANEL)],
        selectforeground=[('focus', TEXT)],
        bordercolor=[('readonly', BORDER), ('focus', BORDER)],
        lightcolor=[('readonly', PANEL), ('focus', PANEL)],
        darkcolor=[('readonly', PANEL), ('focus', PANEL)],
    )

# ── Main window ───────────────────────────────────────────────────────────────────────────────────────────────────────
class ServerLauncher(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("RemoteCamera — Launcher")
        self.configure(bg=BG)
        self.resizable(True, False)
        self.minsize(800, 400)

        self._proc   = None          # subprocess.Popen handle
        self._q      = queue.Queue() # output lines from the server process
        self._reader = None          # background reader thread

        # get available cameras
        self._available_cameras = []
        graph = FilterGraph()
        camera_devices = graph.get_input_devices()
        for index, name in enumerate(camera_devices):
            self._available_cameras.append(f"{index}: {name}")

        generate_combobox_style(self)
        self._build_ui()
        self._poll_queue()           # start the periodic UI updater

    # ── UI ────────────────────────────────────────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        main = tk.Frame(self, bg=BG)   # main has a grid of [2 x 2]
        main.pack(fill='x', pady=(0, 20))
        main.columnconfigure(0, minsize=400, weight=0)
        main.columnconfigure(1, minsize=600, weight=1)

        left_panel = tk.Frame(main, bg=BG)
        left_panel.grid(row=1, column=0)

        self._build_header(main)
        self._build_settings(left_panel)
        self._build_controls(left_panel)
        self._build_console(main)

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=PANEL)
        header.grid(row=0, column=0, columnspan=1, sticky="we")
        tk.Label(header, text="RemoteCamera", bg=PANEL, fg=GREEN,
                 font=(FONT, 13, "bold")).pack(side="left", padx=20, pady=12)
        tk.Label(header, text="// SERVER LAUNCHER", bg=PANEL, fg=DIM,
                 font=MONO_SM).pack(side="left", pady=12)

    def _build_settings(self, parent):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="x", padx=20, pady=(0, 5))

        f = tk.Frame(outer, bg=BG)
        f.pack(fill="x")
        f.columnconfigure(1, minsize=80)
        f.columnconfigure(3, minsize=80)

        r = 0
        # ── Camera ────────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "CAMERA", r); r += 2
        _label(f, "Camera", r, 0)
        self._camera_selector = _combobox(f, self._available_cameras, r, 1); r += 1

        _label(f, "Width (px)", r, 0)
        self._width = _entry(f, srv.STREAM_WIDTH, r, 1, width=8)
        _label(f, "Height (px)", r, 2)
        self._height = _entry(f, srv.STREAM_HEIGHT, r, 3, width=8); r += 1
        _label(f, "FPS", r, 0)
        self._fps = _entry(f, srv.STREAM_FPS, r, 1, width=8); r += 1

        # ── Network ───────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "NETWORK", r); r += 2
        _label(f, "Port", r, 0)
        self._port = _entry(f, srv.FLASK_PORT, r, 1, width=8)
        _label(f, "Password", r, 2)
        self._pwd = _entry(f, "", r, 3, width=14, show="●"); r += 1

        # ── Audio ─────────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "AUDIO", r); r += 2
        _label(f, "Device index", r, 0)
        self._audio = _entry(f, "", r, 1, width=8)
        tk.Label(f, text="(blank = system default)", bg=BG, fg=DIM, font=MONO_SM).grid(row=r,
                    column=2, columnspan=2, sticky="w", padx=(0, 8)); r += 1

        # ── Features ──────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "FEATURES", r); r += 2
        self._motion = _check(f, "Enable motion detection", False, r, 0); r += 1
        self._record = _check(f, "Enable recordings", False, r, 0); r += 1

    def _build_controls(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=20, pady=12)

        self._btn_var = tk.StringVar(value="▶   START SERVER")
        self._btn = tk.Button(frame, textvariable=self._btn_var, command=self._toggle,
            bg=GREEN, fg=BG, activebackground="#00c060", activeforeground=BG,
            font=(FONT, 10, "bold"), relief="flat", padx=20, pady=9, cursor="hand2", bd=0)
        self._btn.pack(fill="x")

    def _build_console(self, parent):
        console_panel = tk.Frame(parent, bg=BG)
        console_panel.grid(row=1, column=1, sticky='nswe', padx=(0, 2))
        header = tk.Frame(parent, bg=PANEL)
        header.grid(row=0, column=1, sticky='nswe')
        tk.Label(header, text="CONSOLE OUTPUT", bg=PANEL, fg=DIM, font=MONO_SM).pack(side="left", padx=20, pady=5)
        self._dot = tk.Label(header, text="●", bg=PANEL, fg=DIM, font=MONO)
        self._dot.pack(side="right", padx=20, pady=5)

        self._console = scrolledtext.ScrolledText(console_panel, bg="#060809", fg=TEXT, font=(TERM, 8),
            relief="flat", bd=0, state="disabled", wrap="word", height=12)
        
        self._console.pack(fill="both", expand=True)
        self._console.tag_config("ok", foreground=GREEN)
        self._console.tag_config("err", foreground=RED)
        self._console.tag_config("warn", foreground=AMBER)
        self._console.tag_config("dim", foreground=DIM)

    # ── Server lifecycle ──────────────────────────────────────────────────────────────────────────────────────────────
    def _toggle(self):
        if self._proc is None:
            self._start()
        else:
            self._stop()

    def _build_cmd(self):
        cmd = [sys.executable, SERVER_SCRIPT]
        cmd += ["--camera", self._camera_selector.get().split(':')[0]]
        cmd += ["--width", self._width.get()]
        cmd += ["--height", self._height.get()]
        cmd += ["--fps", self._fps.get()]
        cmd += ["--port", self._port.get()]
        pwd = self._pwd.get().strip()
        if pwd:
            cmd += ["--password", pwd]
        audio = self._audio.get().strip()
        if audio:
            cmd += ["--audio-device", audio]
        if self._motion.get():
            cmd.append("--motion")
        if self._record.get():
            cmd.append("--record")
        return cmd

    def _start(self):
        cmd = self._build_cmd()
        # Log the command with the password masked
        display = [("●●●●" if i > 0 and cmd[i - 1] == "--password" else c)
                   for i, c in enumerate(cmd)]
        self._log(f"$ {' '.join(display)}\n", "dim")
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=_HERE,)
        except Exception as exc:
            self._log(f"Error: {exc}\n", "err")
            return

        self._btn_var.set("■   STOP SERVER")
        self._btn.config(bg=RED, activebackground="#cc2020")
        self._dot.config(fg=GREEN)

        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    def _stop(self):
        if self._proc:
            self._proc.terminate()
            self._proc = None
        self._set_stopped()
        self._log("— Server stopped —\n", "warn")

    def _set_stopped(self):
        self._proc = None
        self._btn_var.set("▶   START SERVER")
        self._btn.config(bg=GREEN, activebackground="#00c060")
        self._dot.config(fg=DIM)

    # ── Output reader (background thread) ────────────────────────────────────────────────────────────────────────────
    def _read_output(self):
        try:
            if self._proc is not None:
                for line in self._proc.stdout:
                    self._q.put(line)
        except Exception:
            pass
        finally:
            self._q.put(None)  # sentinel: process ended

    # ── Queue poller (main thread, via after()) ───────────────────────────────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                item = self._q.get_nowait()
                if item is None:
                    # Process ended on its own
                    if self._proc is not None:
                        self._set_stopped()
                        self._log("— Server process exited —\n", "warn")
                else:
                    lo = item.lower()
                    tag = ("ok"   if ("local access" in lo or "started" in lo) else
                           "err"  if ("error" in lo or "traceback" in lo or "exception" in lo) else
                           "warn" if "warning" in lo else
                           None)
                    self._log(item, tag)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _log(self, text, tag=None):
        # insert new log lines from server
        self._console.config(state="normal")
        if tag:
            self._console.insert("end", text, tag)
        else:
            self._console.insert("end", text)
        self._console.see("end")
        self._console.config(state="disabled")

        # delete first lines if the maximum has been reached
        cur_lines = int(self._console.index('end-1c').split('.')[0])
        to_delete = cur_lines - MAX_CONSOLE_LINES
        if to_delete > 0:
            self._console.delete('1.0', f'{to_delete}.0')

    # ── Window close ─────────────────────────────────────────────────────────────────────────────────────────────────
    def _on_close(self):
        if self._proc:
            self._proc.terminate()
        self.destroy()


if __name__ == "__main__":
    print("=" * 80)
    print("RemoteCamera GUI Launcher")
    print("=" * 80)
    print("Run with:\tpython gui.py")
    print("\nServer Local Access: http://localhost:port")
    print("Server Remote Access: http://<public-ip>:port")
    print("=" * 80)

    app = ServerLauncher()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()
