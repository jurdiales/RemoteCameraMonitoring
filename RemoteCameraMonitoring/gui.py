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
import importlib.resources as pkg_resources
import webbrowser
from tkinter import scrolledtext, font, ttk, messagebox, filedialog

import platform
PLATFORM = platform.system()
if PLATFORM == 'Windows':
    # set AppID on Windows
    import ctypes
    myappid = 'mycompany.remotecameramonitoring.subproduct.version'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

try:
    from . import state as srv   # installed package
    from .utils import list_camera_names, list_audio_input_names
    from .config import load_config, save_config
    from .password import hash_password
except ImportError:
    import state as srv          # plain script
    from utils import list_camera_names, list_audio_input_names
    from config import load_config, save_config
    from password import hash_password

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
FONT_SZ  = 10
# Monospace font: prefer Cascadia Code on Windows, fall back gracefully
if PLATFORM == "Windows":
    TERM = "Cascadia Code SemiBold"
elif PLATFORM == "Darwin":
    TERM = "Menlo"
else:  # Linux / others
    TERM = "DejaVu Sans Mono"
MONO     = (FONT, FONT_SZ)
LABELS   = (FONT, 11, "bold")
MONO_SM  = (FONT, FONT_SZ)

_HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(_HERE, "server.py")

def _resource(filename: str) -> str:
    """Return the absolute path to a file inside the package's resources/ folder.
    Works both when running from source and when installed via pip.
    """
    try:
        return str(pkg_resources.files("RemoteCameraMonitoring").joinpath("resources", filename))
    except:
        return os.path.join(_HERE, "resources", filename)

MAX_CONSOLE_LINES = 1000
SYSTEM_DEFAULT = "System default"

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ── Helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _sep(parent, row, colspan=4):
    """Horizontal separator line."""
    tk.Frame(parent, bg=BORDER, height=1).grid(
        row=row, column=0, columnspan=colspan, sticky="ew", pady=(2, 6))


def _section_label(parent, text, row, colspan=4):
    tk.Label(parent, text=text, bg=BG, fg=DIM, font=LABELS, anchor="w").grid(
        row=row, column=0, columnspan=colspan, sticky="w", pady=(15, 0))
    _sep(parent, row + 1, colspan)


def _label(parent, text, row, col, colspan=1):
    tk.Label(parent, text=text, bg=BG, fg=DIM, font=MONO, anchor="w").grid(
        row=row, column=col, columnspan=colspan, sticky="w", padx=(0, 8), pady=3)


def _entry(parent, default, row, col, width=8, show='', sticky='w', colspan=1, padx=(20, 20), validate='none',
           validate_cmd=''):
    var = tk.StringVar(value=str(default))
    e = tk.Entry(
        parent, textvariable=var, width=width, show=show, justify=tk.CENTER,
        bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", font=MONO,
        highlightthickness=1, highlightbackground=BORDER, highlightcolor=GREEN,
        validate=validate, validatecommand=validate_cmd, # pyright: ignore[reportArgumentType]
    )
    e.grid(row=row, column=col, columnspan=colspan, sticky=sticky, pady=3, padx=padx)
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
    cbb.grid(row=row, column=col, columnspan=colspan, sticky="we", pady=3, padx=(20, 20))
    if len(values) > 0:
        cbb.current(0)
    return cbb

def _validate_int(value):
    """Return True if *value* can be parsed as a non-negative integer."""
    try:
        return int(value) >= 0
    except (ValueError, TypeError):
        return False

def _generate_combobox_style(root):
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

def list_fonts():
    print('\n'.join(sorted(list(font.families()))))

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ── Main window ──────────────────────────────────────────────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
class ServerLauncher(tk.Tk):

    def __init__(self, camera_list, audio_input_list):
        super().__init__()
        self.title("RemoteCamera")
        self.configure(bg=BG)
        self.resizable(True, False)
        self.minsize(900, 400)
        self._small_icon = tk.PhotoImage(file=_resource("icon16.png"))
        if PLATFORM == 'Windows':
            self._big_icon = tk.PhotoImage(file=_resource("icon32.png"))
        else:
            self._big_icon = tk.PhotoImage(file=_resource("icon64.png"))
        self.iconphoto(False, self._small_icon, self._big_icon)

        self._proc   = None          # subprocess.Popen handle
        self._q      = queue.Queue() # output lines from the server process
        self._reader = None          # background reader thread

        self._cfg = load_config()
        self._hash_generated = False

        _generate_combobox_style(self)
        self._available_cameras = camera_list
        self._available_audio_sources = audio_input_list
        self._has_ssl_cert = bool(self._cfg.get("ssl_cert", ""))
        self._has_ssl_key = bool(self._cfg.get("ssl_key", ""))
        self._build_ui()
        self._poll_queue()           # start the periodic UI updater
    
    def _open_web_interface(self):
        if self._caddy.get():
            webbrowser.open(f"https://localhost")
        elif self._has_ssl_cert and self._has_ssl_key:
            webbrowser.open(f"https://localhost:{self._port.get()}")
        else:
            webbrowser.open(f"http://localhost:{self._port.get()}")
    
    def _clear_console(self):
        self._console.config(state="normal")
        self._console.delete('1.0', tk.END)
        self._console.config(state="disabled")
    
    # ── UI ───────────────────────────────────────────────────────────────────────────────────────────────────────────
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
        # ── Camera and Network ───────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "BASIC", r); r += 2
        _label(f, "Camera", r, 0)
        self._camera_selector = _combobox(f, self._available_cameras, r, 1); r += 1
        cfg_cam = self._cfg.get("camera_index", 0)
        for i, val in enumerate(self._available_cameras):
            if val.startswith(f"{cfg_cam}:"):
                self._camera_selector.current(i)
                break

        _label(f, "Width (px)", r, 0)
        self._width = _entry(f, self._cfg.get("stream_width", 1280), r, 1, width=8)
        _label(f, "Height (px)", r, 2)
        self._height = _entry(f, self._cfg.get("stream_height", 720), r, 3, width=8); r += 1
        _label(f, "FPS", r, 0)
        self._fps = _entry(f, self._cfg.get("stream_fps", 20), r, 1, width=8)
        _label(f, "Net Port", r, 2)
        self._port = _entry(f, self._cfg.get("flask_port", 8090), r, 3, width=8); r += 1

        # ── Security ─────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "SECURITY", r); r += 2

        def _generate_hash():
            if self._pwd.get().strip():
                hash = hash_password(self._pwd.get().strip())
                self._hash.set(hash)
                self._hash_generated = True
                self.clipboard_clear()
                self.clipboard_append(hash)
            else:
                self._hash_generated = False

        _label(f, "Password", r, 0)
        self._pwd = _entry(f, "", r, 1, colspan=2, padx=(20, 0), sticky="we", show="●")
        self._gen_hash_frame = tk.Frame(f, highlightbackground=DIM, highlightthickness=1, bd=0)
        self._gen_hash_frame.grid(row=r, column=3, columnspan=1, sticky='we', pady=3, padx=20)
        self._gen_hash_btn = tk.Button(self._gen_hash_frame, text="Generate Hash", command=_generate_hash, bg=PANEL, fg=DIM,
                                        activebackground=BG, activeforeground=DIM, font=MONO, relief="flat", cursor="hand2", bd=0)
        self._gen_hash_btn.pack(fill='both'); r += 1
        _label(f, "Hash", r, 0)
        env_hash = os.getenv(srv.PASSWORD_HASH_ENV, self._cfg.get("login_password_hash", ""))
        self._hash = _entry(f, env_hash, r, 1, colspan=3, sticky="we"); r += 1
        _label(f, "Remote HTTPS / TLS configuration:", r, 0, colspan=4); r += 1
        
        self._ssl_cert_file = self._cfg.get("ssl_cert", "")
        if not os.path.exists(self._ssl_cert_file):
            self._ssl_cert_file = ""
            self._has_ssl_cert = False
        self._ssl_cert_var = tk.StringVar(value=os.path.basename(self._ssl_cert_file) if self._ssl_cert_file else "No certificate file selected")
        self._ssl_key_file = self._cfg.get("ssl_key", "")
        if not os.path.exists(self._ssl_key_file):
            self._ssl_key_file = ""
            self._has_ssl_key = False
        self._ssl_key_var = tk.StringVar(value=os.path.basename(self._ssl_key_file) if self._ssl_key_file else "No key file selected")
        
        def _open_file_name(name: str):
            result = filedialog.askopenfilename(parent=self, title=f"Open {name} file", initialdir=_HERE, filetypes=(
                ("SSL/TLS Certificates", "*.pem"), ("All files", "*.*")
            ))
            # check selected file validity
            if (len(result) > 0) and (result.split('.')[-1] == "pem"):
                if name == "certificate":
                    self._ssl_cert_file = result
                    self._ssl_cert_var.set(os.path.basename(result))
                    self._has_ssl_cert = True
                elif name == "key":
                    self._ssl_key_file = result
                    self._ssl_key_var.set(os.path.basename(result))
                    self._has_ssl_key = True
        
        self._open_cert_frame = tk.Frame(f, highlightbackground=DIM, highlightthickness=1, bd=0)
        self._open_cert_frame.grid(row=r, column=0, columnspan=2, sticky='w', pady=3, padx=20)
        self._btn_open_cert = tk.Button(self._open_cert_frame, text="Open certificate", command=lambda: _open_file_name("certificate"), bg=PANEL, fg=DIM,
                                        activebackground=BG, activeforeground=DIM, font=MONO, relief="flat", cursor="hand2", bd=0, width=12)
        self._btn_open_cert.pack()
        self._certificate_label = tk.Label(f, textvariable=self._ssl_cert_var, bg=PANEL, fg=DIM, font=MONO)
        self._certificate_label.grid(row=r, column=2, columnspan=2, sticky='we', pady=3, padx=(0, 20)); r += 1

        self._open_key_frame = tk.Frame(f, highlightbackground=DIM, highlightthickness=1, bd=0)
        self._open_key_frame.grid(row=r, column=0, columnspan=2, sticky='w', pady=3, padx=20)
        self._btn_open_key = tk.Button(self._open_key_frame, text="Open key", command=lambda: _open_file_name("key"), bg=PANEL, fg=DIM, activebackground=BG,
                                       activeforeground=DIM, font=MONO, relief="flat", cursor="hand2", bd=0, width=12)
        self._btn_open_key.pack()
        self._key_label = tk.Label(f, textvariable=self._ssl_key_var, bg=PANEL, fg=DIM, font=MONO)
        self._key_label.grid(row=r, column=2, columnspan=2, sticky='we', pady=3, padx=(0, 20)); r += 1

        # ── Audio ────────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "AUDIO", r); r += 2
        _label(f, "Device", r, 0)
        self._audio_selector = _combobox(f, self._available_audio_sources, r, 1); r += 1
        cfg_audio = self._cfg.get("audio_device_index", None)
        if cfg_audio is None:
            self._audio_selector.set(SYSTEM_DEFAULT)
        elif cfg_audio == -1:
            self._audio_selector.set("No audio")
        else:
            for i, val in enumerate(self._available_audio_sources):
                if val.startswith(f"{cfg_audio}:"):
                    self._audio_selector.current(i)
                    break

        # ── Features ─────────────────────────────────────────────────────────────────────────────────────────────────
        _section_label(f, "FEATURES", r); r += 2
        self._motion = _check(f, "Enable motion detection", self._cfg.get("enable_motion_det", False), r, 0)
        self._caddy = _check(f, "Enable HTTPS with Caddy", self._cfg.get("use_caddy", False), r, 2); r += 1
        self._record = _check(f, "Enable recordings", self._cfg.get("enable_recordings", False), r, 0); r += 1

    def _build_controls(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.pack(fill="x", padx=20, pady=12)

        self._btn_browser_image = tk.PhotoImage(file=_resource("web.png")).subsample(2)
        self._btn_browser = tk.Button(frame, relief="flat", font=(FONT, 10, "bold"), command=self._open_web_interface,
                                      bg=GREEN, fg=BG, activebackground="#00c060", activeforeground=BG,
                                      padx=9, pady=9, cursor="hand2", bd=0, image=self._btn_browser_image)
        self._btn_browser.pack(side='right', padx=(5, 0))

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

        self._dot = tk.Label(header, text="●", bg=PANEL, fg=DIM, font=MONO)
        self._dot.pack(side="left", padx=(10, 0), pady=5)
        tk.Label(header, text="CONSOLE OUTPUT", bg=PANEL, fg=DIM, font=MONO_SM).pack(side="left", padx=(20, 0), pady=5)
        self._button_border = tk.Frame(header, highlightbackground=DIM, highlightthickness=1, bd=0)
        self._button_border.pack(side='right', padx=20)
        self._btn_clear = tk.Button(self._button_border, relief="flat", font=(FONT, 10, "bold"), command=self._clear_console,
                                    bg=PANEL, fg=DIM, activebackground=BG, activeforeground=DIM,
                                    padx=5, pady=5, cursor="hand2", bd=0, text='CLEAR')
        self._btn_clear.pack()

        self._console = scrolledtext.ScrolledText(console_panel, bg="#060809", fg=TEXT, font=(TERM, 8),
            relief="flat", bd=0, state="disabled", wrap="word", height=12)
        self._console.pack(fill="both", expand=True)
        self._console.tag_config("ok", foreground=GREEN)
        self._console.tag_config("err", foreground=RED)
        self._console.tag_config("warn", foreground=AMBER)
        self._console.tag_config("dim", foreground=DIM)

    # ── Server lifecycle ─────────────────────────────────────────────────────────────────────────────────────────────
    def _toggle(self):
        if self._proc is None:
            self._start()
        else:
            self._stop()

    def _build_cmd(self):
        # check camera device selected
        if len(self._camera_selector.get()) == 0:
            messagebox.showerror("Error", "Camera device not selected. Please select one, if available.")
            return None
        else:
            camera_index = self._camera_selector.get().split(':')[0]
            try:
                int(camera_index)
            except:
                messagebox.showerror("Error", "Camera device selected not valid.")
                return None
        
        # check audio device selected
        audio = self._audio_selector.get()
        if (len(audio) == 0) or (audio == "No audio"):
            self._log("No audio device selected, stream audio not available\n", "warn")
            audio_index = "-1"
        elif audio == SYSTEM_DEFAULT:
            audio_index = None
        else:
            audio_index = self._audio_selector.get().split(':')[0]
            try:
                int(audio_index)
            except:
                messagebox.showerror("Error", "Audio device selected not valid.")
                return None

        cmd = [sys.executable, "-m", "RemoteCameraMonitoring.server"]
        cmd += ["--camera", camera_index]
        if audio_index is not None:
            cmd += ["--audio-device", audio_index]
        cmd += ["--width", self._width.get().strip()]
        cmd += ["--height", self._height.get().strip()]
        cmd += ["--fps", self._fps.get().strip()]
        cmd += ["--port", self._port.get().strip()]
        
        pwd = self._pwd.get().strip()
        hash = self._hash.get().strip()
        # if the password is set, the user has just entered it, so prefer using it
        # unless the hash was generated by the user
        if self._hash_generated and hash:
            cmd += ["--password-hash", hash]
        elif pwd:
            cmd += ["--password", pwd]
        elif hash:
            cmd += ["--password-hash", hash]
        
        # HTTPS / SSL checks
        if self._has_ssl_cert and self._has_ssl_key:
            cmd += ["--ssl-cert", self._ssl_cert_file]
            cmd += ["--ssl-key", self._ssl_key_file]
        elif not self._caddy.get():
            self._log("No HTTPS connection will be available. Remote connections may not work on some devices\n", "warn")

        if self._motion.get():
            cmd.append("--motion")
        if self._record.get():
            cmd.append("--record")
        
        # check caddy executable if enabled
        if self._caddy.get():
            parent = os.path.abspath(os.path.join(_HERE, os.pardir))
            caddy_file = os.path.join(parent, "resources", "caddy.exe")
            if not os.path.exists(self._cfg["caddy_exe"]):
                messagebox.showerror("Error", f"Caddy executable not found in path:\n"
                                              f"{self._cfg["caddy_exe"]}\n"
                                              f"Please download it and place it in this folder.")
                return None
            
        # Save settings for next time
        self._save_settings(camera_index, audio_index)
            
        return cmd

    def _save_settings(self, camera_index, audio_index):
        try:
            self._cfg["camera_index"] = int(camera_index)
            self._cfg["audio_device_index"] = int(audio_index) if audio_index is not None and audio_index != "-1" else (None if audio_index is None else -1)
            self._cfg["stream_width"] = int(self._width.get())
            self._cfg["stream_height"] = int(self._height.get())
            self._cfg["stream_fps"] = int(self._fps.get())
            self._cfg["flask_port"] = int(self._port.get())
            self._cfg["login_password_hash"] = self._hash.get().strip()
            self._cfg["ssl_cert"] = self._ssl_cert_file
            self._cfg["ssl_key"] = self._ssl_key_file
            self._cfg["enable_motion_det"] = self._motion.get()
            self._cfg["enable_recordings"] = self._record.get()
            self._cfg["use_caddy"] = self._caddy.get()
            # TODO select a path for Caddy executable and store it in config
            save_config(self._cfg)
        except Exception as e:
            self._log(f"Error saving config: {e}\n", "err")

    def _start(self):
        cmd = self._build_cmd()
        if cmd is None:
            return
        # Log the command with the password masked
        display = [("●●●●" if i > 0 and (cmd[i - 1] == "--password" or cmd[i - 1] == "--password-hash") else c)
                   for i, c in enumerate(cmd)]
        self._log(f"$ {' '.join(display)}\n", "dim")
        # Use module invocation so relative imports work whether the package is
        # installed (pip install) or run from source (PYTHONPATH set below).
        pkg_root = os.path.dirname(_HERE)  # directory that contains RemoteCameraMonitoring/
        # Ensure the package root is importable in the subprocess (needed
        # when running from source without 'pip install -e .').
        _env = os.environ.copy()
        pythonpath = _env.get("PYTHONPATH", "")
        if pkg_root not in pythonpath.split(os.pathsep):
            _env["PYTHONPATH"] = pkg_root + (os.pathsep + pythonpath if pythonpath else "")
        try:
            self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1, env=_env)
        except Exception as exc:
            self._log(f"Error: {exc}\n", "err")
            return

        self._btn_var.set("■   STOP SERVER")
        self._btn.config(bg=RED, activebackground="#cc2020")
        self._dot.config(fg=GREEN)

        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    def _stop(self):
        terminated = False
        if self._proc:
            if PLATFORM == "Windows":
                # Kill the process and all its children (e.g. caddy.exe) using taskkill
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    self._proc.terminate()
            else:
                self._proc.terminate()
                
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None
            terminated = True
            
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=1)
            self._reader = None
        
        if terminated:
            self._set_stopped()
            self._log("— Server stopped —\n", "warn")

    def _set_stopped(self):
        self._proc = None
        self._btn_var.set("▶   START SERVER")
        self._btn.config(bg=GREEN, activebackground="#00c060")
        self._dot.config(fg=DIM)

    # ── Output reader (background thread) ───────────────────────────────────────────────────────────────────────────
    def _read_output(self):
        try:
            if self._proc is not None:
                if self._proc.stdout is not None:
                    for line in self._proc.stdout:
                        self._q.put(line)
        except Exception:
            pass
        finally:
            self._q.put(None)  # sentinel: process ended

    # ── Queue poller (main thread, via after()) ──────────────────────────────────────────────────────────────────────
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
            self._console.config(state="normal")
            self._console.delete('1.0', f'{to_delete}.0')
            self._console.config(state="disabled")

    # ── Window close ─────────────────────────────────────────────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop()
        self.destroy()

# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# ── Entry Point ──────────────────────────────────────────────────────────────────────────────────────────────────────
# ═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

def main():
    """Launch the remote camera GUI, enumerating local cameras and audio devices."""
    print("=" * 80)
    print("RemoteCamera GUI Launcher")
    print("=" * 80)
    print("Run with:\tpython gui.py")
    print("\nServer Local Access: http://localhost:port")
    print("Server Remote Access: http://<public-ip>:port")
    print("=" * 80)

    # Enumerate cameras — friendly names on Windows, index-based elsewhere
    camera_names = list_camera_names()
    available_cameras = [f"{index}: {name}" for index, name in enumerate(camera_names)]
    # Enumerate audio input devices via sounddevice (cross-platform)
    available_audio_sources = [SYSTEM_DEFAULT]
    available_audio_sources += list_audio_input_names()
    available_audio_sources.append("No audio")

    app = ServerLauncher(available_cameras, available_audio_sources)
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()


if __name__ == "__main__":
    sys.exit(main())
