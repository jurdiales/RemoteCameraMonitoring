"""
Remote Camera Monitoring System — Main Server
Featuring a motion detection system and video recording
=====================================================
Requisites: pip install flask opencv-python numpy aiortc av sounddevice
Use: python server.py [options]
Local Access: http://localhost:port
Remote Access: http://<public-ip>:port
"""

import cv2
import threading
import time
import datetime
import os
import argparse
import asyncio
import queue
import fractions

from flask import Flask, Response, jsonify, render_template_string, request
import numpy as np
from aiortc import RTCIceServer, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack, RTCConfiguration
import av
import sounddevice as sd
from utils import list_cameras

# ─────────────────────────────────────────────
#  SETTINGS
# ─────────────────────────────────────────────
CAMERA_INDEX        = 0             # 0 = main webcam, 1 = USB camera, etc. (depens on the system)
STREAM_WIDTH        = 1280          # frame width (adjust this setting if your camera doesn't support this resolution)
STREAM_HEIGHT       = 720           # frame height (adjust this setting if your camera doesn't support this resolution)
STREAM_FPS          = 20            # stream fps
FLASK_PORT          = 8090          # port for the web interface

# Audio
AUDIO_DEVICE_INDEX  = None          # None = system default mic; set to int to pick a specific device
AUDIO_SAMPLE_RATE   = 48000         # Hz  (48 kHz is the WebRTC standard)
AUDIO_CHANNELS      = 1            # 1 = mono, 2 = stereo
AUDIO_CHUNK_FRAMES  = 960           # samples per chunk (20 ms at 48 kHz — matches Opus frame size)

# Motion detection
ENABLE_MOTION_DET   = False         # enable motion detection
MOTION_THRESHOLD    = 4000          # total pixel area to consider for motion detection
MIN_CONTOUR_AREA    = 400           # minimum area of an individual contour to be taken into account
RECORD_SECONDS      = 15            # seconds it continues recording after detecting motion
BLUR_KERNEL         = (21, 21)      # smoothing to reduce false positives
DILATION_KERNEL     = np.ones((5, 5), np.uint8)    # dilation to connect motion areas

# Video recording
ENABLE_RECORDINGS   = False         # enable recording
RECORDINGS_DIR      = "recordings"  # name of the folder to store recordings
MAX_RECORDINGS      = 50            # maximum number of recordings to store
# ─────────────────────────────────────────────

app = Flask(__name__)
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Global status shared between threads
_lock             = threading.Lock()
_current_frame    = None
_motion_active    = False
_is_recording     = False
_last_motion_ts   = None
_event_log        = []              # list of dict {time, type}
_stats            = {"total_events": 0, "start_time": datetime.datetime.now()}


# ══════════════════════════════════════════════════════════════
#  MAIN THREAD
# ══════════════════════════════════════════════════════════════
def camera_worker():
    global _current_frame, _motion_active, _is_recording, _last_motion_ts

    # use CAP_DSHOW to improve Windows compatibility
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, STREAM_FPS)

    if not cap.isOpened():
        # Fallback without CAP_DSHOW
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)

    prev_gray = None
    video_writer = None
    record_until = None

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        now = datetime.datetime.now()

        # ── Motion detection ──────────────────────────
        motion  = False

        if ENABLE_MOTION_DET:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, BLUR_KERNEL, 0)

            if prev_gray is not None:
                delta = cv2.absdiff(prev_gray, gray)
                thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, DILATION_KERNEL, iterations=2)
                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                total_area = sum(cv2.contourArea(c) for c in contours)

                if total_area > MOTION_THRESHOLD:
                    motion       = True
                    record_until = now + datetime.timedelta(seconds=RECORD_SECONDS)

                    # Register event
                    if not _motion_active:
                        ts_str = now.strftime("%H:%M:%S")
                        with _lock:
                            _event_log.insert(0, {"time": ts_str, "type": "motion"})
                            if len(_event_log) > 100:
                                _event_log.pop()
                            _stats["total_events"] += 1
                        _last_motion_ts = now

                    # Draw rectangles over moving objects
                    height, width, _ = frame.shape
                    xmin, ymin, xmax, ymax = width, height, 0, 0
                    for c in contours:
                        if cv2.contourArea(c) > MIN_CONTOUR_AREA:
                            x, y, w, h = cv2.boundingRect(c)
                            # cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 230, 80), 2)
                            xmin = min(xmin, x)
                            ymin = min(ymin, y)
                            xmax = max(xmax, x + w)
                            ymax = max(ymax, y + h)
                    if xmax > 0 and ymax > 0:
                        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (38, 167, 255), 2)

            prev_gray = gray

        # ── Recording ────────────────────────────────────────
        currently_recording = ENABLE_RECORDINGS and record_until is not None and now < record_until

        if currently_recording:
            if video_writer is None:
                _cleanup_old_recordings()
                fname = os.path.join(
                    RECORDINGS_DIR,
                    f"mov_{now.strftime('%Y%m%d_%H%M%S')}.mp4"
                )
                fourcc       = cv2.VideoWriter.fourcc('H','2','6','4')
                actual_w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                video_writer = cv2.VideoWriter(fname, fourcc, STREAM_FPS, (actual_w, actual_h))
            video_writer.write(frame)
        else:
            if video_writer is not None:
                video_writer.release()
                video_writer = None

        # ── Screen overlay ────────────────────────────────────
        _draw_overlay(frame, now, motion, currently_recording)

        # ── Update global state ───────────────────────────────
        with _lock:
            _current_frame  = frame.copy()
            _motion_active  = motion
            _is_recording   = currently_recording

        time.sleep(1 / STREAM_FPS)

    cap.release()


def _draw_overlay(frame, ts, motion, recording):
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 48), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # Date and time
    cv2.putText(frame, ts.strftime("%d/%m/%Y  %H:%M:%S"), (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (220, 220, 220), 2)

    # Motion status
    if motion:
        label  = "MOVIMIENTO DETECTADO"
        color  = (0, 60, 255)
        # Red flshing border
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (0, 0, 220), 6)
    else:
        label = "EN VIVO"
        color = (0, 200, 80)

    cv2.putText(frame, label, (w - 340, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)

    # REC indicator
    if recording:
        cv2.circle(frame, (w - 28, h - 24), 8, (0, 0, 240), -1)
        cv2.putText(frame, "REC", (w - 62, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 240), 2)


def _cleanup_old_recordings():
    files = sorted(
        [f for f in os.listdir(RECORDINGS_DIR) if f.endswith(".mp4")],
        key=lambda f: os.path.getmtime(os.path.join(RECORDINGS_DIR, f))
    )
    while len(files) >= MAX_RECORDINGS:
        os.remove(os.path.join(RECORDINGS_DIR, files.pop(0)))


# ══════════════════════════════════════════════════════════════
#  WebRTC STREAM GENERATOR
# ══════════════════════════════════════════════════════════════
_pcs = set()
_aiortc_loop = asyncio.new_event_loop()


class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = None

        while frame is None:
            with _lock:
                if _current_frame is not None:
                    frame = _current_frame.copy()
            if frame is None:
                await asyncio.sleep(1 / STREAM_FPS)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(rgb_frame, format="rgb24") # pyright: ignore[reportArgumentType]
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


class MicrophoneAudioTrack(AudioStreamTrack):
    """
    Captures PCM audio from the system microphone using sounddevice and
    delivers av.AudioFrame objects to the WebRTC peer connection.
    Each chunk is AUDIO_CHUNK_FRAMES samples long (20 ms at 48 kHz),
    which matches the Opus codec's preferred frame size.
    """

    def __init__(self):
        super().__init__()
        self._queue: queue.Queue = queue.Queue(maxsize=50)
        self._pts   = 0

        # Open the input stream in a daemon thread so it doesn't block the
        # asyncio event loop.  The callback pushes raw PCM into _queue.
        self._stream = sd.InputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            dtype="int16",
            blocksize=AUDIO_CHUNK_FRAMES,
            device=AUDIO_DEVICE_INDEX,
            callback=self._sd_callback,
        )
        self._stream.start()

    def _sd_callback(self, indata, frames, time_info, status):
        """Called by sounddevice from a C audio thread — keep it fast."""
        if not self._queue.full():
            self._queue.put_nowait(indata.copy())

    async def recv(self):
        # Wait for a PCM chunk without blocking the event loop
        loop = asyncio.get_event_loop()
        pcm = await loop.run_in_executor(None, self._queue.get)

        # pcm shape: (AUDIO_CHUNK_FRAMES, AUDIO_CHANNELS), dtype int16
        # av expects shape (channels, samples) for 'fltp' or (1, samples) for s16
        samples = pcm.T  # (channels, frames)

        audio_frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono" if AUDIO_CHANNELS == 1 else "stereo")  # pyright: ignore[reportArgumentType]
        audio_frame.sample_rate = AUDIO_SAMPLE_RATE
        audio_frame.pts         = self._pts
        audio_frame.time_base   = fractions.Fraction(1, AUDIO_SAMPLE_RATE)
        self._pts              += AUDIO_CHUNK_FRAMES
        return audio_frame

    def stop(self):
        self._stream.stop()
        self._stream.close()
        super().stop()


def _start_aiortc_loop():
    asyncio.set_event_loop(_aiortc_loop)
    _aiortc_loop.run_forever()


async def _handle_offer(data):
    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    pc = RTCPeerConnection(
        configuration=RTCConfiguration(
            iceServers=[RTCIceServer("stun:stun.l.google.com:19302")]
        )
    )
    _pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed", "disconnected"):
            await pc.close()
            _pcs.discard(pc)

    pc.addTrack(CameraVideoTrack())
    pc.addTrack(MicrophoneAudioTrack())
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


def _run_coroutine(coro):
    return asyncio.run_coroutine_threadsafe(coro, _aiortc_loop).result()


# ══════════════════════════════════════════════════════════════
#  MJPEG STREAM GENERATOR
# ══════════════════════════════════════════════════════════════
def _mjpeg_generator():
    while True:
        with _lock:
            frame = _current_frame

        if frame is None:
            time.sleep(0.05)
            continue

        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )
        time.sleep(1 / STREAM_FPS)


# ══════════════════════════════════════════════════════════════
#  RUTAS FLASK
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/stream")
def stream():
    return Response(
        _mjpeg_generator(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/offer", methods=["POST"])
def offer():
    data = request.get_json()
    if not data or "sdp" not in data or "type" not in data:
        return jsonify({"error": "Invalid SDP offer"}), 400
    answer = _run_coroutine(_handle_offer(data))
    return jsonify(answer)


@app.route("/api/status")
def api_status():
    uptime = datetime.datetime.now() - _stats["start_time"]
    h, rem = divmod(int(uptime.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    with _lock:
        return jsonify({
            "motion": _motion_active,
            "recording": _is_recording,
            "total_events": _stats["total_events"],
            "uptime": f"{h:02d}:{m:02d}:{s:02d}",
            "events": _event_log[:20],
            "port": FLASK_PORT,
        })


@app.route("/api/recordings")
def api_recordings():
    files = []
    for f in sorted(os.listdir(RECORDINGS_DIR), reverse=True):
        if f.endswith(".mp4"):
            path = os.path.join(RECORDINGS_DIR, f)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            files.append({"name": f, "size": f"{size_mb:.1f} MB"})
    return jsonify(files)


# ══════════════════════════════════════════════════════════════
#  WEB INTERFACE
# ══════════════════════════════════════════════════════════════
HTML_PAGE = open("index.html", "r", encoding='utf-8').read()


# ══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--setup", action="store_true", help="Run camera setup utility", required=False)
    parser.add_argument("-c", "--camera", type=int, default=CAMERA_INDEX, help="Camera index")
    parser.add_argument("-r", "--record", action="store_true", default=ENABLE_RECORDINGS, help="Enable recordings")
    parser.add_argument("-m", "--motion", action="store_true", default=ENABLE_MOTION_DET, help="Enable motion detection")
    parser.add_argument("-p", "--port", type=int, default=FLASK_PORT, help="Flask server port")
    parser.add_argument("-a", "--audio-device", type=int, default=None, help="Audio input device index (default: system default)")
    args = parser.parse_args()

    if args.setup:
        print("Running camera setup utility...")
        available, working = list_cameras()
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

    CAMERA_INDEX = args.camera
    ENABLE_RECORDINGS = args.record
    ENABLE_MOTION_DET = args.motion
    FLASK_PORT = args.port
    if args.audio_device is not None:
        AUDIO_DEVICE_INDEX = args.audio_device

    _audio_label = f"device index {AUDIO_DEVICE_INDEX}" if AUDIO_DEVICE_INDEX is not None else "system default"

    print("=" * 55)
    print("  Remote Camera Monitoring System")
    print("=" * 55)
    print(f"  Camera:        index {CAMERA_INDEX}")
    print(f"  Resolution:    {STREAM_WIDTH}x{STREAM_HEIGHT} @ {STREAM_FPS}fps")
    print(f"  Microphone:    {_audio_label}")
    print(f"  Recordings:    ./{RECORDINGS_DIR}/")
    print(f"  Local access:  http://localhost:{FLASK_PORT}")
    print("  Remote access: see SETUP.md")
    print("=" * 55)

    t = threading.Thread(target=camera_worker, daemon=True)
    t.start()

    aiortc_thread = threading.Thread(target=_start_aiortc_loop, daemon=True)
    aiortc_thread.start()

    app.run(host="0.0.0.0", port=FLASK_PORT, threaded=True, use_reloader=False)
