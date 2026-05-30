import platform
from dataclasses import dataclass

import cv2
import sounddevice as sd

_OS = platform.system()
MAX_CAMERA_PORTS = 10  # upper bound to avoid excessive probing on systems with virtual cameras

# ── Cameras ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def list_cameras() -> list[str]:
    """Return human-readable camera names where possible.

    On Windows, pygrabber can return friendly DirectShow names, but it is not
    available on Linux or macOS.  We fall back to a plain OpenCV index scan on
    all platforms so the function works everywhere.
    """
    if _OS == "Windows":
        try:
            from pygrabber.dshow_graph import FilterGraph  # type: ignore[import]
            return FilterGraph().get_input_devices()
        except Exception:
            pass  # fall through to the generic scan

    # Generic: scan indices with OpenCV
    names: list[str] = []
    for idx in range(MAX_CAMERA_PORTS):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        names.append(f"Camera {idx}")
        cap.release()

    return names


def list_camera_names() -> list[str]:
    """Return a list of camera display names (friendly on Windows, generic elsewhere)."""
    if _OS == "Windows":
        try:
            from pygrabber.dshow_graph import FilterGraph  # type: ignore[import]
            return FilterGraph().get_input_devices()
        except Exception:
            pass

    names: list[str] = []
    for idx in range(MAX_CAMERA_PORTS):
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            cap.release()
            continue
        names.append(f"Camera {idx}")
        cap.release()
    return names


def list_audio_input_names() -> list[str]:
    """Return a list of audio *input* device display names (cross-platform via sounddevice).

    On Windows, results are filtered to the WASAPI host API only, which exposes
    one entry per physical device — matching the clean list that DirectShow gave.
    On Linux and macOS, all input devices are returned (PortAudio typically only
    has one host API on those platforms anyway).
    """
    # Find the WASAPI host API index (Windows only; None on other platforms)
    wasapi_index = None
    if _OS == "Windows":
        try:
            for i, api in enumerate(sd.query_hostapis()):
                if "wasapi" in api["name"].lower():  # type: ignore[index]
                    wasapi_index = i
                    break
        except Exception:
            pass  # fall through: show all devices

    result: list[str] = []
    for idx, device in enumerate(sd.query_devices()):
        if device["max_input_channels"] <= 0:  # type: ignore[index]
            continue
        # On Windows, skip non-WASAPI devices to avoid duplicates and virtual devices
        if wasapi_index is not None and device["hostapi"] != wasapi_index:  # type: ignore[index]
            continue
        result.append(f"{idx}: {device['name']}")  # type: ignore[index]
    return result


# ── Audio Devices ────────────────────────────────────────────────────────────────────────────────────────────────────
def list_audio_devices():
    devices = sd.query_devices()
    print("\n🎙️  Available Audio Devices:")
    print(f"  {'Index':<6} {'I/O':<5} {'Name'}")
    print(f"  {'─'*5}  {'─'*4}  {'─'*40}")
    for index, device in enumerate(devices):
        inputs  = device['max_input_channels']
        outputs = device['max_output_channels']
        if inputs > 0 and outputs > 0:
            io = "I+O"
        elif inputs > 0:
            io = "IN"
        else:
            io = "OUT"
        print(f"  {index:<6} {io:<5} {device['name']}")
    return devices

# ── OpenCV helpers ───────────────────────────────────────────────────────────────────────────────────────────────────
@dataclass
class CameraInfo:
    port: int
    width: int
    height: int
    fps: int


def list_cameras_opencv() -> tuple:
    """
    Test the cameras and returns a tuple with the available cameras 
    and the ones that are working.
    """
    working_cameras = []
    available_cameras = []
    for dev_port in range(MAX_CAMERA_PORTS):
        camera = cv2.VideoCapture(dev_port)
        if not camera.isOpened():
            camera.release()
            continue

        is_reading, _ = camera.read()
        w = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(camera.get(cv2.CAP_PROP_FPS))
        camera.release()  # release the handle so the camera is free for the main thread
        if is_reading:
            print("Port %s is working and reads images (%s x %s)" %(dev_port, h, w))
            working_cameras.append(CameraInfo(port=dev_port, width=w, height=h, fps=fps))
        else:
            print("Port %s for camera ( %s x %s) is present but does not reads." %(dev_port, h, w))
            available_cameras.append(dev_port)
    return available_cameras, working_cameras


def select_camera_opencv() -> int | None:
    _, working_cameras = list_cameras_opencv()
    if len(working_cameras) == 0:
        print("No working cameras found.")
        return None
    elif len(working_cameras) == 1:
        print(f"One working camera found: {working_cameras[0]}. Using it by default.")
        return working_cameras[0].port
    else:
        print("Multiple working cameras found. Please select one:")
        for idx, cam in enumerate(working_cameras):
            print(f"{idx + 1}: Camera at port {cam.port} with resolution {cam.width}x{cam.height}")
        while True:
            try:
                choice = int(input("Enter the number of the camera to use: "))
                if 1 <= choice <= len(working_cameras):
                    return working_cameras[choice - 1].port
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
