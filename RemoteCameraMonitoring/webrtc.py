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
video_events = set()
aiortc_loop = asyncio.new_event_loop()

def _on_new_frame():
    if not aiortc_loop.is_closed():
        for ev in list(video_events):
            aiortc_loop.call_soon_threadsafe(ev.set)

state.on_new_frame_callbacks.append(_on_new_frame)


def start_aiortc_loop():
    """Target for the aiortc background thread."""
    asyncio.set_event_loop(aiortc_loop)
    try:
        _start_shared_audio()
    except Exception as e:
        print(f"Warning: Failed to start shared audio stream: {e}")
    aiortc_loop.run_forever()


# ─────────────────────────────────────────────
#  Video Track
# ─────────────────────────────────────────────
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self._event = asyncio.Event()
        video_events.add(self._event)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = None

        while frame is None:
            with state.lock:
                frame = state.current_frame
            if frame is None:
                await self._event.wait()
                self._event.clear()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        video_frame = av.VideoFrame.from_ndarray(rgb_frame, format="rgb24")  # pyright: ignore[reportArgumentType]
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

    def stop(self):
        super().stop()
        video_events.discard(self._event)


# ─────────────────────────────────────────────
#  Audio Shared Worker & Track
# ─────────────────────────────────────────────
active_audio_tracks = set()
shared_audio_stream = None

def _start_shared_audio():
    global shared_audio_stream
    if state.AUDIO_DEVICE_INDEX is not None and state.AUDIO_DEVICE_INDEX < 0:
        return
        
    try:
        dev_info = sd.query_devices(state.AUDIO_DEVICE_INDEX, kind="input")
        native_rate = int(dev_info["default_samplerate"])
    except Exception:
        native_rate = state.AUDIO_SAMPLE_RATE

    native_blocksize = max(1, round(
        native_rate * state.AUDIO_CHUNK_FRAMES / state.AUDIO_SAMPLE_RATE
    ))

    def _sd_callback(indata, frames, time_info, status):
        pcm = indata.copy()
        for track in list(active_audio_tracks):
            if not track._queue.full():
                aiortc_loop.call_soon_threadsafe(track._queue.put_nowait, pcm)

    shared_audio_stream = sd.InputStream(
        samplerate=native_rate,
        channels=state.AUDIO_CHANNELS,
        dtype="int16",
        blocksize=native_blocksize,
        device=state.AUDIO_DEVICE_INDEX,
        callback=_sd_callback,
    )
    shared_audio_stream.start()

def _stop_shared_audio():
    global shared_audio_stream
    if shared_audio_stream:
        shared_audio_stream.stop()
        shared_audio_stream.close()
        shared_audio_stream = None


class MicrophoneAudioTrack(AudioStreamTrack):
    """
    Consumes PCM audio from the shared system microphone background thread
    and delivers av.AudioFrame objects to the WebRTC peer connection.
    """

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue(maxsize=50)
        self._pts = 0
        
        try:
            dev_info = sd.query_devices(state.AUDIO_DEVICE_INDEX, kind="input")
            self._native_rate = int(dev_info["default_samplerate"])
        except Exception:
            self._native_rate = state.AUDIO_SAMPLE_RATE
            
        layout = "mono" if state.AUDIO_CHANNELS == 1 else "stereo"
        
        # Hardware native rate to target sample rate using PyAV
        self.resampler = av.AudioResampler(
            format="s16",
            layout=layout,
            rate=state.AUDIO_SAMPLE_RATE,
        )

        active_audio_tracks.add(self)

    async def recv(self):
        pcm = await self._queue.get()

        if pcm is None:
            raise Exception("Track stopped")

        samples = pcm.T
        layout = "mono" if state.AUDIO_CHANNELS == 1 else "stereo"
        raw_frame = av.AudioFrame.from_ndarray(samples, format="s16", layout=layout)
        raw_frame.sample_rate = self._native_rate

        audio_frame = self.resampler.resample(raw_frame)[0]

        audio_frame.pts = self._pts
        self._pts += audio_frame.samples
        # time_base is automatically handled by PyAV/resampler
        return audio_frame

    def stop(self):
        super().stop()
        active_audio_tracks.discard(self)
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            pass


async def cleanup_if_stalled(pc, timeout=30):
    await asyncio.sleep(timeout)
    if pc.connectionState == "disconnected":
        await pc.close()
        pcs.discard(pc)

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
        elif pc.connectionState == "disconnected":
            asyncio.create_task(cleanup_if_stalled(pc))

    # Wait up to 5 s for the camera hardware to produce a frame
    ev = asyncio.Event()
    video_events.add(ev)
    try:
        if state.current_frame is None:
            await asyncio.wait_for(ev.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        pass
    finally:
        video_events.discard(ev)

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
    _stop_shared_audio()
    if aiortc_loop.is_running():
        future = asyncio.run_coroutine_threadsafe(close_all_pcs(), aiortc_loop)
        try:
            future.result(timeout=5)
        except Exception:
            pass
        aiortc_loop.call_soon_threadsafe(aiortc_loop.stop)
