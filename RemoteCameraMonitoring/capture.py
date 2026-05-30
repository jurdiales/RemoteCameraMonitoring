"""
Camera capture, motion detection, overlay rendering, and recording logic.
"""

import datetime
import logging
import os
import platform
import time

import cv2
import numpy as np

try:
    from . import state
except ImportError:
    import state


MAX_CONSECUTIVE_READ_FAILURES = 30
MOTION_HOLD_SECONDS = 0.8


def _open_camera(index: int) -> cv2.VideoCapture:
    """Open a camera with the best available backend for the current OS."""
    _os = platform.system()
    if _os == "Windows":
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, 0]
    elif _os == "Linux":
        backends = [cv2.CAP_V4L2, 0]
    else:  # macOS and others
        backends = [cv2.CAP_AVFOUNDATION, 0]

    for backend in backends:
        cap = cv2.VideoCapture(index, backend) if backend != 0 else cv2.VideoCapture(index)
        if cap.isOpened():
            return cap
        cap.release()

    # Last-resort fallback
    return cv2.VideoCapture(index)


def is_camera_needed(pcs_count: int) -> bool:
    """Return True if at least one consumer needs the camera feed."""
    with state.lock:
        return state.ENABLE_MOTION_DET or (state.active_viewers > 0) or (pcs_count > 0)


def camera_worker(get_pcs_count):
    """Main camera loop. `get_pcs_count` is a callable returning len(_pcs)."""
    logger = logging.getLogger(__name__)
    cap = None
    prev_gray = None
    video_writer = None
    read_failures = 0
    prev_motion_state = False
    motion_hold_until = 0.0
    record_until_monotonic = 0.0

    while True:
        try:
            needed = is_camera_needed(get_pcs_count())
            target_fps = max(1, int(state.STREAM_FPS))
            target_period = 1.0 / target_fps

            if not needed:
                if cap is not None:
                    cap.release()
                    cap = None
                if video_writer is not None:
                    video_writer.release()
                    video_writer = None

                prev_gray = None
                read_failures = 0
                prev_motion_state = False
                motion_hold_until = 0.0
                record_until_monotonic = 0.0

                with state.lock:
                    state.current_frame = None
                    state.current_jpeg = None
                    state.motion_active = False
                    state.is_recording = False
                time.sleep(0.2)
                continue

            if cap is None:
                cap = _open_camera(state.CAMERA_INDEX)
                if cap is not None and cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, state.STREAM_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, state.STREAM_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, target_fps)
                    # Best effort: low capture buffer reduces latency on supported backends.
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                else:
                    if cap is not None:
                        cap.release()
                    cap = None
                    prev_gray = None
                    time.sleep(1.0)
                    continue

            ret, frame = cap.read()
            if not ret:
                read_failures += 1
                if read_failures >= MAX_CONSECUTIVE_READ_FAILURES:
                    logger.warning("Camera read failed %s times; reopening device", read_failures)
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    prev_gray = None
                    read_failures = 0
                time.sleep(0.05)
                continue

            read_failures = 0

            _frame_start = time.monotonic()
            now = datetime.datetime.now()
            now_monotonic = time.monotonic()

            # ── Motion detection ──────────────────────────
            motion = False
            motion_contours = []

            if state.ENABLE_MOTION_DET:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, state.BLUR_KERNEL, 0)

                if prev_gray is not None:
                    delta = cv2.absdiff(prev_gray, gray)
                    thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
                    thresh = cv2.dilate(thresh, state.DILATION_KERNEL, iterations=2)
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    motion_contours = [c for c in contours if cv2.contourArea(c) > state.MIN_CONTOUR_AREA]
                    total_area = sum(cv2.contourArea(c) for c in motion_contours)

                    if total_area > state.MOTION_THRESHOLD:
                        motion_hold_until = now_monotonic + MOTION_HOLD_SECONDS
                        record_until_monotonic = max(
                            record_until_monotonic,
                            now_monotonic + max(0, int(state.RECORD_SECONDS)),
                        )

                motion = now_monotonic < motion_hold_until
                if motion and not prev_motion_state:
                    ts_str = now.strftime("%H:%M:%S")
                    with state.lock:
                        state.event_log.appendleft({"time": ts_str, "type": "motion"})
                        state.stats["total_events"] += 1
                    state.last_motion_ts = now

                if motion and motion_contours:
                    # Draw a combined bounding box around detected moving regions.
                    height, width, _ = frame.shape
                    xmin, ymin, xmax, ymax = width, height, 0, 0
                    for c in motion_contours:
                        x, y, w, h = cv2.boundingRect(c)
                        xmin = min(xmin, x)
                        ymin = min(ymin, y)
                        xmax = max(xmax, x + w)
                        ymax = max(ymax, y + h)
                    if xmax > 0 and ymax > 0:
                        cv2.rectangle(frame, (xmin, ymin), (xmax, ymax), (38, 167, 255), 2)

                prev_gray = gray
            else:
                prev_gray = None

            # ── Recording ────────────────────────────────────────
            currently_recording = state.ENABLE_RECORDINGS and (now_monotonic < record_until_monotonic)

            if currently_recording:
                if video_writer is None:
                    _cleanup_old_recordings()
                    fname = os.path.join(state.RECORDINGS_DIR, f"mov_{now.strftime('%Y%m%d_%H%M%S')}.mp4")
                    fourcc = cv2.VideoWriter.fourcc(*'avc1')
                    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    if actual_w <= 0 or actual_h <= 0:
                        actual_h, actual_w = frame.shape[:2]
                    video_writer = cv2.VideoWriter(fname, fourcc, state.STREAM_FPS, (actual_w, actual_h))
                    if not video_writer.isOpened():
                        fourcc = cv2.VideoWriter.fourcc(*'mp4v')
                        video_writer = cv2.VideoWriter(fname, fourcc, state.STREAM_FPS, (actual_w, actual_h))
                    if not video_writer.isOpened():
                        logger.error("Failed to initialize recording writer for %s", fname)
                        video_writer.release()
                        video_writer = None
                        currently_recording = False

                if video_writer is not None:
                    video_writer.write(frame)
            else:
                if video_writer is not None:
                    video_writer.release()
                    video_writer = None

            # ── Screen overlay ────────────────────────────────────
            _draw_overlay(frame, now, motion, currently_recording)

            # ── Encode JPEG once for all MJPEG/WS consumers ──────
            ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
            jpeg_bytes = buf.tobytes() if ret else None

            # ── Update global state ───────────────────────────────
            with state.lock:
                state.current_frame = frame
                state.current_jpeg = jpeg_bytes
                state.motion_active = motion
                state.is_recording = currently_recording

            prev_motion_state = motion
            
            for cb in list(state.on_new_frame_callbacks):
                try:
                    cb()
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            # Sleep accounting for elapsed processing time to maintain target FPS
            elapsed = time.monotonic() - _frame_start
            sleep_time = max(0.0, target_period - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
        except Exception as exc:
            logger.exception("camera_worker error: %s — restarting loop", exc)
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
            if video_writer is not None:
                try:
                    video_writer.release()
                except Exception:
                    pass
                video_writer = None

            prev_gray = None
            read_failures = 0
            prev_motion_state = False
            motion_hold_until = 0.0
            record_until_monotonic = 0.0

            with state.lock:
                state.motion_active = False
                state.is_recording = False

            time.sleep(1.0)


def _draw_overlay(frame, ts, motion, recording):
    h, w = frame.shape[:2]

    # Semi-transparent top bar
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 48), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

    # Date and time
    cv2.putText(frame, ts.strftime("%d/%m/%Y  %H:%M:%S"), (12, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (220, 220, 220), 2)

    # Motion status
    if motion:
        label = "MOTION DETECTED"
        color = (0, 60, 255)
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (0, 0, 220), 6)
    else:
        label = "LIVE"
        color = (0, 200, 80)

    cv2.putText(frame, label, (w - 340, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2)

    # REC indicator
    if recording:
        cv2.circle(frame, (w - 28, h - 24), 8, (0, 0, 240), -1)
        cv2.putText(frame, "REC", (w - 62, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 240), 2)


def _cleanup_old_recordings():
    if not os.path.isdir(state.RECORDINGS_DIR):
        return

    files = sorted(
        [f for f in os.listdir(state.RECORDINGS_DIR) if f.endswith(".mp4")],
        key=lambda f: os.path.getmtime(os.path.join(state.RECORDINGS_DIR, f))
    )
    while len(files) >= state.MAX_RECORDINGS:
        oldest = os.path.join(state.RECORDINGS_DIR, files.pop(0))
        try:
            os.remove(oldest)
        except OSError:
            break
