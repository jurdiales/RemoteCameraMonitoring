"""
Shared mutable state and configuration settings for the Remote Camera Monitoring system.

All modules import from here to access the camera frame, status flags,
and configuration values. This avoids circular imports and centralizes
the lock-protected global state.
"""

import collections
import datetime
import os
import threading

import numpy as np

try:
    from .config import load_config
except ImportError:
    from config import load_config

_cfg = load_config()

# ─────────────────────────────────────────────
#  SETTINGS (mutable — CLI args may override)
# ─────────────────────────────────────────────
CAMERA_INDEX        = _cfg.get("camera_index", 0)
STREAM_WIDTH        = _cfg.get("stream_width", 1280)
STREAM_HEIGHT       = _cfg.get("stream_height", 720)
STREAM_FPS          = _cfg.get("stream_fps", 20)
FLASK_PORT          = _cfg.get("flask_port", 8090)

# Audio
AUDIO_DEVICE_INDEX  = _cfg.get("audio_device_index", None)
AUDIO_SAMPLE_RATE   = _cfg.get("audio_sample_rate", 48000)
AUDIO_CHANNELS      = _cfg.get("audio_channels", 1)
AUDIO_CHUNK_FRAMES  = _cfg.get("audio_chunk_frames", 960)

# Motion detection
ENABLE_MOTION_DET   = _cfg.get("enable_motion_det", False)
MOTION_THRESHOLD    = _cfg.get("motion_threshold", 4000)
MIN_CONTOUR_AREA    = _cfg.get("min_contour_area", 400)
RECORD_SECONDS      = _cfg.get("record_seconds", 15)
BLUR_KERNEL         = tuple(_cfg.get("blur_kernel", [21, 21]))
DILATION_KERNEL     = np.ones(tuple(_cfg.get("dilation_kernel", (5, 5))), np.uint8)
ENABLE_ADAPTIVE_MOTION   = _cfg.get("enable_adaptive_motion", True)
MOTION_NOISE_ALPHA       = _cfg.get("motion_noise_alpha", 0.06)
MOTION_NOISE_MULTIPLIER  = _cfg.get("motion_noise_multiplier", 1.6)
MOTION_THRESHOLD_MIN_FACTOR = _cfg.get("motion_threshold_min_factor", 0.75)
MOTION_THRESHOLD_MAX_FACTOR = _cfg.get("motion_threshold_max_factor", 1.35)
MOTION_HOLD_SECONDS      = _cfg.get("motion_hold_seconds", 0.8)

# Video recording
ENABLE_RECORDINGS   = _cfg.get("enable_recordings", False)
RECORDINGS_DIR      = os.path.join(os.getcwd(), "recordings")
MAX_RECORDINGS      = _cfg.get("max_recordings", 50)

# Authentication
LOGIN_PASSWORD_HASH = _cfg.get("login_password_hash", "")
FLASK_SECRET_KEY   = _cfg.get("flask_secret_key", "")
PASSWORD_HASH_ENV   = "REMOTE_CAMERA_PASSWORD_HASH"
SECRET_KEY_ENV      = "REMOTE_CAMERA_SECRET_KEY"

# ─────────────────────────────────────────────
#  SHARED RUNTIME STATE
# ─────────────────────────────────────────────
lock             = threading.Lock()
current_frame    = None
current_jpeg     = None        # pre-encoded JPEG bytes (shared by MJPEG + WS consumers)
motion_active    = False
is_recording     = False
last_motion_ts   = None
event_log        = collections.deque(maxlen=100)
stats            = {"total_events": 0, "start_time": datetime.datetime.now()}
active_viewers   = 0
capture_stats    = {
    "read_failures_streak": 0,
    "read_failures_total": 0,
    "camera_reopens": 0,
    "avg_loop_ms": 0.0,
    "last_loop_ms": 0.0,
    "motion_area": 0.0,
    "adaptive_threshold": float(MOTION_THRESHOLD),
    "noise_floor": float(MOTION_THRESHOLD),
}

on_new_frame_callbacks = []
