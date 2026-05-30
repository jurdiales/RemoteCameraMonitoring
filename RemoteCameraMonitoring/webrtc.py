"""
WebRTC streaming: video/audio tracks, aiortc event loop, and offer handling.
"""

import asyncio
import fractions
import queue

import av
import cv2
import numpy as np
import sounddevice as sd
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
    AudioStreamTrack,
    VideoStreamTrack,
)

try:
    from . import state
except ImportError:
    import state

# ─────────────────────────────────────────────
#  Event loop + peer connection registry
# ─────────────────────────────────────────────
pcs = set()
aiortc_loop = asyncio.new_event_loop()


def start_aiortc_loop():
    """Target for the aiortc background thread."""
    asyncio.set_event_loop(aiortc_loop)
    aiortc_loop.run_forever()


# ─────────────────────────────────────────────
#  Video Track
# ─────────────────────────────────────────────
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = None

        while frame is None:
            with state.lock:
                frame = state.current_frame
            if frame is None:
                await asyncio.sleep(1 / state.STREAM_FPS)

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(rgb_frame, format="rgb24")  # pyright: ignore[reportArgumentType]
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


# ─────────────────────────────────────────────
#  Audio Track
# ─────────────────────────────────────────────
class MicrophoneAudioTrack(AudioStreamTrack):
    """
    Captures PCM audio from the system microphone using sounddevice and
    delivers av.AudioFrame objects to the WebRTC peer connection.
    """

    def __init__(self):
        super().__init__()
        self._queue: queue.Queue = queue.Queue(maxsize=50)
        self._pts = 0
        sd.default.device = state.AUDIO_DEVICE_INDEX

        try:
            dev_info = sd.query_devices(state.AUDIO_DEVICE_INDEX, kind="input")
            self._native_rate: int = int(dev_info["default_samplerate"])  # type: ignore[index]
        except Exception:
            self._native_rate = state.AUDIO_SAMPLE_RATE

        native_blocksize = max(1, round(
            self._native_rate * state.AUDIO_CHUNK_FRAMES / state.AUDIO_SAMPLE_RATE
        ))

        self._stream = sd.InputStream(
            samplerate=self._native_rate,
            channels=state.AUDIO_CHANNELS,
            dtype="int16",
            blocksize=native_blocksize,
            device=state.AUDIO_DEVICE_INDEX,
            callback=self._sd_callback,
        )
        self._stream.start()

    def _sd_callback(self, indata, frames, time_info, status):
        if not self._queue.full():
            self._queue.put_nowait(indata.copy())

    def _resample(self, pcm: np.ndarray) -> np.ndarray:
        n_in = pcm.shape[0]
        n_out = round(n_in * state.AUDIO_SAMPLE_RATE / self._native_rate)
        xi = np.linspace(0.0, 1.0, n_in)
        xo = np.linspace(0.0, 1.0, n_out)
        if state.AUDIO_CHANNELS == 1:
            return np.interp(xo, xi, pcm[:, 0]).astype(np.int16).reshape(-1, 1)
        return np.column_stack([
            np.interp(xo, xi, pcm[:, ch]).astype(np.int16)
            for ch in range(state.AUDIO_CHANNELS)
        ])

    async def recv(self):
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, self._queue.get)

        if pcm is None:
            raise Exception("Track stopped")

        if self._native_rate != state.AUDIO_SAMPLE_RATE:
            pcm = self._resample(pcm)

        samples = pcm.T
        layout = "mono" if state.AUDIO_CHANNELS == 1 else "stereo"
        audio_frame = av.AudioFrame.from_ndarray(samples, format="s16", layout=layout)  # pyright: ignore[reportArgumentType]
        audio_frame.sample_rate = state.AUDIO_SAMPLE_RATE
        audio_frame.pts = self._pts
        audio_frame.time_base = fractions.Fraction(1, state.AUDIO_SAMPLE_RATE)
        self._pts += state.AUDIO_CHUNK_FRAMES
        return audio_frame

    def stop(self):
        if hasattr(self, '_stream'):
            self._stream.stop()
            self._stream.close()

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass

        super().stop()


# ─────────────────────────────────────────────
#  Offer handling
# ─────────────────────────────────────────────
async def handle_offer(data):
    """Process a WebRTC SDP offer and return the answer."""
    offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
    pc = RTCPeerConnection(
        configuration=RTCConfiguration(
            iceServers=[RTCIceServer("stun:stun.l.google.com:19302")]
        )
    )
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            pcs.discard(pc)

    # Wait up to 5 s for the camera hardware to produce a frame
    deadline_cam = aiortc_loop.time() + 5.0
    while aiortc_loop.time() < deadline_cam:
        with state.lock:
            if state.current_frame is not None:
                break
        await asyncio.sleep(0.1)

    pc.addTrack(CameraVideoTrack())
    if (state.AUDIO_DEVICE_INDEX is None) or (state.AUDIO_DEVICE_INDEX >= 0):
        try:
            pc.addTrack(MicrophoneAudioTrack())
        except Exception as e:
            print(f"Warning: Failed to open microphone: {e}")

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Wait for ICE gathering (up to 5 s)
    deadline = aiortc_loop.time() + 5.0
    while pc.iceGatheringState != "complete" and aiortc_loop.time() < deadline:
        await asyncio.sleep(0.1)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


def run_coroutine(coro, timeout=15):
    """Submit a coroutine to the aiortc loop and block until done (with timeout)."""
    return asyncio.run_coroutine_threadsafe(coro, aiortc_loop).result(timeout=timeout)


async def close_all_pcs():
    """Close all active peer connections."""
    coros = [pc.close() for pc in list(pcs)]
    if coros:
        await asyncio.gather(*coros, return_exceptions=True)
    pcs.clear()


def cleanup():
    """Gracefully shut down the aiortc event loop and all peer connections."""
    if aiortc_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(close_all_pcs(), aiortc_loop)
        try:
            future.result(timeout=5)
        except Exception:
            pass
        aiortc_loop.call_soon_threadsafe(aiortc_loop.stop)
