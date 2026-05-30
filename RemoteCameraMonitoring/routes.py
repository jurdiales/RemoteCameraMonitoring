"""
Flask application, routes, authentication, and streaming endpoints.
"""

import datetime
import logging
import os
import secrets
import time
from functools import wraps

import importlib.resources as pkg_resources
from flask import Flask, Response, jsonify, render_template, request, session, redirect, send_from_directory
from flask_sock import Sock

try:
    from . import state
    from . import webrtc
    from .password import verify_password
except ImportError:
    import state
    import webrtc
    from password import verify_password

# ─────────────────────────────────────────────
#  Flask app setup
# ─────────────────────────────────────────────
try:
    _TEMPLATES_DIR = str(pkg_resources.files("RemoteCameraMonitoring").joinpath("templates"))
except ModuleNotFoundError:
    _TEMPLATES_DIR = "templates"

app = Flask(__name__, template_folder=_TEMPLATES_DIR)
_configured_secret = os.getenv(state.SECRET_KEY_ENV, state.FLASK_SECRET_KEY)
if _configured_secret:
    app.secret_key = _configured_secret
else:
    app.secret_key = secrets.token_hex(32)
    logging.getLogger(__name__).warning(
        "No persistent Flask secret key configured; sessions will reset on restart. "
        "Set REMOTE_CAMERA_SECRET_KEY or flask_secret_key in config."
    )
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
)
sock = Sock(app)


# ── CSRF token generation ──
@app.context_processor
def _inject_csrf():
    """Make csrf_token() available in all templates."""
    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(32)
        return session["_csrf_token"]
    return {"csrf_token": csrf_token}


# ─────────────────────────────────────────────
#  Authentication helpers
# ─────────────────────────────────────────────
def require_auth(f):
    """Gate a route behind the configured password. No-op when LOGIN_PASSWORD_HASH is empty."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if state.LOGIN_PASSWORD_HASH and not session.get("authenticated"):
            if request.path.startswith("/api/") or request.is_json:
                return jsonify({"error": "Unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


# ── Simple in-memory rate limiter for login attempts ──
_login_attempts = {}  # ip -> (count, first_attempt_time)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_TRACKED_IPS = 1024


def _prune_login_attempts(now: float):
    expired_ips = [
        ip for ip, (_, first_ts) in _login_attempts.items()
        if now - first_ts > _LOGIN_WINDOW_SECONDS
    ]
    for ip in expired_ips:
        _login_attempts.pop(ip, None)

    overflow = len(_login_attempts) - _LOGIN_MAX_TRACKED_IPS
    if overflow > 0:
        oldest_ips = sorted(
            _login_attempts.items(),
            key=lambda item: item[1][1],
        )[:overflow]
        for ip, _ in oldest_ips:
            _login_attempts.pop(ip, None)


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    _prune_login_attempts(now)
    if ip in _login_attempts:
        count, _ = _login_attempts[ip]
        return count >= _LOGIN_MAX_ATTEMPTS
    return False


def _record_failed_attempt(ip: str):
    now = time.time()
    _prune_login_attempts(now)
    if ip in _login_attempts:
        count, first_ts = _login_attempts[ip]
        _login_attempts[ip] = (count + 1, first_ts)
    else:
        _login_attempts[ip] = (1, now)
    _prune_login_attempts(now)


# ─────────────────────────────────────────────
#  Auth routes
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if not state.LOGIN_PASSWORD_HASH:
        return redirect("/")
    if request.method == "POST":
        token = request.form.get("_csrf_token", "")
        if not token or token != session.get("_csrf_token"):
            return render_template("login.html", error="Invalid request. Please try again."), 403
        client_ip = request.remote_addr or "unknown"
        if _is_rate_limited(client_ip):
            return render_template("login.html", error="Too many attempts. Try again later."), 429
        pwd = request.form.get("password", "")
        if verify_password(pwd, state.LOGIN_PASSWORD_HASH):
            _login_attempts.pop(client_ip, None)
            session.pop("_csrf_token", None)
            session["authenticated"] = True
            session["from_login"] = True
            return redirect("/")
        _record_failed_attempt(client_ip)
        return render_template("login.html", error="Incorrect password")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login" if state.LOGIN_PASSWORD_HASH else "/")


# ─────────────────────────────────────────────
#  Streaming helpers
# ─────────────────────────────────────────────
def _mjpeg_generator():
    with state.lock:
        state.active_viewers += 1
    try:
        while True:
            with state.lock:
                jpeg = state.current_jpeg

            if jpeg is None:
                time.sleep(0.05)
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            )
            time.sleep(1 / state.STREAM_FPS)
    finally:
        with state.lock:
            state.active_viewers -= 1


# ─────────────────────────────────────────────
#  Application routes
# ─────────────────────────────────────────────
@app.route("/health")
def health():
    """Unauthenticated health-check for monitoring tools and load balancers."""
    return jsonify({"status": "ok"}), 200


@app.route("/")
@require_auth
def index():
    from_login = session.pop("from_login", False)
    audio_enabled = not (state.AUDIO_DEVICE_INDEX is not None and state.AUDIO_DEVICE_INDEX == -1)
    return render_template("index.html", auth_enabled=bool(state.LOGIN_PASSWORD_HASH),
                           from_login=from_login, audio_enabled=audio_enabled)


@app.route("/stream")
@require_auth
def stream():
    """MJPEG fallback — kept for backward compatibility / direct URL access."""
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@sock.route("/ws/stream")
def ws_stream(ws):
    """WebSocket endpoint that pushes JPEG frames as binary messages."""
    if state.LOGIN_PASSWORD_HASH and not session.get("authenticated"):
        return

    with state.lock:
        state.active_viewers += 1

    try:
        while True:
            with state.lock:
                jpeg = state.current_jpeg

            if jpeg is None:
                time.sleep(0.05)
                continue

            ws.send(jpeg)
            time.sleep(1 / state.STREAM_FPS)
    except Exception:
        pass
    finally:
        with state.lock:
            state.active_viewers -= 1


@app.route("/offer", methods=["POST"])
@require_auth
def offer():
    data = request.get_json()
    if not data or "sdp" not in data or "type" not in data:
        return jsonify({"error": "Invalid SDP offer"}), 400
    try:
        answer = webrtc.run_coroutine(webrtc.handle_offer(data))
    except TimeoutError:
        return jsonify({"error": "WebRTC negotiation timed out"}), 504
    except Exception as e:
        logging.getLogger(__name__).error("WebRTC offer failed: %s", e)
        return jsonify({"error": "WebRTC setup failed"}), 500
    return jsonify(answer)


@app.route("/api/status")
@require_auth
def api_status():
    uptime = datetime.datetime.now() - state.stats["start_time"]
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m, s = divmod(rem, 60)
    with state.lock:
        return jsonify({
            "motion": state.motion_active,
            "recording": state.is_recording,
            "total_events": state.stats["total_events"],
            "uptime": f"{h:02d}:{m:02d}:{s:02d}",
            "events": list(state.event_log)[:20],
            "capture": dict(state.capture_stats),
            "port": state.FLASK_PORT,
        })


@app.route("/api/recordings")
@require_auth
def api_recordings():
    files = []
    for f in sorted(os.listdir(state.RECORDINGS_DIR), reverse=True):
        if f.endswith(".mp4"):
            path = os.path.join(state.RECORDINGS_DIR, f)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            files.append({"name": f, "size": f"{size_mb:.1f} MB"})
    return jsonify(files)


@app.route("/recordings/<path:filename>")
@require_auth
def download_recording(filename):
    """Serve a recorded MP4 file directly."""
    return send_from_directory(state.RECORDINGS_DIR, filename)

