import json
import os
import platform

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.abspath(os.path.join(_HERE, os.pardir))
CONFIG_ENV_VAR = "REMOTE_CAMERA_CONFIG"


def _get_user_config_dir() -> str:
    if os.name == "nt":
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "RemoteCameraMonitoring")
    if platform.system() == "Darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "RemoteCameraMonitoring")

    base = os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    return os.path.join(base, "RemoteCameraMonitoring")


def _get_default_config_file() -> str:
    project_config = os.path.join(_PARENT, "config.json")
    if os.path.isdir(_PARENT) and os.access(_PARENT, os.W_OK):
        return project_config
    return os.path.join(_get_user_config_dir(), "config.json")


CONFIG_FILE = os.getenv(CONFIG_ENV_VAR, _get_default_config_file())
LEGACY_CONFIG_FILE = os.path.join(os.getcwd(), "config.json")

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
    """Load configuration, merging persisted values with defaults."""
    config = DEFAULT_CONFIG.copy()
    config_file = CONFIG_FILE
    # Backward compatibility for setups still using a CWD-local config.json file.
    if not os.path.exists(config_file) and os.path.exists(LEGACY_CONFIG_FILE):
        config_file = LEGACY_CONFIG_FILE

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
        except Exception as e:
            print(f"Error loading config file ({config_file}): {e}")
    return config


def save_config(config):
    """Save the configuration dictionary to a deterministic location."""
    try:
        config_dir = os.path.dirname(CONFIG_FILE)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)

        # Restrict permissions to owner-only (contains password hash)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass  # Windows or restricted filesystem — best-effort
    except Exception as e:
        print(f"Error saving config file: {e}")
