import json
import os

CONFIG_FILE = "config.json"
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.abspath(os.path.join(_HERE, os.pardir))

DEFAULT_CONFIG = {
    # camera
    "camera_index": 0,
    "stream_width": 1280,
    "stream_height": 720,
    "stream_fps": 20,
    "flask_port": 8090,
    # audio
    "audio_device_index": None,
    "audio_sample_rate": 48000,
    "audio_channels": 1,
    "audio_chunk_frames": 960,
    # motion detection
    "enable_motion_det": False,
    "motion_threshold": 4000,
    "min_contour_area": 400,
    "record_seconds": 15,
    "blur_kernel": [21, 21],
    "dilation_kernel": [5, 5],
    # video recording
    "enable_recordings": False,
    "max_recordings": 50,
    # authentication
    "login_password_hash": "",
    "ssl_cert": "",
    "ssl_key": "",
    "use_caddy": False,
    "caddy_exe": os.path.join(_PARENT, "resources", "caddy.exe")
}

def load_config():
    """Loads configuration from config.json, merging with defaults."""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception as e:
            print(f"Error loading config file: {e}")
    return config

def save_config(config):
    """Saves the given configuration dictionary to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config file: {e}")
