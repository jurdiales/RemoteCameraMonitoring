from dataclasses import dataclass

import cv2

@dataclass
class CameraInfo:
    port: int
    width: int
    height: int
    fps: int


def list_cameras() -> tuple:
    """
    Test the cameras and returns a tuple with the available cameras 
    and the ones that are working.
    """
    is_working = True
    dev_port = 0
    working_cameras = []
    available_cameras = []
    while is_working:
        camera = cv2.VideoCapture(dev_port)
        if not camera.isOpened():
            is_working = False
        else:
            is_reading, _ = camera.read()
            w = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(camera.get(cv2.CAP_PROP_FPS))
            if is_reading:
                print("Port %s is working and reads images (%s x %s)" %(dev_port, h, w))
                working_cameras.append(CameraInfo(port=dev_port, width=w, height=h, fps=fps))
            else:
                print("Port %s for camera ( %s x %s) is present but does not reads." %(dev_port, h, w))
                available_cameras.append(dev_port)
        dev_port +=1
    return available_cameras, working_cameras


def select_camera() -> int | None:
    _, working_cameras = list_cameras()
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
