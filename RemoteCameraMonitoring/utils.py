from dataclasses import dataclass

import cv2
from pygrabber.dshow_graph import FilterGraph
import sounddevice as sd

# ── Cameras ──────────────────────────────────────────────────────────────────
def list_cameras():
    graph = FilterGraph()
    devices = graph.get_input_devices()
    print("📷 Available Cameras:")
    print(f"  {'Index':<6} {'Name'}")
    print(f"  {'─'*5}  {'─'*40}")
    for index, name in enumerate(devices):
        print(f"  {index:<6} {name}")
    return devices

# ── Audio Devices ─────────────────────────────────────────────────────────────
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
    MAX_CAMERA_PORTS = 10  # upper bound to prevent an infinite scan on systems with virtual cameras
    is_working = True
    dev_port = 0
    working_cameras = []
    available_cameras = []
    while is_working and dev_port < MAX_CAMERA_PORTS:
        camera = cv2.VideoCapture(dev_port)
        if not camera.isOpened():
            is_working = False
        else:
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
        dev_port += 1
    return available_cameras, working_cameras


def select_camera_opencv() -> int | None:
    _, working_cameras = list_cameras_opencv()
    if len(working_cameras) == 0:
        print("No working cameras found.")
        return None
    elif len(working_cameras) == 1:
        print(f"One working camera found: {working_cameras[0]}. Using it by default.")
        return working_cameras[0]
    else:
        print("Multiple working cameras found. Please select one:")
        for idx, cam in enumerate(working_cameras):
            print(f"{idx + 1}: Camera at port {cam.port} with resolution {cam.width}x{cam.height}")
        while True:
            try:
                choice = int(input("Enter the number of the camera to use: "))
                if 1 <= choice <= len(working_cameras):
                    return working_cameras[choice - 1]
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
