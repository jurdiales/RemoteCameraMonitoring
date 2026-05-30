"""
Remote Camera Monitoring System — Main Server Entry Point
=========================================================
Requisites: pip install flask opencv-python numpy aiortc av sounddevice
Use: python -m RemoteCameraMonitoring.server [options]
Local Access: http://localhost:port
Remote Access: http://<public-ip>:port
"""

import argparse
import atexit
import os
import socket
import ssl
import subprocess
import threading

try:
    from . import state
    from .capture import camera_worker
    from .webrtc import start_aiortc_loop, pcs, cleanup as cleanup_webrtc
    from .routes import app
    from .utils import list_cameras_opencv
    from .password import hash_password
    from .config import load_config, resolve_caddy_executable
except ImportError:
    import state
    from capture import camera_worker
    from webrtc import start_aiortc_loop, pcs, cleanup as cleanup_webrtc
    from routes import app
    from utils import list_cameras_opencv
    from password import hash_password
    from config import load_config, resolve_caddy_executable

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.abspath(os.path.join(_HERE, os.pardir))
_cfg = load_config()
_caddy_proc = None


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def _valid_port(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("must be in range 1..65535")
    return parsed


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def _cleanup_caddy():
    global _caddy_proc
    if _caddy_proc:
        try:
            _caddy_proc.terminate()
            _caddy_proc.wait(timeout=2)
        except Exception:
            try:
                _caddy_proc.kill()
            except Exception:
                pass


atexit.register(_cleanup_caddy)
atexit.register(cleanup_webrtc)


# ══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════
def main():
    global _caddy_proc

    parser = argparse.ArgumentParser(description="RemoteCamera — headless server")
    parser.add_argument("-s", "--setup", action="store_true", help="Run camera setup utility", required=False)
    parser.add_argument("-c", "--camera", type=_non_negative_int, default=state.CAMERA_INDEX, help="Camera index")
    parser.add_argument("--width", type=_positive_int, default=state.STREAM_WIDTH, help="Stream width in pixels")
    parser.add_argument("--height", type=_positive_int, default=state.STREAM_HEIGHT, help="Stream height in pixels")
    parser.add_argument("--fps", type=_positive_int, default=state.STREAM_FPS, help="Stream frames per second")
    parser.add_argument("-a", "--audio-device", type=int, default=None, help="Audio input device index (default: system default)")
    parser.add_argument("-r", "--record", action="store_true", default=state.ENABLE_RECORDINGS, help="Enable recordings")
    parser.add_argument("-m", "--motion", action="store_true", default=state.ENABLE_MOTION_DET, help="Enable motion detection")
    parser.add_argument("-p", "--port", type=_valid_port, default=state.FLASK_PORT, help="Flask server port")
    parser.add_argument("--password", type=str, default=None, metavar="PWD", help="Password to protect the web interface (leave empty to disable)")
    parser.add_argument("--password-hash", type=str, default=None, metavar="HASH", help="Precomputed password hash; or set REMOTE_CAMERA_PASSWORD_HASH instead")
    parser.add_argument("--ssl-cert", type=str, default=None, metavar="PATH", help="Path to TLS certificate file for HTTPS")
    parser.add_argument("--ssl-key", type=str, default=None, metavar="PATH", help="Path to TLS private key file for HTTPS")
    args = parser.parse_args()

    if args.setup:
        print("Running camera setup utility...")
        available, working = list_cameras_opencv()
        if len(working) == 0 and len(available) == 0:
            print("No cameras found. Please connect a camera and try again.")
            exit(0)
        if len(working) == 0:
            print("No working cameras found. Please check your connections and try again.")
            if len(available) > 0:
                print("\nAvailable camera ports (present but not reading):", available)
        else:
            print("Working cameras (present and reading):")
            for idx, cam in enumerate(working):
                print(f"\t{idx + 1}: Camera at port {cam.port} with resolution {cam.width}x{cam.height}")
        exit(0)

    # Apply CLI overrides to shared state
    state.CAMERA_INDEX = args.camera
    state.STREAM_WIDTH = args.width
    state.STREAM_HEIGHT = args.height
    state.STREAM_FPS = args.fps
    if args.audio_device is not None:
        state.AUDIO_DEVICE_INDEX = args.audio_device
    state.ENABLE_RECORDINGS = args.record
    state.ENABLE_MOTION_DET = args.motion
    state.FLASK_PORT = args.port

    env_hash = os.getenv(state.PASSWORD_HASH_ENV, "")
    if args.password:
        print("[!] WARNING: --password is visible in the process list (ps aux).")
        print("    Prefer --password-hash or the REMOTE_CAMERA_PASSWORD_HASH env var.")
        state.LOGIN_PASSWORD_HASH = hash_password(args.password)
    elif args.password_hash:
        state.LOGIN_PASSWORD_HASH = args.password_hash
    elif env_hash:
        state.LOGIN_PASSWORD_HASH = env_hash
    else:
        state.LOGIN_PASSWORD_HASH = ""

    if (args.ssl_cert and not args.ssl_key) or (args.ssl_key and not args.ssl_cert):
        parser.error("Both --ssl-cert and --ssl-key are required to enable HTTPS")

    ssl_context = None
    use_caddy = _cfg.get("use_caddy", False)
    if not use_caddy and args.ssl_cert and args.ssl_key:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(args.ssl_cert, args.ssl_key)

    # Mark session cookie Secure when served over TLS
    if use_caddy or ssl_context:
        app.config["SESSION_COOKIE_SECURE"] = True

    # Re-compute RECORDINGS_DIR in case CWD changed
    state.RECORDINGS_DIR = os.path.join(os.getcwd(), "recordings")
    os.makedirs(state.RECORDINGS_DIR, exist_ok=True)

    # ── Banner ────────────────────────────────────────────────
    _audio_label = f"device index {state.AUDIO_DEVICE_INDEX}" if state.AUDIO_DEVICE_INDEX is not None else "system default"
    if state.LOGIN_PASSWORD_HASH:
        _auth_label = "enabled (hashed password configured)"
    else:
        _auth_label = "DISABLED (no password set)"
    _https_label = (
        "https://localhost" if use_caddy
        else f"https://localhost:{state.FLASK_PORT}" if ssl_context
        else f"http://localhost:{state.FLASK_PORT}"
    )

    print("=" * 55)
    print("  Remote Camera Monitoring System")
    print("=" * 55)
    print(f"  Camera:        index {state.CAMERA_INDEX}")
    print(f"  Resolution:    {state.STREAM_WIDTH}x{state.STREAM_HEIGHT} @ {state.STREAM_FPS}fps")
    print(f"  Microphone:    {_audio_label}")
    print(f"  Auth:          {_auth_label}")
    print(f"  Recordings:    {state.RECORDINGS_DIR}")
    print(f"  Local access:  {_https_label}")
    print("  Remote access: see SETUP.md")
    print("=" * 55)

    # ── Caddy reverse proxy (optional) ────────────────────────
    if use_caddy:
        local_ip = get_local_ip()
        caddyfile_path = os.path.join(_PARENT, "resources", "Caddyfile")
        caddy_content = f"""localhost {{
    reverse_proxy localhost:{state.FLASK_PORT}
}}

# local network IP
{local_ip} {{
    tls internal
    reverse_proxy localhost:{state.FLASK_PORT}
}}
"""
        with open(caddyfile_path, "w") as f:
            f.write(caddy_content)

        print(f"[*] Starting Caddy server for https://localhost and https://{local_ip}...")
        success = False
        try:
            caddy_cfg = _cfg.get("caddy_exe", "")
            caddy_exe = resolve_caddy_executable(caddy_cfg)
            if caddy_exe:
                _cfg["caddy_exe"] = caddy_exe
                _caddy_proc = subprocess.Popen(
                    [caddy_exe, "run", "--config", caddyfile_path],
                    cwd=_PARENT,
                )
                success = True
            else:
                if caddy_cfg:
                    print(f"[!] Caddy executable not found: {caddy_cfg}")
                else:
                    print("[!] Caddy executable not configured.")
                print("    Install Caddy and add it to PATH, or set caddy_exe in config.")
        except Exception as e:
            print(f"[!] Failed to start Caddy: {e}")

        if not success:
            if args.ssl_cert and args.ssl_key:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(args.ssl_cert, args.ssl_key)
                print("[!] WARNING: Using SSL context without Caddy.")
            else:
                print("[!] WARNING: No SSL context will be available.")

    # ── Start background threads ──────────────────────────────
    t = threading.Thread(target=camera_worker, args=(lambda: len(pcs),), daemon=True)
    t.start()

    aiortc_thread = threading.Thread(target=start_aiortc_loop, daemon=True)
    aiortc_thread.start()

    app.run(host="0.0.0.0", port=state.FLASK_PORT, threaded=True, debug=False,
            use_reloader=False, ssl_context=ssl_context)


if __name__ == "__main__":
    main()
