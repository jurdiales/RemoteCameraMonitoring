"""
RemoteCamera — PySide6 QML Launcher
===================================
A modern PySide6 & QML interface to configure and launch the monitoring server.
Run with: python -m RemoteCameraMonitoring.qtgui
"""

import os
import sys
import platform
import webbrowser

# Force Basic styling to allow customized dark theme QML controls
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PySide6.QtCore import QObject, Signal, Slot, Property, QProcess, QProcessEnvironment
from PySide6.QtGui import QGuiApplication, QClipboard
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QFileDialog

try:
    from . import server as srv
    from .utils import list_camera_names, list_audio_input_names
    from .config import load_config, save_config
    from .password import hash_password
except ImportError:
    import server as srv
    from utils import list_camera_names, list_audio_input_names
    from config import load_config, save_config
    from password import hash_password

PLATFORM = platform.system()
if PLATFORM == 'Windows':
    import ctypes
    myappid = 'mycompany.remotecameramonitoring.subproduct.version'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

_HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DEFAULT = "System default"

class ServerBackend(QObject):
    # Signals to notify QML of state changes
    isRunningChanged = Signal(bool)
    statusTextChanged = Signal(str)
    statusColorChanged = Signal(str)
    camerasChanged = Signal()
    audioDevicesChanged = Signal()
    
    # Settings Properties Signals
    selectedCameraChanged = Signal(str)
    selectedAudioChanged = Signal(str)
    streamWidthChanged = Signal(str)
    streamHeightChanged = Signal(str)
    fpsChanged = Signal(str)
    portChanged = Signal(str)
    passwordChanged = Signal(str)
    passwordHashChanged = Signal(str)
    sslCertChanged = Signal(str)
    sslKeyChanged = Signal(str)
    motionChanged = Signal(bool)
    caddyChanged = Signal(bool)
    recordingsChanged = Signal(bool)
    
    # Core Log Signal
    logReceived = Signal(str, str) # text, tag (info/ok/err/warn)

    def __init__(self):
        super().__init__()
        self._cfg = load_config()
        self._process = None
        self._hash_generated = False
        
        # Populate available devices
        camera_names = list_camera_names()
        self._cameras = [f"{index}: {name}" for index, name in enumerate(camera_names)]
        
        self._audio_devices = [SYSTEM_DEFAULT]
        self._audio_devices.extend(list_audio_input_names())
        self._audio_devices.append("No audio")
        
        # Read from config and populate properties
        self._selected_camera = ""
        cfg_cam = self._cfg.get("camera_index", 0)
        for val in self._cameras:
            if val.startswith(f"{cfg_cam}:"):
                self._selected_camera = val
                break
        if not self._selected_camera and self._cameras:
            self._selected_camera = self._cameras[0]

        self._selected_audio = SYSTEM_DEFAULT
        cfg_audio = self._cfg.get("audio_device_index", None)
        if cfg_audio is None:
            self._selected_audio = SYSTEM_DEFAULT
        elif cfg_audio == -1:
            self._selected_audio = "No audio"
        else:
            for val in self._audio_devices:
                if val.startswith(f"{cfg_audio}:"):
                    self._selected_audio = val
                    break

        self._stream_width = str(self._cfg.get("stream_width", 1280))
        self._stream_height = str(self._cfg.get("stream_height", 720))
        self._fps = str(self._cfg.get("stream_fps", 20))
        self._port = str(self._cfg.get("flask_port", 8090))
        
        self._password = ""
        self._password_hash = os.getenv(srv.PASSWORD_HASH_ENV, self._cfg.get("login_password_hash", ""))
        
        self._ssl_cert = self._cfg.get("ssl_cert", "")
        if self._ssl_cert and not os.path.exists(self._ssl_cert):
            self._ssl_cert = ""
            
        self._ssl_key = self._cfg.get("ssl_key", "")
        if self._ssl_key and not os.path.exists(self._ssl_key):
            self._ssl_key = ""
            
        self._motion = bool(self._cfg.get("enable_motion_det", False))
        self._caddy = bool(self._cfg.get("use_caddy", False))
        self._recordings = bool(self._cfg.get("enable_recordings", False))
        
        self._is_running = False
        self._status_text = "Stopped"
        self._status_color = "#4a5060" # DIM

    # --- Properties Exposed to QML ---
    @Property(bool, notify=isRunningChanged)
    def isRunning(self):
        return self._is_running

    @Property(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @Property(str, notify=statusColorChanged)
    def statusColor(self):
        return self._status_color

    @Property(list, notify=camerasChanged)
    def cameras(self):
        return self._cameras

    @Property(list, notify=audioDevicesChanged)
    def audioDevices(self):
        return self._audio_devices

    @Property(str, notify=selectedCameraChanged)
    def selectedCamera(self):
        return self._selected_camera

    @selectedCamera.setter
    def selectedCamera(self, val):
        if self._selected_camera != val:
            self._selected_camera = val
            self.selectedCameraChanged.emit(val)

    @Property(str, notify=selectedAudioChanged)
    def selectedAudio(self):
        return self._selected_audio

    @selectedAudio.setter
    def selectedAudio(self, val):
        if self._selected_audio != val:
            self._selected_audio = val
            self.selectedAudioChanged.emit(val)

    @Property(str, notify=streamWidthChanged)
    def streamWidth(self):
        return self._stream_width

    @streamWidth.setter
    def streamWidth(self, val):
        if self._stream_width != val:
            self._stream_width = val
            self.streamWidthChanged.emit(val)

    @Property(str, notify=streamHeightChanged)
    def streamHeight(self):
        return self._stream_height

    @streamHeight.setter
    def streamHeight(self, val):
        if self._stream_height != val:
            self._stream_height = val
            self.streamHeightChanged.emit(val)

    @Property(str, notify=fpsChanged)
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, val):
        if self._fps != val:
            self._fps = val
            self.fpsChanged.emit(val)

    @Property(str, notify=portChanged)
    def port(self):
        return self._port

    @port.setter
    def port(self, val):
        if self._port != val:
            self._port = val
            self.portChanged.emit(val)

    @Property(str, notify=passwordChanged)
    def password(self):
        return self._password

    @password.setter
    def password(self, val):
        if self._password != val:
            self._password = val
            self.passwordChanged.emit(val)

    @Property(str, notify=passwordHashChanged)
    def passwordHash(self):
        return self._password_hash

    @passwordHash.setter
    def passwordHash(self, val):
        if self._password_hash != val:
            self._password_hash = val
            self.passwordHashChanged.emit(val)

    @Property(str, notify=sslCertChanged)
    def sslCert(self):
        return self._ssl_cert

    @sslCert.setter
    def sslCert(self, val):
        if self._ssl_cert != val:
            self._ssl_cert = val
            self.sslCertChanged.emit(val)

    @Property(str, notify=sslKeyChanged)
    def sslKey(self):
        return self._ssl_key

    @sslKey.setter
    def sslKey(self, val):
        if self._ssl_key != val:
            self._ssl_key = val
            self.sslKeyChanged.emit(val)

    @Property(bool, notify=motionChanged)
    def motion(self):
        return self._motion

    @motion.setter
    def motion(self, val):
        if self._motion != val:
            self._motion = val
            self.motionChanged.emit(val)

    @Property(bool, notify=caddyChanged)
    def caddy(self):
        return self._caddy

    @caddy.setter
    def caddy(self, val):
        if self._caddy != val:
            self._caddy = val
            self.caddyChanged.emit(val)

    @Property(bool, notify=recordingsChanged)
    def recordings(self):
        return self._recordings

    @recordings.setter
    def recordings(self, val):
        if self._recordings != val:
            self._recordings = val
            self.recordingsChanged.emit(val)

    # --- Slots Exposed to QML ---
    @Slot()
    def toggleServer(self):
        if self._is_running:
            self.stopServer()
        else:
            self.startServer()

    @Slot()
    def generateHash(self):
        pwd = self._password.strip()
        if pwd:
            hashed = hash_password(pwd)
            self.passwordHash = hashed
            self._hash_generated = True
            
            # Copy to clipboard
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(hashed)
            self.logReceived.emit("[GUI] Hashed password generated and copied to clipboard.\n", "ok")
        else:
            self._hash_generated = False
            self.logReceived.emit("[GUI] Password cannot be empty to generate hash.\n", "err")

    @Slot()
    def selectCertFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Open Certificate File", _HERE, "SSL/TLS Certificates (*.pem);;All Files (*)"
        )
        if file_path:
            self.sslCert = file_path

    @Slot()
    def selectKeyFile(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Open Key File", _HERE, "SSL/TLS Certificates (*.pem);;All Files (*)"
        )
        if file_path:
            self.sslKey = file_path

    @Slot()
    def openBrowser(self):
        if self._caddy:
            url = "https://localhost"
        elif self._ssl_cert and self._ssl_key:
            url = f"https://localhost:{self._port}"
        else:
            url = f"http://localhost:{self._port}"
        webbrowser.open(url)
        self.logReceived.emit(f"[GUI] Opening web interface: {url}\n", "info")

    # --- Core Server Operations ---
    def _build_cmd(self):
        # Validate camera selection
        if not self._selected_camera:
            self.logReceived.emit("[Error] Camera device not selected.\n", "err")
            return None
        camera_index = self._selected_camera.split(':')[0]
        try:
            int(camera_index)
        except ValueError:
            self.logReceived.emit("[Error] Camera device selected is not valid.\n", "err")
            return None

        # Validate audio selection
        audio = self._selected_audio
        if not audio or audio == "No audio":
            self.logReceived.emit("No audio device selected, stream audio not available.\n", "warn")
            audio_index = "-1"
        elif audio == SYSTEM_DEFAULT:
            audio_index = None
        else:
            audio_index = audio.split(':')[0]
            try:
                int(audio_index)
            except ValueError:
                self.logReceived.emit("[Error] Audio device selected is not valid.\n", "err")
                return None

        cmd = [sys.executable, "-m", "RemoteCameraMonitoring.server"]
        cmd += ["--camera", camera_index]
        if audio_index is not None:
            cmd += ["--audio-device", audio_index]
        cmd += ["--width", self._stream_width.strip()]
        cmd += ["--height", self._stream_height.strip()]
        cmd += ["--fps", self._fps.strip()]
        cmd += ["--port", self._port.strip()]

        pwd = self._password.strip()
        hash_val = self._password_hash.strip()
        if self._hash_generated and hash_val:
            cmd += ["--password-hash", hash_val]
        elif pwd:
            cmd += ["--password", pwd]
        elif hash_val:
            cmd += ["--password-hash", hash_val]

        if self._ssl_cert and self._ssl_key:
            cmd += ["--ssl-cert", self._ssl_cert]
            cmd += ["--ssl-key", self._ssl_key]
        elif not self._caddy:
            self.logReceived.emit("No HTTPS connection will be available. Remote connections may not work on some devices.\n", "warn")

        if self._motion:
            cmd.append("--motion")
        if self._recordings:
            cmd.append("--record")

        # Caddy executable check
        if self._caddy:
            if not os.path.exists(self._cfg.get("caddy_exe", "")):
                self.logReceived.emit(f"[Error] Caddy executable not found in path:\n{self._cfg.get('caddy_exe', '')}\nPlease download and place it in the resources folder.\n", "err")
                return None

        # Save configuration
        self._save_settings(camera_index, audio_index)
        return cmd

    def _save_settings(self, camera_index, audio_index):
        try:
            self._cfg["camera_index"] = int(camera_index)
            self._cfg["audio_device_index"] = int(audio_index) if audio_index is not None and audio_index != "-1" else (None if audio_index is None else -1)
            self._cfg["stream_width"] = int(self._stream_width)
            self._cfg["stream_height"] = int(self._stream_height)
            self._cfg["stream_fps"] = int(self._fps)
            self._cfg["flask_port"] = int(self._port)
            self._cfg["login_password_hash"] = self._password_hash.strip()
            self._cfg["ssl_cert"] = self._ssl_cert
            self._cfg["ssl_key"] = self._ssl_key
            self._cfg["enable_motion_det"] = self._motion
            self._cfg["enable_recordings"] = self._recordings
            self._cfg["use_caddy"] = self._caddy
            save_config(self._cfg)
        except Exception as e:
            self.logReceived.emit(f"[Error] Failed to save config: {e}\n", "err")

    def startServer(self):
        cmd = self._build_cmd()
        if cmd is None:
            self._set_stopped("Error starting", "#ff3d3d")
            return

        display_cmd = [("●●●●" if i > 0 and (cmd[i - 1] == "--password" or cmd[i - 1] == "--password-hash") else c)
                       for i, c in enumerate(cmd)]
        self.logReceived.emit(f"$ {' '.join(display_cmd)}\n", "info")

        pkg_root = os.path.dirname(_HERE)
        _env = os.environ.copy()
        pythonpath = _env.get("PYTHONPATH", "")
        if pkg_root not in pythonpath.split(os.pathsep):
            _env["PYTHONPATH"] = pkg_root + (os.pathsep + pythonpath if pythonpath else "")

        self._process = QProcess()
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        
        # Configure process environment
        q_env = QProcessEnvironment()
        for k, v in _env.items():
            q_env.insert(k, v)
        self._process.setProcessEnvironment(q_env)

        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_process_finished)

        # Launch process
        self._process.start(cmd[0], cmd[1:])
        
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self.logReceived.emit("[Error] Process failed to start.\n", "err")
            self._set_stopped("Error", "#ff3d3d")
            return

        self._is_running = True
        self.isRunningChanged.emit(True)
        self._status_text = "Running"
        self.statusTextChanged.emit(self._status_text)
        self._status_color = "#00e676" # GREEN
        self.statusColorChanged.emit(self._status_color)

    def stopServer(self):
        if not self._process:
            return

        self.logReceived.emit("[GUI] Stopping server process...\n", "warn")

        # Disconnect finished BEFORE killing so _on_process_finished never fires
        # after a manual stop.  This also prevents the exit-code-1 log entry that
        # comes from taskkill's forced termination.
        try:
            self._process.finished.disconnect(self._on_process_finished)
        except RuntimeError:
            pass  # already disconnected
        try:
            self._process.readyReadStandardOutput.disconnect(self._read_output)
        except RuntimeError:
            pass

        if PLATFORM == "Windows":
            try:
                # Forcefully kill the process tree (including Caddy subprocesses)
                QProcess.execute("taskkill", ["/F", "/T", "/PID", str(self._process.processId())])
            except Exception:
                self._process.terminate()
        else:
            self._process.terminate()

        self._process.waitForFinished(2000)
        if self._process and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1000)

        self._set_stopped()
        self.logReceived.emit("\u2014 Server stopped —\n", "warn")

    def _set_stopped(self, text="Stopped", color="#4a5060"):
        self._is_running = False
        self.isRunningChanged.emit(False)
        self._status_text = text
        self.statusTextChanged.emit(text)
        self._status_color = color
        self.statusColorChanged.emit(color)
        self._process = None

    def _read_output(self):
        if not self._process:
            return
        data = self._process.readAllStandardOutput()
        text = data.data().decode("utf-8", errors="ignore")
        for line in text.splitlines():
            lo = line.lower()
            tag = "ok" if ("local access" in lo or "started" in lo) else \
                  "err" if ("error" in lo or "traceback" in lo or "exception" in lo) else \
                  "warn" if "warning" in lo else \
                  "info"
            self.logReceived.emit(line, tag)

    def _on_process_finished(self, exit_code, exit_status):
        # Only reached when the server exits on its own (not via stopServer).
        # stopServer() disconnects this signal before killing the process, so
        # we will never see a forced-kill exit code here.
        self.logReceived.emit("\u2014 Server process exited \u2014\n", "warn")
        self._set_stopped()

def main():
    app = QApplication(sys.argv)

    # Attach backend and engine to the app object so Python's GC cannot collect
    # them before QML teardown completes.  Local variables in main() are eligible
    # for collection as soon as app.exec() returns, which is too early — QML
    # bindings can still fire during engine shutdown and would see backend=null.
    app.backend = ServerBackend()
    app.engine  = QQmlApplicationEngine()
    app.engine.rootContext().setContextProperty("backend", app.backend)

    qml_file = os.path.join(_HERE, "resources", "main.qml")
    app.engine.load(qml_file)

    if not app.engine.rootObjects():
        sys.exit(-1)

    # Graceful shutdown: stop the server subprocess when the window is closed.
    root_window = app.engine.rootObjects()[0]
    root_window.closing.connect(app.backend.stopServer)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
